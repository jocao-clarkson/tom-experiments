"""Judge finished runs with a fixed Sonnet judge (claude -p, one fresh session per call).

For every finished run in experiment/results/<run-id>/ without a judge.json:

- final        (all techniques): defect matches, out-of-lane. Blind: the judge
               sees only the final findings and the ground truth, with no technique
               name and no predictions, debate or surprise blocks.
- tensions     (tension cases): status of each seeded tension, from a step-by-step
               checklist. Judged --tension-votes times (default 3); each tension
               takes the majority status. Same blinding.
- contradictions (all techniques): pairs of final findings from different lenses
               that can't both be followed, found topic by topic. The judge sees
               only the final findings, not even the ground truth.
- flips        (second-round, debate, ptu): round-1 findings that matched a defect
               and what happened to them in round 2. Same blinding.
- predictions  (ptu only): how well each lens predicted each peer.

    py experiment\\judge.py --run-id pilot
    py experiment\\judge.py --run-id smoke --mock
"""

import argparse
import concurrent.futures
import datetime
import json
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

import run as runner
from run import CASES, LENSES, RESULTS, ROUNDS

PROMPTS = Path(__file__).resolve().parent / "prompts"
INSTRUCTION = "Follow the judge instructions and the JUDGE TASK in the input, and reply with only the JSON object."
HEADER = re.compile(r"^[A-Z][A-Z \-]*:")
REQUIRED = {
    "final": ["findings"],
    "tensions": ["tensions"],
    "contradictions": ["topics", "contradictions"],
    "flips": ["round1_matches"],
    "predictions": ["pairs"],
}


# --------------------------------------------------------------------------
# Parsing lens output


def strip_fences(text):
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("```"))


def section(text, name):
    """Body of a top-level `NAME:` section, up to the next top-level header."""
    lines = strip_fences(text).splitlines()
    body, inside = [], False
    for line in lines:
        if not inside:
            if line.startswith(f"{name}:"):
                inside = True
                rest = line[len(name) + 1:].strip()
                if rest:
                    body.append(rest)
            continue
        if HEADER.match(line):
            break
        body.append(line)
    return "\n".join(body).strip() if inside else None


def parse_findings(text):
    """Findings as dicts. Only the FINDINGS section is read, so SUMMARY,
    TRACEABILITY, PREDICTIONS, DEBATE and SURPRISE RESPONSES never reach the judge."""
    body = section(text or "", "FINDINGS")
    if body is None or body.lower().startswith("none"):
        return []
    findings, cur, key = [], None, None
    for line in body.splitlines():
        m = re.match(r"^\s*-\s+id:\s*(.+)$", line)
        if m:
            cur = {"id": m.group(1).strip()}
            findings.append(cur)
            key = "id"
            continue
        if cur is None:
            continue
        m = re.match(r"^\s+(\w+):\s*(.*)$", line)
        if m and m.group(1) in ("severity", "fix_in", "title", "evidence", "detail", "recommendation"):
            key = m.group(1)
            cur[key] = m.group(2).strip()
        elif line.strip() and key:
            cur[key] = (cur.get(key, "") + " " + line.strip()).strip()
    if not findings and body.strip():
        return [{"id": "UNPARSED", "text": body.strip()}]
    return findings


def load_rounds(rdir, technique):
    """Lens outputs per round, as extracted from the transcript, if complete."""
    lens_path = rdir / "lens_outputs.json"
    if lens_path.exists():
        lens = json.loads(lens_path.read_text(encoding="utf-8"))
        if runner.complete(lens.get("rounds", {}), technique):
            return lens["rounds"], "transcript"
    return None, None


# --------------------------------------------------------------------------
# Judge inputs


def build_inputs(rounds, gt, technique):
    final = str(ROUNDS[technique])
    defects = gt.get("defects", [])
    tensions = gt.get("tensions", [])
    tasks = {
        "final": {
            "defects": defects,
            "tensions": tensions,
            "findings": {l: parse_findings(rounds[final].get(l, "")) for l in LENSES},
        },
        "contradictions": {
            "findings": {l: parse_findings(rounds[final].get(l, "")) for l in LENSES},
        },
    }
    if tensions:
        tasks["tensions"] = {
            "tensions": tensions,
            "findings": {l: parse_findings(rounds[final].get(l, "")) for l in LENSES},
        }
    if ROUNDS[technique] == 2:
        tasks["flips"] = {
            "defects": defects,
            "round1": {l: parse_findings(rounds["1"].get(l, "")) for l in LENSES},
            "round2": {l: parse_findings(rounds["2"].get(l, "")) for l in LENSES},
        }
    if technique == "ptu":
        r1 = {l: parse_findings(rounds["1"].get(l, "")) for l in LENSES}
        tasks["predictions"] = {
            "lenses": {
                l: {
                    "predictions": section(rounds["1"].get(l, ""), "PREDICTIONS") or "",
                    "peer_findings": {p: r1[p] for p in LENSES if p != l},
                }
                for l in LENSES
            }
        }
    return tasks


def judge_prompt(task, data):
    instructions = (PROMPTS / f"judge-{task}.md").read_text(encoding="utf-8")
    return (
        f"{instructions}\n\nJUDGE TASK: {task}\n<<<INPUT_JSON\n"
        f"{json.dumps(data, indent=2, ensure_ascii=False)}\nINPUT_JSON>>>\n"
    )


def parse_answer(text, task):
    m = re.search(r"```json\s*(\{.*\})\s*```", text, re.S)
    candidate = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    obj = json.loads(candidate)
    missing = [k for k in REQUIRED[task] if not isinstance(obj.get(k), list)]
    if missing:
        raise ValueError(f"judge answer missing list keys: {missing}")
    return obj


class UsageLimit(Exception):
    def __init__(self, resets_at):
        super().__init__("usage limit")
        self.resets_at = resets_at


def call_judge(task, data, args):
    stdin = judge_prompt(task, data)
    cwd = Path(tempfile.mkdtemp(prefix="vjudge-"))  # empty: nothing to read
    try:
        last_error = None
        for _ in range(2):  # one retry on an unparseable answer
            code, out, err, wall, timed_out = runner.call_claude(
                ["-p", INSTRUCTION, "--output-format", "json", "--model", args.model],
                cwd, args.mock, stdin_text=stdin, timeout=args.timeout,
            )
            result = runner.result_event(out)
            if result is None:
                try:
                    result = json.loads(out)
                except json.JSONDecodeError:
                    result = None
            if timed_out or code != 0 or not result or result.get("is_error"):
                result_text = (result or {}).get("result") or ""
                if runner.usage_limited(out, result_text, err):
                    raise UsageLimit(runner.reset_time(out + result_text + err))
                last_error = f"exit={code} timed_out={timed_out} {err.strip()[:300]}"
                continue
            try:
                parsed = parse_answer(result.get("result", ""), task)
            except (ValueError, json.JSONDecodeError) as e:
                last_error = f"unparseable answer: {e}"
                continue
            return {
                "parsed": parsed,
                "response": result.get("result", ""),
                "usage": runner.usage_summary(result),
                "wall_seconds": round(wall, 1),
            }
        raise RuntimeError(last_error)
    finally:
        runner.remove_tree(cwd)


# --------------------------------------------------------------------------
# Main


# Ties (only possible with an even vote count) go against `reconciled`, the
# primary metric, so a split jury never inflates it.
TIE_ORDER = ["unreconciled_conflict", "unreconciled_compatible", "one_side_only", "neither", "reconciled"]


def majority_tensions(votes):
    """Per tension, the most common status across votes, with the vote split."""
    by_id = {}
    for vote in votes:
        for t in vote["parsed"]["tensions"]:
            by_id.setdefault(t.get("id"), []).append(t)
    result = []
    for tid, ts in by_id.items():
        statuses = [t.get("status") for t in ts]
        top = max(statuses.count(s) for s in set(statuses))
        status = next(s for s in TIE_ORDER + statuses if statuses.count(s) == top)
        pick = next(t for t in ts if t.get("status") == status)
        result.append({**pick, "status": status, "votes": statuses})
    return {"tensions": result}


def judge_tensions(data, args):
    votes = [call_judge("tensions", data, args) for _ in range(max(1, args.tension_votes))]
    usage = {}
    for v in votes:
        for k, n in (v.get("usage") or {}).items():
            if isinstance(n, int):
                usage[k] = usage.get(k, 0) + n
    return {"parsed": majority_tensions(votes), "votes": votes, "usage": usage,
            "wall_seconds": round(sum(v.get("wall_seconds") or 0 for v in votes), 1)}


def judge_run(rdir, args):
    meta = json.loads((rdir / "meta.json").read_text(encoding="utf-8"))
    technique = meta["technique"]
    rounds, source = load_rounds(rdir, technique)
    if rounds is None:
        raise RuntimeError("lens outputs incomplete in the transcript")
    # The ground truth the run was made against; older runs have no copy.
    gt_path = rdir / "ground_truth.json"
    if not gt_path.exists():
        gt_path = CASES / meta["case"] / "ground_truth.json"
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    inputs = build_inputs(rounds, gt, technique)
    # With --tasks, keep the other tasks' answers from the existing judge.json.
    old = {}
    if args.tasks and (rdir / "judge.json").exists():
        old = json.loads((rdir / "judge.json").read_text(encoding="utf-8"))["outputs"]
    outputs = {
        task: old[task] if task in old and task not in args.tasks
        else judge_tensions(data, args) if task == "tensions"
        else call_judge(task, data, args)
        for task, data in inputs.items()
    }
    record = {
        "run": {k: meta[k] for k in ("run_id", "case", "technique", "rep")},
        "case_type": gt.get("type"),
        "lens_source": source,
        "judge_model": args.model,
        "mock": args.mock,
        "judged_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "inputs": inputs,
        "outputs": outputs,
    }
    (rdir / "judge.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    (rdir / "judge_error.txt").unlink(missing_ok=True)
    return record


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", required=True)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--model", default="sonnet")
    p.add_argument("--mock", action="store_true", help="fake claude -p; spends no usage")
    p.add_argument("--rejudge", action="store_true", help="judge again even if judge.json exists")
    p.add_argument("--tasks", type=lambda s: [t.strip() for t in s.split(",") if t.strip()], default=None,
                   help="with --rejudge, rerun only these tasks (comma list of final, flips, predictions)")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--tension-votes", type=int, default=3,
                   help="judge each run's tensions this many times and take the majority (default 3)")
    p.add_argument("--wait-for-reset", type=float, nargs="?", const=24, default=None, metavar="HOURS",
                   help="after a usage limit, wait for it to reset and resume; give up after HOURS (default 24)")
    args = p.parse_args(argv)
    if args.tasks and (not args.rejudge or set(args.tasks) - set(REQUIRED)):
        sys.exit("--tasks needs --rejudge and names from: " + ", ".join(REQUIRED))

    root = RESULTS / args.run_id / "runs"
    if not root.exists():
        sys.exit(f"no results for run-id {args.run_id!r}")
    config = json.loads((RESULTS / args.run_id / "config.json").read_text(encoding="utf-8"))
    if config.get("mock") and not args.mock:
        sys.exit("these runs are mock runs; judge them with --mock")
    if args.mock and not config.get("mock"):
        sys.exit("these are real runs; don't judge them with --mock")

    deadline = time.time() + 3600 * args.wait_for_reset if args.wait_for_reset else None
    while True:
        rc, limit = judge_batch(root, args)
        if not (deadline and limit):
            return rc
        if not runner.wait_for_reset(limit.resets_at, deadline):
            return rc


def judge_batch(root, args):
    """Judge every unjudged finished run once. Returns (exit code, the
    UsageLimit that stopped it or None)."""
    done = sorted(d.parent for d in root.glob("*/*/rep*/done.json"))
    todo = [d for d in done if args.rejudge or not (d / "judge.json").exists()]
    print(f"{len(done)} finished runs, {len(done) - len(todo)} already judged, {len(todo)} to judge"
          + (" [mock]" if args.mock else ""))

    lock = threading.Lock()
    stop = threading.Event()
    counts = {"ok": 0, "failed": 0, "limit": None}

    def work(rdir):
        if stop.is_set():
            return
        name = "/".join(rdir.relative_to(root).parts)
        try:
            judge_run(rdir, args)
            status = "ok"
        except UsageLimit as e:
            # The rest would fail the same way; leave them for the next pass.
            counts["limit"] = e
            stop.set()
            status = "FAILED (usage limit)"
        except Exception as e:  # keep going; the run stays unjudged and is retried next time
            (rdir / "judge_error.txt").write_text(str(e), encoding="utf-8")
            status = f"FAILED ({e})"
        with lock:
            counts["ok" if status == "ok" else "failed"] += 1
            print(f"[{counts['ok'] + counts['failed']}/{len(todo)}] {name}: {status}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(work, todo))
    print(f"done: {counts['ok']} judged, {counts['failed']} failed")
    if counts["limit"]:
        print("stopped at a usage limit; re-run the same command to resume.")
    return (0 if counts["failed"] == 0 else 1), counts["limit"]


if __name__ == "__main__":
    sys.exit(main())
