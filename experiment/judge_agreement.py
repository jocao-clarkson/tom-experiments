"""How consistent is the judge? Judge the same finished runs several times and
compare the answers.

Each repeat is a fresh judge session on identical inputs, saved as
<run>/agreement/<task>.r<k>.json, so an interrupted batch resumes. Nothing
here touches judge.json.

    py experiment\\judge_agreement.py --run-id pilot --task contradictions --reps 3
    py experiment\\judge_agreement.py --run-id pilot --task final --reps 2 --limit 8
"""

import argparse
import itertools
import json
import sys

import judge
import run as runner
from run import RESULTS


def judge_repeats(rdir, task, reps, args):
    meta = json.loads((rdir / "meta.json").read_text(encoding="utf-8"))
    rounds, _ = judge.load_rounds(rdir, meta["technique"])
    if rounds is None:
        return None
    gt_path = rdir / "ground_truth.json"
    if not gt_path.exists():
        gt_path = runner.CASES / meta["case"] / "ground_truth.json"
    data = judge.build_inputs(rounds, json.loads(gt_path.read_text(encoding="utf-8")), meta["technique"])[task]
    out = rdir / "agreement"
    out.mkdir(exist_ok=True)
    answers = []
    for k in range(1, reps + 1):
        path = out / f"{task}.r{k}.json"
        if not path.exists():
            path.write_text(json.dumps(judge.call_judge(task, data, args), indent=2, ensure_ascii=False),
                            encoding="utf-8")
        answers.append(json.loads(path.read_text(encoding="utf-8"))["parsed"])
    return answers


def pair_set(answer):
    pairs = set()
    for c in answer.get("contradictions", []):
        a = ((c.get("a") or {}).get("lens"), (c.get("a") or {}).get("id"))
        b = ((c.get("b") or {}).get("lens"), (c.get("b") or {}).get("id"))
        if a[0] != b[0]:
            pairs.add(frozenset([a, b]))
    return pairs


def report_contradictions(per_run):
    jaccards, counts = [], []
    in_all = in_majority = union_total = 0
    for answers in per_run.values():
        sets = [pair_set(a) for a in answers]
        counts.append([len(s) for s in sets])
        union = set().union(*sets)
        union_total += len(union)
        in_all += sum(all(p in s for s in sets) for p in union)
        in_majority += sum(sum(p in s for s in sets) * 2 > len(sets) for p in union)
        for x, y in itertools.combinations(sets, 2):
            if x | y:
                jaccards.append(len(x & y) / len(x | y))
    totals = [sum(c[k] for c in counts) for k in range(len(counts[0]))]
    print(f"pairs flagged per repeat (all runs): {totals}")
    print(f"distinct pairs: {union_total}; in every repeat: {in_all}; in a majority: {in_majority}")
    if jaccards:
        print(f"mean pairwise Jaccard over runs with any pair: {sum(jaccards) / len(jaccards):.2f} (n={len(jaccards)})")
    same_count = sum(len(set(c)) == 1 for c in counts)
    print(f"runs whose contradiction count is the same in every repeat: {same_count}/{len(counts)}")


def report_final(per_run):
    agree = total = t_agree = t_total = 0
    for answers in per_run.values():
        matches = [{(f.get("lens"), f.get("id")): tuple(sorted(f.get("matches_defects") or []))
                    for f in a.get("findings", [])} for a in answers]
        for key in set.intersection(*(set(m) for m in matches)):
            total += 1
            agree += len({m[key] for m in matches}) == 1
        tensions = [{t.get("id"): t.get("status") for t in a.get("tensions", [])} for a in answers]
        for tid in set.intersection(*(set(t) for t in tensions)):
            t_total += 1
            t_agree += len({t[tid] for t in tensions}) == 1
    if total:
        print(f"defect matches identical across repeats: {agree}/{total} findings ({agree / total:.0%})")
    if t_total:
        print(f"tension status identical across repeats: {t_agree}/{t_total} tensions ({t_agree / t_total:.0%})")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", required=True)
    p.add_argument("--task", default="contradictions", choices=["contradictions", "final"])
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--limit", type=int, default=None, help="only the first N finished runs")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--mock", action="store_true", help="fake claude -p; spends no usage")
    p.add_argument("--timeout", type=int, default=900)
    args = p.parse_args(argv)

    root = RESULTS / args.run_id / "runs"
    done = sorted(d.parent for d in root.glob("*/*/rep*/done.json"))[: args.limit]
    per_run = {}
    for i, rdir in enumerate(done, 1):
        name = "/".join(rdir.relative_to(root).parts)
        try:
            answers = judge_repeats(rdir, args.task, args.reps, args)
        except judge.UsageLimit:
            print(f"[{i}/{len(done)}] {name}: usage limit; re-run the same command to resume")
            break
        if answers is not None:
            per_run[name] = answers
            print(f"[{i}/{len(done)}] {name}: ok", flush=True)
    if not per_run:
        sys.exit("nothing to compare")
    print(f"\n{args.task}, {len(per_run)} runs x {args.reps} repeats")
    (report_contradictions if args.task == "contradictions" else report_final)(per_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
