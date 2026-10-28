"""Cross-model check of the blinded tension judge: a second model (Opus by
default) judges the tensions of the runs sampled by
`analyze.py labels --task tensions --blind`, and its statuses are compared
with the Sonnet judge's in judge_blind.json.

It sends the second model exactly the inputs the Sonnet judge saw (the
blinded findings and the seeded tensions, from judge_blind.json) with the same
prompt, judged --votes times with the same majority rule. Each answer is cached
as <run>/cross/tensions.<model>.<prompt hash>.r<k>.json, so an interrupted batch
resumes. Nothing here touches judge_blind.json or the human label files.

    py experiment\\cross_judge.py --run-id full
    py experiment\\cross_judge.py --run-id full --workers 3 --wait-for-reset

Writes analysis/tension_cross_<model>.csv (one row per sampled item) and
tension_cross_<model>.json (agreement and Cohen's kappa, on the 40 sampled
items and on every tension in the sampled runs).
"""

import argparse
import concurrent.futures
import csv
import hashlib
import json
import sys
import threading
import time

import judge
import run as runner
from analyze import TENSION_STATUSES, kappa_stats, write_csv
from run import RESULTS


def cross_votes(rdir, args):
    blind = json.loads((rdir / "judge_blind.json").read_text(encoding="utf-8"))
    data = blind["inputs"]["tensions"]
    out = rdir / "cross"
    out.mkdir(exist_ok=True)
    # Keyed by model and prompt, so answers from another model or an edited prompt never mix.
    version = hashlib.sha256((judge.PROMPTS / "judge-tensions.md").read_bytes()).hexdigest()[:8]
    tag = f"{args.model}{'-mock' if args.mock else ''}"
    votes = []
    for k in range(1, args.votes + 1):
        path = out / f"tensions.{tag}.{version}.r{k}.json"
        if not path.exists():
            path.write_text(json.dumps(judge.call_judge("tensions", data, args), indent=2, ensure_ascii=False),
                            encoding="utf-8")
        votes.append(json.loads(path.read_text(encoding="utf-8")))
    cross = {t["id"]: t["status"] for t in judge.majority_tensions(votes)["tensions"]}
    base = {t["id"]: t["status"] for t in blind["outputs"]["tensions"]["parsed"]["tensions"]}
    return base, cross


def summarize(pairs):
    agree, kappa = kappa_stats(pairs)
    bin_agree, bin_kappa = kappa_stats([(a == "reconciled", b == "reconciled") for a, b in pairs])
    return {
        "n": len(pairs),
        "status_agreement": agree,
        "status_kappa": kappa,
        "reconciled_agreement": bin_agree,
        "reconciled_kappa": bin_kappa,
        "confusion": {f"sonnet_{a}__cross_{b}": pairs.count((a, b))
                      for a in TENSION_STATUSES for b in TENSION_STATUSES if (a, b) in pairs},
    }


def judge_all(runs, args):
    """Judge every sampled run. Returns ({run: (base, cross)}, the UsageLimit that stopped it or None)."""
    results = {}
    lock = threading.Lock()
    stop = threading.Event()
    state = {"n": 0, "limit": None}

    def work(item):
        name, rdir = item
        if stop.is_set():
            return
        try:
            base_cross = cross_votes(rdir, args)
            status = "ok"
        except judge.UsageLimit as e:
            # The rest would fail the same way; leave them for the next pass.
            state["limit"] = e
            stop.set()
            base_cross, status = None, "usage limit"
        except Exception as e:  # keep going; it's retried next time
            base_cross, status = None, f"FAILED ({e})"
        with lock:
            if base_cross is not None:
                results[name] = base_cross
            state["n"] += 1
            print(f"[{state['n']}/{len(runs)}] {name}: {status}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(work, sorted(runs.items())))
    return results, state["limit"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", required=True)
    p.add_argument("--model", default="opus")
    p.add_argument("--votes", type=int, default=3, help="judgings per run, reduced by majority (default 3)")
    p.add_argument("--workers", type=int, default=1, help="runs judged in parallel")
    p.add_argument("--mock", action="store_true", help="fake claude -p; spends no usage")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--wait-for-reset", type=float, nargs="?", const=24, default=None, metavar="HOURS",
                   help="after a usage limit, wait for it to reset and resume; give up after HOURS (default 24)")
    args = p.parse_args(argv)

    out = RESULTS / args.run_id / "analysis"
    key_path = out / "tension_labels_key.csv"
    if not key_path.exists():
        sys.exit(f"no {key_path}; run analyze.py labels --task tensions --blind first")
    with key_path.open(encoding="utf-8", newline="") as f:
        key = list(csv.DictReader(f))
    if any(r.get("judge_file") != "judge_blind.json" for r in key):
        sys.exit("the sampled items weren't made with --blind; re-run analyze.py labels --task tensions --blind")
    root = RESULTS / args.run_id / "runs"
    runs = {f"{r['case']}/{r['technique']}/rep{r['rep']}": root / r["case"] / r["technique"] / f"rep{r['rep']}"
            for r in key}
    print(f"{len(key)} sampled items in {len(runs)} runs; {args.model} x {args.votes} votes"
          + (" [mock]" if args.mock else ""))

    deadline = time.time() + 3600 * args.wait_for_reset if args.wait_for_reset else None
    while True:
        results, limit = judge_all(runs, args)
        if not limit or len(results) == len(runs):
            break
        if not (deadline and runner.wait_for_reset(limit.resets_at, deadline)):
            sys.exit("stopped at a usage limit; re-run the same command to resume")
    missing = sorted(set(runs) - set(results))
    if missing:
        sys.exit(f"{len(missing)} runs failed ({', '.join(missing)}); re-run the same command to retry them")

    rows, sampled = [], []
    for r in key:
        base, cross = results[f"{r['case']}/{r['technique']}/rep{r['rep']}"]
        b, c = base.get(r["tension"]), cross.get(r["tension"])
        rows.append({"label_id": r["label_id"], "case": r["case"], "technique": r["technique"], "rep": r["rep"],
                     "tension": r["tension"], "sonnet_status": b, "cross_status": c})
        if b in TENSION_STATUSES and c in TENSION_STATUSES:
            sampled.append((b, c))
    every = [(base[t], cross[t]) for base, cross in results.values() for t in base
             if base[t] in TENSION_STATUSES and cross.get(t) in TENSION_STATUSES]
    by_tech = {}
    for row in rows:
        if row["sonnet_status"] in TENSION_STATUSES and row["cross_status"] in TENSION_STATUSES:
            by_tech.setdefault(row["technique"], []).append(
                (row["sonnet_status"] == "reconciled") == (row["cross_status"] == "reconciled"))
    result = {
        "cross_model": args.model,
        "votes": args.votes,
        "mock": args.mock,
        "sampled_items": summarize(sampled),
        "all_tensions_in_sampled_runs": summarize(every),
        "reconciled_agreement_by_technique": {t: sum(v) / len(v) for t, v in sorted(by_tech.items())},
        "reconciled_rate": {
            "sonnet": sum(a == "reconciled" for a, _ in every) / len(every),
            "cross": sum(b == "reconciled" for _, b in every) / len(every),
        },
    }
    tag = f"{args.model}{'-mock' if args.mock else ''}"
    write_csv(out / f"tension_cross_{tag}.csv", rows,
              ["label_id", "case", "technique", "rep", "tension", "sonnet_status", "cross_status"])
    (out / f"tension_cross_{tag}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
