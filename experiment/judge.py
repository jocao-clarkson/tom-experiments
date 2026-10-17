"""Judge finished runs with a fixed Sonnet judge (claude -p, one fresh session per call).

For every finished run in experiment/results/<run-id>/ without a judge.json:

- final        (all techniques): contradictions, seeded tensions, defect matches,
               out-of-lane. Blind: the judge sees only the final findings and the
               ground truth, with no technique name and no predictions, debate or
               surprise blocks.
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
import shutil
import sys
import tempfile
import threading
from pathlib import Path

import run as runner
from run import CASES, LENSES, RESULTS, ROUNDS

PROMPTS = Path(__file__).resolve().parent / "prompts"
INSTRUCTION = "Follow the judge instructions and the JUDGE TASK in the input, and reply with only the JSON object."
HEADER = re.compile(r"^[A-Z][A-Z \-]*:")
REQUIRED = {
    "final": ["findings", "contradictions", "tensions"],
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
    """Lens outputs per round: the transcript copy when complete, else raw.json."""
    lens_path = rdir / "lens_outputs.json"
    if lens_path.exists():
        lens = json.loads(lens_path.read_text(encoding="utf-8"))
        if runner.complete(lens.get("rounds", {}), technique):
            return lens["rounds"], "transcript"
    raw_path = rdir / "raw.json"
    if raw_path.exists():
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if runner.complete(raw.get("rounds", {}), technique):
            return raw["rounds"], "raw.json"
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
        }
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
        shutil.rmtree(cwd, ignore_errors=True)


# --------------------------------------------------------------------------
# Main


def judge_run(rdir, args):
    meta = json.loads((rdir / "meta.json").read_text(encoding="utf-8"))
    technique = meta["technique"]
    rounds, source = load_rounds(rdir, technique)
    if rounds is None:
        raise RuntimeError("lens outputs incomplete in both transcript and raw.json")
    gt = json.loads((CASES / meta["case"] / "ground_truth.json").read_text(encoding="utf-8"))
    inputs = build_inputs(rounds, gt, technique)
    outputs = {task: call_judge(task, data, args) for task, data in inputs.items()}
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
    p.add_argument("--timeout", type=int, default=900)
    args = p.parse_args(argv)

    root = RESULTS / args.run_id / "runs"
    if not root.exists():
        sys.exit(f"no results for run-id {args.run_id!r}")
    config = json.loads((RESULTS / args.run_id / "config.json").read_text(encoding="utf-8"))
    if config.get("mock") and not args.mock:
        sys.exit("these runs are mock runs; judge them with --mock")
    if args.mock and not config.get("mock"):
        sys.exit("these are real runs; don't judge them with --mock")

    done = sorted(d.parent for d in root.glob("*/*/rep*/done.json"))
    todo = [d for d in done if args.rejudge or not (d / "judge.json").exists()]
    print(f"{len(done)} finished runs, {len(done) - len(todo)} already judged, {len(todo)} to judge"
          + (" [mock]" if args.mock else ""))

    lock = threading.Lock()
    counts = {"ok": 0, "failed": 0}

    def work(rdir):
        name = "/".join(rdir.relative_to(root).parts)
        try:
            judge_run(rdir, args)
            status = "ok"
        except Exception as e:  # keep going; the run stays unjudged and is retried next time
            (rdir / "judge_error.txt").write_text(str(e), encoding="utf-8")
            status = f"FAILED ({e})"
        with lock:
            counts["ok" if status == "ok" else "failed"] += 1
            print(f"[{counts['ok'] + counts['failed']}/{len(todo)}] {name}: {status}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(work, todo))
    print(f"done: {counts['ok']} judged, {counts['failed']} failed")
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
