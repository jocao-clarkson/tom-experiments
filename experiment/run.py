"""Run the plan-phase validation gate over the experiment cases.

Each run (case x technique x rep) gets a fresh temp folder holding the case's
fixture, spec, plan and this repo's .claude/ (skill + lens agents), then a
fresh headless orchestrator:

    claude -p "/validation-orchestrator phase=plan spec=... plan=... technique=..."

Results land in experiment/results/<run-id>/runs/<case>/<technique>/rep<k>/.
A run that finished has a done.json and is skipped when the same run-id is
re-run, so an interrupted batch can resume.

Two-round techniques run round 2 as its own session, started from a finished
round 1 written into the workspace (round1=...). second-round and debate reuse
the `baseline` run's round 1; PTU's predicting round 1 runs in ptu/rep<k>/round1/.
A failed round 2 is retried without redoing round 1. --single-session runs
both rounds in one session instead.

    py experiment\\run.py --run-id pilot --cases pilot --reps 1
    py experiment\\run.py --run-id smoke --cases case-01,case-02 --mock
"""

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent
REPO = EXP.parent
CASES = EXP / "cases"
RESULTS = EXP / "results"

TECHNIQUES = ["baseline", "second-round", "debate", "ptu"]
LENSES = [
    "lens-spec-coverage",
    "lens-consistency",
    "lens-architecture",
    "lens-risk",
    "lens-tests",
]
ROUNDS = {"baseline": 1, "second-round": 2, "debate": 2, "ptu": 2}
LENS_CALLS = {t: 5 * n for t, n in ROUNDS.items()}

SPEC_REL = "specs/feature/spec.md"
PLAN_REL = "specs/feature/plan.md"
ROUND1_REL = "specs/feature/round1-findings.md"
BRIEFS_REL = "specs/feature/round1-briefs.md"
ORCHESTRATOR_TOOLS = "Skill,Agent,Read,Grep,Glob,Bash,Write"
STOP_AFTER_FAILURES = 3
EFFORTS = ["low", "medium", "high", "xhigh", "max"]

# Unless --single-session, a two-round technique's round 2 is its own session
# that starts from a finished round 1 (its "base"). second-round and debate
# share the standard round 1, which is the `baseline` run itself; PTU's round 1
# asks for predictions, so it runs alone in ptu/rep<k>/round1/.
ROUND1_BASE = {"second-round": "baseline", "debate": "baseline", "ptu": "ptu"}


# --------------------------------------------------------------------------
# claude -p (real or mock)


def claude_command(args, mock):
    """Command line for `claude <args>`, or for the fake claude in --mock mode."""
    if mock:
        return [sys.executable, str(Path(__file__).resolve()), "_fake-claude", *args]
    exe = shutil.which("claude")
    if not exe:
        sys.exit("claude not found on PATH. Install Claude Code or use --mock.")
    return [exe, *args]


def call_claude(args, cwd, mock, stdin_text="", timeout=3600):
    """Run claude. Returns (exit_code, stdout, stderr, wall_seconds, timed_out)."""
    cmd = claude_command(args, mock)
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        out, err = proc.communicate(stdin_text.encode("utf-8"), timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        out, err = proc.communicate()
        timed_out = True
    wall = time.monotonic() - start
    return (
        proc.returncode,
        out.decode("utf-8", "replace"),
        err.decode("utf-8", "replace"),
        wall,
        timed_out,
    )


def kill_tree(proc):
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc.kill()


def result_event(stdout):
    """The final {"type": "result"} object from json or stream-json output."""
    found = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result":
            found = ev
    return found


LIMIT_ERROR = re.compile(r'"api_error"\s*:\s*"usage_limit_reached"|"error"\s*:\s*"rate_limit"')
LIMIT_TEXT = re.compile(r"session limit|usage limit|weekly limit|rate limit|limit reached|quota", re.I)
POLL_SECONDS = 20 * 60


def usage_limited(stdout, result_text, stderr):
    """Whether claude stopped on a usage limit. The structured error is checked
    in the whole stream, the wording only in the result and stderr: lens output
    can mention rate limits."""
    return bool(LIMIT_ERROR.search(stdout) or LIMIT_TEXT.search(result_text + stderr))


def reset_time(text):
    """Epoch seconds when the usage limit lifts, from claude's output, or None."""
    # The rejected window's reset, not the other windows listed beside it
    # (a weekly window can reset days later than the 5-hour one that hit).
    times = [int(t) for t in re.findall(r'"status"\s*:\s*"rejected"\s*,\s*"resetsAt"\s*:\s*(\d+)', text)]
    if times:
        return max(times)
    m = re.search(r"resets (\d{1,2})(?::(\d{2}))?\s*([ap]m)", text, re.I)
    if not m:
        return None
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    t = datetime.datetime.now().replace(hour=hour, minute=int(m.group(2) or 0), second=0, microsecond=0)
    if t <= datetime.datetime.now():
        t += datetime.timedelta(days=1)
    return int(t.timestamp())


def wait_for_reset(resets_at, deadline):
    """Sleep until the usage limit should have lifted, or POLL_SECONDS if the
    reset time is unknown. False, without sleeping, if that is past deadline."""
    wake = max(resets_at + 120 if resets_at else time.time() + POLL_SECONDS, time.time() + 60)
    when = datetime.datetime.fromtimestamp(wake).strftime("%a %H:%M")
    if wake > deadline:
        print(f"usage limit lifts after the --wait-for-reset window (around {when}); giving up", flush=True)
        return False
    print(f"usage limit; waiting until {when} to resume", flush=True)
    time.sleep(wake - time.time())
    return True


def usage_summary(result):
    """Token counts from a result event, summed over every model it reports."""
    if not result:
        return {}
    usage = result.get("usage") or {}
    summary = {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
    }
    model_usage = result.get("modelUsage") or {}
    if model_usage:
        # modelUsage breaks usage down per model; when present it is the
        # better total because it can include subagent (lens) models.
        totals = dict.fromkeys(summary, 0)
        for m in model_usage.values():
            totals["input_tokens"] += m.get("inputTokens", 0)
            totals["output_tokens"] += m.get("outputTokens", 0)
            totals["cache_creation_input_tokens"] += m.get("cacheCreationInputTokens", 0)
            totals["cache_read_input_tokens"] += m.get("cacheReadInputTokens", 0)
        summary = totals
        summary["models"] = sorted(model_usage)
    summary["total_tokens"] = sum(
        v for k, v in summary.items() if k.endswith("tokens")
    )
    return summary


# --------------------------------------------------------------------------
# Lens outputs from the transcript


ASYNC_LAUNCH = "Async agent launched"
HANDBACK = "[Subagent hand-back]"


def unwrap_handback(text):
    """A foreground Agent result frames the lens's report: a notice line, the
    report indented two spaces, then agentId/<usage> lines at column zero.
    Return the report as the lens wrote it."""
    if not text.startswith(HANDBACK):
        return text
    body = text.split("\n", 1)[1] if "\n" in text else ""
    report = []
    for line in body.split("\n"):
        if line.startswith("  "):
            report.append(line[2:])
        elif line == "":
            report.append("")
        else:
            break  # first column-zero line is the harness trailer
    return "\n".join(report).strip("\n")


def extract_lens_outputs(stdout):
    """Pull every top-level Agent call and its verbatim result out of stream-json.

    Lenses usually run as background agents: the Agent tool_result is only a
    launch notice, and the lens's final text arrives later in a system
    task_notification event (its `summary`) with the same tool_use_id.
    """
    calls = {}
    order = []
    notifications = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict) or ev.get("parent_tool_use_id"):
            continue  # events from inside a subagent
        if ev.get("type") == "system" and ev.get("subtype") == "task_notification":
            notifications[ev.get("tool_use_id")] = ev
            continue
        message = ev.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if (
                ev.get("type") == "assistant"
                and item.get("type") == "tool_use"
                and item.get("name") in ("Agent", "Task")
            ):
                inp = item.get("input") or {}
                calls[item["id"]] = {
                    "lens": inp.get("subagent_type", ""),
                    "prompt": inp.get("prompt", ""),
                    "output": None,
                }
                order.append(item["id"])
            elif ev.get("type") == "user" and item.get("type") == "tool_result":
                call = calls.get(item.get("tool_use_id"))
                if call is not None:
                    call["output"] = unwrap_handback(tool_result_text(item.get("content")))
                    call["is_error"] = bool(item.get("is_error"))

    for cid, call in calls.items():
        if call["output"] is not None and call["output"].startswith(ASYNC_LAUNCH):
            note = notifications.get(cid)
            call["background"] = True
            call["status"] = note.get("status") if note else None
            call["output"] = note.get("summary") if note and note.get("status") == "completed" else None

    rounds = {}
    problems = []
    for cid in order:
        call = calls[cid]
        m = re.search(r"^ROUND:\s*(\d+)", call["prompt"], re.M)
        call["round"] = int(m.group(1)) if m else 1
        if call["lens"] not in LENSES:
            problems.append(f"non-lens agent call: {call['lens']!r}")
            continue
        slot = rounds.setdefault(str(call["round"]), {})
        if call["lens"] in slot:
            problems.append(f"lens {call['lens']} called twice in round {call['round']}; kept last")
        if not call["output"]:
            problems.append(f"no result for {call['lens']} round {call['round']}")
            continue  # leaves the slot empty, so the run is not complete
        slot[call["lens"]] = call["output"]
    return {
        "source": "transcript",
        "rounds": rounds,
        "calls": [calls[c] for c in order],
        "problems": problems,
    }


def tool_result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
        )
    return ""


def complete(rounds, technique, want=None):
    want = want or ROUNDS[technique]
    return all(
        set(LENSES) <= set(rounds.get(str(r), {})) for r in range(1, want + 1)
    )


# --------------------------------------------------------------------------
# Cases and schedule


def all_cases():
    return sorted(
        p.name for p in CASES.iterdir() if p.is_dir() and (p / "ground_truth.json").exists()
    )


def case_type(case):
    gt = json.loads((CASES / case / "ground_truth.json").read_text(encoding="utf-8"))
    return gt.get("type")


def select_cases(spec):
    cases = all_cases()
    if spec == "all":
        return cases
    if spec == "pilot":
        # 5 tension + 1 clean, picked deterministically. Only the type field
        # is read, so the operator stays blind to the seeded defects.
        def key(c):
            return hashlib.sha256(f"pilot:{c}".encode()).hexdigest()

        tension = sorted((c for c in cases if case_type(c) == "tension"), key=key)[:5]
        clean = sorted((c for c in cases if case_type(c) == "clean"), key=key)[:1]
        if len(tension) < 5 or len(clean) < 1:
            sys.exit("pilot needs at least 5 tension cases and 1 clean case")
        return sorted(tension + clean)
    chosen = [c.strip() for c in spec.split(",") if c.strip()]
    unknown = [c for c in chosen if c not in cases]
    if unknown:
        sys.exit(f"unknown cases: {', '.join(unknown)}")
    return chosen


def case_hash(case):
    """Hash of every file in the case folder, so runs on different versions
    of a case can be told apart."""
    h = hashlib.sha256()
    for f in sorted(p for p in (CASES / case).rglob("*") if p.is_file()):
        h.update(f.relative_to(CASES / case).as_posix().encode() + b"\0" + f.read_bytes())
    return h.hexdigest()[:16]


def run_dir(run_id, case, technique, rep):
    return RESULTS / run_id / "runs" / case / technique / f"rep{rep}"


def base_dir(run_id, case, technique, rep):
    """Where the round 1 that `technique`'s round-2 session starts from lives."""
    base = ROUND1_BASE[technique]
    if base == technique:
        return run_dir(run_id, case, technique, rep) / "round1"
    return run_dir(run_id, case, base, rep)


def record_config(run_id, args, cases, techniques):
    root = RESULTS / run_id
    root.mkdir(parents=True, exist_ok=True)
    path = root / "config.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if config and config.get("mock") != args.mock:
        sys.exit(
            f"run-id {run_id!r} was created with mock={config.get('mock')}; "
            "use a different --run-id instead of mixing mock and real runs"
        )
    config.setdefault("mock", args.mock)
    config.setdefault("created", now())
    config.setdefault("invocations", []).append(
        {
            "at": now(),
            "cases": cases,
            "techniques": techniques,
            "reps": args.reps,
            "orchestrator_model": args.orchestrator_model,
            "orchestrator_effort": args.orchestrator_effort,
            "single_session": args.single_session,
            "workers": args.workers,
        }
    )
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# One run


def prepare_workdir(case):
    """Fresh folder with the fixture at the root, the skill and lenses, and the
    spec and plan. ground_truth.json is never copied."""
    work = Path(tempfile.mkdtemp(prefix="vgate-"))
    src = CASES / case
    shutil.copytree(src / "fixture", work, dirs_exist_ok=True)
    for sub in ("agents", "skills"):
        shutil.copytree(REPO / ".claude" / sub, work / ".claude" / sub)
    (work / "specs" / "feature").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "spec.md", work / SPEC_REL)
    shutil.copy2(src / "plan.md", work / PLAN_REL)
    if shutil.which("git"):
        quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        ident = ["-c", "user.name=experiment", "-c", "user.email=experiment@example.invalid"]
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=work, **quiet)
        subprocess.run(["git", "add", "-A"], cwd=work, **quiet)
        subprocess.run(["git", *ident, "commit", "-q", "-m", "initial"], cwd=work, **quiet)
    return work


def remove_tree(path):
    """rmtree that also removes read-only files (git objects on Windows)."""
    def make_writable_and_retry(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=make_writable_and_retry)
        else:
            shutil.rmtree(path, onerror=make_writable_and_retry)
    except OSError:
        pass  # a leftover temp folder is not worth failing a run over


def check_round1_file(work, out, rounds, technique):
    """Keep the round1-findings.md the orchestrator handed to round 2, and note
    per lens whether its block matches the round-1 output from the transcript."""
    if ROUNDS[technique] < 2:
        return None
    path = work / Path(SPEC_REL).parent / "round1-findings.md"
    if not path.exists():
        return {"present": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    (out / "round1-findings.md").write_text(text, encoding="utf-8")

    def norm(s):
        return "\n".join(line.rstrip() for line in s.strip().splitlines())

    blocks = dict(re.findall(r"^=== (lens-[\w-]+) ===\n(.*?)(?=^=== lens-[\w-]+ ===$|\Z)", text, re.M | re.S))
    r1 = rounds.get("1", {})
    return {"present": True,
            "verbatim": {l: l in blocks and l in r1 and norm(blocks[l]) == norm(r1[l]) for l in LENSES}}


def load_base(bdir):
    """A finished round 1: the five outputs, the brief each lens got, and what
    the session cost. None if it hasn't finished."""
    if not (bdir / "done.json").exists():
        return None
    lens = json.loads((bdir / "lens_outputs.json").read_text(encoding="utf-8"))
    meta = json.loads((bdir / "meta.json").read_text(encoding="utf-8"))
    r1 = lens["rounds"].get("1", {})
    if not complete(lens["rounds"], meta["technique"], want=1):
        return None
    briefs = {c["lens"]: c["prompt"] for c in lens["calls"] if c.get("round") == 1 and c["lens"] in LENSES}
    return {
        "from": bdir.relative_to(RESULTS).as_posix(),
        "rounds": {l: r1[l] for l in LENSES},
        "briefs": briefs,
        "usage": meta.get("usage") or {},
        "wall_seconds": meta.get("wall_seconds"),
    }


def write_round1(work, base):
    """Hand round 1 to the round-2 session as files, copied from the base's
    transcript, so the orchestrator never retypes it."""
    def blocks(texts):
        return "".join(f"=== {l} ===\n{texts.get(l, '').strip()}\n\n" for l in LENSES)

    (work / ROUND1_REL).write_text(blocks(base["rounds"]), encoding="utf-8")
    (work / BRIEFS_REL).write_text(blocks(base["briefs"]), encoding="utf-8")


def run_one(run_id, case, technique, rep, args, stage="full"):
    """stage "full" runs every round in one session; "round1" runs only PTU's
    first round (its base); "round2" starts from the finished base round 1."""
    out = run_dir(run_id, case, technique, rep)
    if stage == "round1":
        out = out / "round1"
    out.mkdir(parents=True, exist_ok=True)
    # The judge scores against this copy, not the live case, which may be
    # revised later. It stays out of the lenses' workspace.
    shutil.copy2(CASES / case / "ground_truth.json", out / "ground_truth.json")
    work = prepare_workdir(case)
    prompt = (
        f"/validation-orchestrator phase=plan spec={SPEC_REL} "
        f"plan={PLAN_REL} technique={technique}"
    )
    base = None
    if stage == "round1":
        prompt += " stop=round1"
    elif stage == "round2":
        base = load_base(base_dir(run_id, case, technique, rep))
        if base is None:
            raise RuntimeError(f"{case} {technique} rep{rep}: base round 1 is not done")
        write_round1(work, base)
        prompt += f" round1={ROUND1_REL}"
    claude_args = [
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--model", args.orchestrator_model,
        "--allowedTools", ORCHESTRATOR_TOOLS,
    ]
    if args.orchestrator_effort != "default":
        claude_args += ["--effort", args.orchestrator_effort]
    started = now()
    code, stdout, stderr, wall, timed_out = call_claude(
        claude_args, work, args.mock, timeout=args.timeout
    )

    (out / "transcript.jsonl").write_text(stdout, encoding="utf-8")
    if stderr.strip():
        (out / "stderr.txt").write_text(stderr, encoding="utf-8")
    lens = extract_lens_outputs(stdout)
    lens_calls = len([c for c in lens["calls"] if c["lens"] in LENSES])
    if base:
        if lens["rounds"].pop("1", None):
            lens["problems"].append("round-1 lens calls in a round-2 session; replaced with the base round 1")
        lens["rounds"]["1"] = base["rounds"]
        lens["round1_from"] = base["from"]
    lens["complete"] = complete(lens["rounds"], technique, want=1 if stage == "round1" else None)
    (out / "lens_outputs.json").write_text(json.dumps(lens, indent=2), encoding="utf-8")

    result = result_event(stdout)
    reason = None
    if timed_out:
        reason = "timeout"
    elif code != 0:
        reason = f"exit {code}"
    elif result is None:
        reason = "no result event"
    elif result.get("is_error"):
        reason = f"result error: {result.get('subtype')}"
    elif not lens["complete"]:
        reason = "lens outputs incomplete"
    result_text = (result or {}).get("result") or ""
    resets_at = None
    if reason and usage_limited(stdout, result_text, stderr):
        reason += " (looks like a usage limit)"
        resets_at = reset_time(stdout + result_text + stderr)

    meta = {
        "run_id": run_id,
        "case": case,
        "technique": technique,
        "rep": rep,
        "stage": stage,
        "case_hash": case_hash(case),
        "status": "failed" if reason else "ok",
        "reason": reason,
        "resets_at": resets_at,
        "exit_code": code,
        "started_at": started,
        "finished_at": now(),
        "wall_seconds": round(wall, 1),
        "usage": usage_summary(result),
        "num_turns": (result or {}).get("num_turns"),
        "duration_ms": (result or {}).get("duration_ms"),
        "lens_calls": lens_calls,
        "expected_lens_calls": LENS_CALLS[technique] if stage == "full" else 5,
        "lens_outputs_complete": lens["complete"],
        "round1_file": check_round1_file(work, out, lens["rounds"], technique) if stage == "full" else None,
        # A round-2 session's cost excludes the round 1 it started from; analyze
        # adds these back so every technique is costed end to end.
        "round1_from": base["from"] if base else None,
        "round1_usage": base["usage"] if base else None,
        "round1_wall_seconds": base["wall_seconds"] if base else None,
        "orchestrator_model": args.orchestrator_model,
        "orchestrator_effort": args.orchestrator_effort,
        "mock": args.mock,
        "command": ["claude", *claude_args],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not reason:
        (out / "done.json").write_text(json.dumps({"finished_at": meta["finished_at"]}), encoding="utf-8")
    if not args.keep_tmp:
        remove_tree(work)
    return meta


# --------------------------------------------------------------------------
# Main


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cases", default="all", help='"all", "pilot" (5 tension + 1 clean), or a comma list like case-01,case-02')
    p.add_argument("--techniques", default=",".join(TECHNIQUES), help="comma list from: " + ", ".join(TECHNIQUES))
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--run-id", required=True)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--mock", action="store_true", help="fake claude -p; spends no usage")
    p.add_argument("--orchestrator-model", default="opus")
    p.add_argument("--orchestrator-effort", default="medium", choices=["default", *EFFORTS],
                   help='--effort for the orchestrator session; "default" leaves it unset')
    p.add_argument("--single-session", action="store_true",
                   help="run both rounds of a technique in one session (no shared round 1)")
    p.add_argument("--timeout", type=int, default=3600, help="seconds per run")
    p.add_argument("--wait-for-reset", type=float, nargs="?", const=24, default=None, metavar="HOURS",
                   help="after a usage limit, wait for it to reset and resume; give up after HOURS (default 24)")
    p.add_argument("--keep-tmp", action="store_true", help="keep each run's temp folder")
    args = p.parse_args(argv)

    techniques = [t.strip() for t in args.techniques.split(",") if t.strip()]
    bad = [t for t in techniques if t not in TECHNIQUES]
    if bad:
        sys.exit(f"unknown techniques: {', '.join(bad)}")
    cases = select_cases(args.cases)
    record_config(args.run_id, args, cases, techniques)

    tasks = [
        (c, t, r) for c in cases for t in techniques for r in range(1, args.reps + 1)
    ]
    # Interleave cases and techniques so drift over a long batch (or hitting a
    # usage limit) doesn't line up with one technique.
    random.Random(args.run_id).shuffle(tasks)
    deadline = time.time() + 3600 * args.wait_for_reset if args.wait_for_reset else None
    while True:
        rc, state = run_batch(args, tasks)
        if not (deadline and state["resume_after_limit"]):
            return rc
        if not wait_for_reset(state["resets_at"], deadline):
            return rc


def run_batch(args, tasks):
    """Run every unfinished task once. Returns (exit code, state)."""
    todo = [x for x in tasks if not (run_dir(args.run_id, *x) / "done.json").exists()]

    def split(t):
        return not args.single_session and ROUNDS[t] == 2

    def base_session(c, t, r):
        """(case, technique, rep, stage) of the session that makes t's round 1."""
        b = ROUND1_BASE[t]
        return (c, b, r, "round1" if b == t else "full")

    # Sessions still to run: a round-2 session also needs its base, and
    # second-round and debate share one (the `baseline` run).
    sessions = set()
    for c, t, r in todo:
        if split(t):
            if not (base_dir(args.run_id, c, t, r) / "done.json").exists():
                sessions.add(base_session(c, t, r))
            sessions.add((c, t, r, "round2"))
        else:
            sessions.add((c, t, r, "full"))
    print(f"{len(tasks)} runs in plan, {len(tasks) - len(todo)} already done, {len(todo)} to go "
          f"({len(sessions)} sessions)" + (" [mock]" if args.mock else ""))
    if not todo:
        return 0, {"resume_after_limit": False}

    lock = threading.Lock()
    stop = threading.Event()
    state = {"failures_in_a_row": 0, "ok": 0, "failed": 0, "why": None,
             "resume_after_limit": False, "resets_at": None}
    base_locks = {}

    def session(c, t, r, stage):
        """Run one session and report it. True if it succeeded."""
        if stop.is_set():
            return False
        meta = run_one(args.run_id, c, t, r, args, stage)
        with lock:
            n = state["ok"] + state["failed"] + 1
            label = t if stage == "full" else f"{t} {stage}"
            tag = "ok" if meta["status"] == "ok" else f"FAILED ({meta['reason']})"
            print(f"[{n}/{len(sessions)}] {c} {label} rep{r}: {tag} {meta['wall_seconds']}s", flush=True)
            if meta["status"] == "ok":
                state["ok"] += 1
                state["failures_in_a_row"] = 0
                return True
            state["failed"] += 1
            state["failures_in_a_row"] += 1
            if "usage limit" in (meta["reason"] or ""):
                # Every session after this fails the same way, so stop now
                # instead of burning the next ones.
                state["why"] = "a usage limit"
                state["resume_after_limit"] = True
                state["resets_at"] = meta.get("resets_at")
                stop.set()
            elif state["failures_in_a_row"] >= STOP_AFTER_FAILURES:
                state["why"] = f"{STOP_AFTER_FAILURES} failures in a row"
                stop.set()
            return False

    def work(task):
        c, t, r = task
        if stop.is_set() or (run_dir(args.run_id, c, t, r) / "done.json").exists():
            return  # finished meanwhile, as another technique's base
        if args.single_session:
            session(c, t, r, "full")
            return
        # `baseline` is also the shared base, so it takes the same lock as the
        # round-2 sessions waiting on it.
        key = base_session(c, t, r) if split(t) else (c, t, r, "full")
        bdir = base_dir(args.run_id, c, t, r) if split(t) else run_dir(args.run_id, c, t, r)
        with lock:
            base_lock = base_locks.setdefault(key, threading.Lock())
        with base_lock:
            if not (bdir / "done.json").exists() and not session(*key):
                return
        if split(t):
            session(c, t, r, "round2")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(work, todo))

    print(f"done: {state['ok']} ok, {state['failed']} failed")
    if stop.is_set():
        print(f"stopped after {state['why']}. Check the last meta.json, "
              "then re-run the same command to resume.")
        return 1, state
    return (0 if state["failed"] == 0 else 1), state


# --------------------------------------------------------------------------
# Fake claude for --mock. Writes the same files and emits the same stream
# shape as a real run, so everything downstream gets exercised.

PREFIX = {
    "lens-spec-coverage": "COV",
    "lens-consistency": "CON",
    "lens-architecture": "ARC",
    "lens-risk": "RSK",
    "lens-tests": "TST",
}
TITLES = {
    "lens-spec-coverage": ["AC not mapped to any step", "Requirement only partly covered", "Step serves no requirement"],
    "lens-consistency": ["Plan changes the spec's default", "Spec silent, plan assumes behaviour", "Same field, two names"],
    "lens-architecture": ["Rebuilds an existing helper", "Crosses the service/repository boundary", "Step depends on a later step"],
    "lens-risk": ["Unbounded retry on write", "No timeout on outbound call", "Sensitive field logged"],
    "lens-tests": ["AC too vague to test", "No error-path tests planned", "Existing tests will break"],
}


def fake_claude(argv):
    prompt = argv[argv.index("-p") + 1] if "-p" in argv else ""
    stdin = sys.stdin.buffer.read().decode("utf-8", "replace")
    time.sleep(0.05)
    if prompt.startswith("/validation-orchestrator"):
        fake_orchestrator(prompt)
    else:
        fake_judge(stdin)
    return 0


def emit(obj):
    sys.stdout.buffer.write((json.dumps(obj) + "\n").encode("utf-8"))


def fake_findings(rng, lens, n):
    out = []
    for i in range(1, n + 1):
        out.append({
            "id": f"{PREFIX[lens]}-{i}",
            "severity": rng.choice(["blocker", "major", "minor"]),
            "fix_in": rng.choice(["plan", "plan", "spec"]),
            "title": rng.choice(TITLES[lens]),
            "evidence": f'plan.md step {rng.randint(1, 10)}: "..."',
            "detail": "Mock detail.",
            "recommendation": "Mock recommendation.",
        })
    return out


def lens_text(lens, findings, extra=""):
    lines = [f"LENS: {lens}", "PHASE: plan", "SUMMARY: Mock summary.", ""]
    if findings:
        lines.append("FINDINGS:")
        for f in findings:
            lines.append(f"- id: {f['id']}")
            for k in ("severity", "fix_in", "title", "evidence", "detail", "recommendation"):
                lines.append(f"  {k}: {f[k]}")
    else:
        lines.append("FINDINGS: none")
    if lens == "lens-spec-coverage":
        lines += ["", "TRACEABILITY:", "| ID | Requirement (short) | Plan step | Implementation | Test | Status |",
                  "| R1 | mock | 2 | - | - | ok |"]
    return "\n".join(lines) + ("\n\n" + extra if extra else "")


def fake_orchestrator(prompt):
    params = dict(re.findall(r"(\w+)=(\S+)", prompt))
    technique = params.get("technique", "baseline")
    given_round1 = "round1" in params and Path(params["round1"]).exists()
    stop_after_round1 = params.get("stop") == "round1"
    plan = Path(params.get("plan", PLAN_REL))
    plan_text = plan.read_text(encoding="utf-8", errors="replace") if plan.exists() else ""
    seed = hashlib.sha256((plan_text + technique).encode()).hexdigest()
    rng = random.Random(seed)
    emit({"type": "system", "subtype": "init", "model": "mock"})

    def round_of(n, outputs):
        uses = []
        for lens in LENSES:
            tid = f"toolu_{n}_{PREFIX[lens]}"
            brief = f"PHASE: plan\nROUND: {n}\n" if n > 1 else "PHASE: plan\n"
            if technique == "ptu" and n == 1:
                brief += "PREDICT PEERS: yes\n"
            uses.append({"type": "tool_use", "id": tid, "name": "Agent",
                         "input": {"subagent_type": lens, "description": lens, "prompt": brief}})
        emit({"type": "assistant", "parent_tool_use_id": None, "message": {"content": uses}})
        for lens in LENSES:
            emit({"type": "user", "parent_tool_use_id": None, "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"toolu_{n}_{PREFIX[lens]}",
                 "content": [{"type": "text", "text": outputs[lens]}]}]}})

    r1_findings = {lens: fake_findings(rng, lens, rng.randint(0, 3)) for lens in LENSES}
    r1 = {}
    for lens in LENSES:
        extra = ""
        if technique == "ptu":
            parts = ["PREDICTIONS:"]
            for peer in LENSES:
                if peer == lens:
                    continue
                parts += [f"- peer: {peer}", "  will_flag:", f"    - {rng.choice(TITLES[peer])} near plan.md step {rng.randint(1, 10)}"]
                mine = r1_findings[lens]
                if mine and rng.random() < 0.4:
                    parts += ["  conflicts_with_mine:", f"    - mine: {mine[0]['id']}", "      expect: mock conflict"]
                else:
                    parts.append("  conflicts_with_mine: none")
            extra = "\n".join(parts)
        r1[lens] = lens_text(lens, r1_findings[lens], extra)
    rounds = {}
    if not given_round1:
        round_of(1, r1)
        rounds["1"] = r1

    if ROUNDS.get(technique, 1) == 2 and not stop_after_round1:
        r2 = {}
        for lens in LENSES:
            kept = [f for f in r1_findings[lens] if rng.random() > 0.2]
            if rng.random() < 0.3:
                kept += fake_findings(rng, lens, 1)
                kept[-1]["id"] = f"{PREFIX[lens]}-{len(r1_findings[lens]) + 1}"
            extra = ""
            if technique == "debate":
                extra = "DEBATE: none" if not kept else (
                    f"DEBATE:\n- re: {kept[0]['id']}\n  conflicts_with: RSK-1\n  stance: defend\n  reason: mock")
            elif technique == "ptu":
                extra = "SURPRISE RESPONSES:\n- surprise: S1\n  changes_view: no\n  why: mock"
            r2[lens] = lens_text(lens, kept, extra)
        round_of(2, r2)
        rounds["2"] = r2

    n_calls = 5 * len(rounds)
    emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 4 + n_calls,
          "duration_ms": 1000 * n_calls, "result": "Lens rounds complete.",
          "usage": {"input_tokens": 2000, "output_tokens": 800,
                    "cache_creation_input_tokens": 0, "cache_read_input_tokens": 5000},
          "modelUsage": {"mock-orchestrator": {"inputTokens": 2000, "outputTokens": 800,
                                               "cacheReadInputTokens": 5000, "cacheCreationInputTokens": 0},
                         "mock-lens": {"inputTokens": 9000 * n_calls, "outputTokens": 1200 * n_calls,
                                       "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0}}})


def fake_judge(stdin):
    task = re.search(r"JUDGE TASK:\s*(\w+)", stdin).group(1)
    data = json.loads(stdin.split("<<<INPUT_JSON", 1)[1].split("INPUT_JSON>>>", 1)[0])
    rng = random.Random(hashlib.sha256(stdin.encode()).hexdigest())
    if task == "contradictions":
        refs = [(lens, f["id"]) for lens, fs in data["findings"].items() for f in fs]
        contradictions = []
        for _ in range(rng.randint(0, 3)):
            if len(refs) < 2:
                break
            a, b = rng.sample(refs, 2)
            if a[0] != b[0]:
                contradictions.append({"a": {"lens": a[0], "id": a[1]}, "b": {"lens": b[0], "id": b[1]},
                                       "topic": "mock", "why": "mock"})
        answer = {"topics": [{"topic": "mock", "findings": [{"lens": l, "id": i} for l, i in refs[:2]]}],
                  "contradictions": contradictions}
    elif task == "final":
        defects = [d["id"] for d in data["defects"]]
        findings, refs = [], []
        for lens, fs in data["findings"].items():
            for f in fs:
                refs.append((lens, f["id"]))
                match = [rng.choice(defects)] if defects and rng.random() < 0.5 else []
                findings.append({"lens": lens, "id": f["id"], "matches_defects": match,
                                 "out_of_lane": rng.random() < 0.1, "note": "mock"})
        contradictions = []
        for _ in range(rng.randint(0, 3)):
            if len(refs) < 2:
                break
            a, b = rng.sample(refs, 2)
            if a[0] != b[0]:
                contradictions.append({"a": {"lens": a[0], "id": a[1]}, "b": {"lens": b[0], "id": b[1]},
                                       "why": "mock"})
        tensions = [{"id": t["id"], "status": rng.choice(["reconciled", "unreconciled_conflict", "unreconciled_compatible", "one_side_only", "neither"]),
                     "evidence": "mock"} for t in data["tensions"]]
        answer = {"findings": findings, "contradictions": contradictions, "tensions": tensions}
    elif task == "flips":
        defects = [d["id"] for d in data["defects"]]
        matches = []
        for lens, fs in data["round1"].items():
            r2_ids = {f["id"] for f in data["round2"].get(lens, [])}
            for f in fs:
                if defects and rng.random() < 0.5:
                    status = "kept" if f["id"] in r2_ids else "dropped"
                    matches.append({"lens": lens, "id": f["id"], "defect": rng.choice(defects),
                                    "round2_status": status, "round2_id": f["id"] if status == "kept" else None,
                                    "note": "mock"})
        answer = {"round1_matches": matches}
    else:
        pairs = []
        for lens, info in data["lenses"].items():
            for peer, peer_findings in info["peer_findings"].items():
                pairs.append({
                    "lens": lens, "peer": peer,
                    "predictions": [{"text": "mock", "kind": "will_flag", "came_true": rng.random() < 0.5,
                                     "matched_ids": []}],
                    "peer_findings": [{"id": f["id"], "predicted": rng.random() < 0.4} for f in peer_findings],
                })
        answer = {"pairs": pairs}
    sys.stdout.buffer.write(json.dumps({
        "type": "result", "subtype": "success", "is_error": False, "duration_ms": 500, "num_turns": 1,
        "result": "```json\n" + json.dumps(answer, indent=2) + "\n```",
        "usage": {"input_tokens": 6000, "output_tokens": 900,
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
    }).encode("utf-8"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "_fake-claude":
        sys.exit(fake_claude(sys.argv[2:]))
    sys.exit(main())
