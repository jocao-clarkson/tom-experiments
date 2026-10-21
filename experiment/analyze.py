"""Metrics, paired comparisons, and judge-vs-human agreement for a judged run-id.

    py experiment\\analyze.py summary --run-id pilot
    py experiment\\analyze.py labels  --run-id pilot --n 60
    py experiment\\analyze.py kappa   --run-id pilot

Outputs go to experiment/results/<run-id>/analysis/:
  runs.csv          one row per judged run
  summary.csv       one row per technique
  comparisons.csv   paired-by-case differences with bootstrap 95% CI and sign-flip p
  predictions.csv   PTU prediction accuracy per lens and peer
  labels.csv        pairs for a human to label (labels command; never filled in here)
  labels_key.csv    what each label row is and what the judge said (keep it closed while labelling)
  kappa.json        judge-vs-human agreement (kappa command)
"""

import argparse
import csv
import itertools
import json
import random
import statistics
import sys
from pathlib import Path

from run import RESULTS, TECHNIQUES

COMPARISONS = [
    ("ptu", "debate"),
    ("ptu", "second-round"),
    ("debate", "second-round"),
    ("second-round", "none"),
    ("debate", "none"),
    ("ptu", "none"),
]
COMPARE_METRICS = [
    "contradictions",
    "tension_resolved_rate",
    "recall",
    "precision",
    "flip_rate",
    "out_of_lane_rate",
    "tokens_total",
    "wall_seconds",
]
SUMMARY_METRICS = [
    "contradictions",
    "n_findings",
    "tensions_resolved",
    "tension_resolved_rate",
    "recall",
    "precision",
    "flip_rate",
    "pred_recall",
    "pred_precision",
    "out_of_lane_rate",
    "tokens_total",
    "judge_tokens",
    "wall_seconds",
]
BOOTSTRAP = 10000
PERMUTATIONS = 20000


# --------------------------------------------------------------------------
# Per-run metrics


def ratio(a, b):
    return a / b if b else None


def mean(values):
    vals = [v for v in values if v is not None]
    return statistics.fmean(vals) if vals else None


def run_metrics(rdir):
    meta = json.loads((rdir / "meta.json").read_text(encoding="utf-8"))
    judged = json.loads((rdir / "judge.json").read_text(encoding="utf-8"))
    final_in = judged["inputs"]["final"]
    final_out = judged["outputs"]["final"]["parsed"]

    refs = {(lens, f["id"]) for lens, fs in final_in["findings"].items() for f in fs}
    defect_ids = {d["id"] for d in final_in["defects"]}
    tension_ids = {t["id"] for t in final_in["tensions"]}

    judged_findings = {}
    for f in final_out["findings"]:
        key = (f.get("lens"), f.get("id"))
        if key in refs:
            judged_findings[key] = f
    matched = [k for k, f in judged_findings.items() if set(f.get("matches_defects") or []) & defect_ids]
    found = set()
    for f in judged_findings.values():
        found |= set(f.get("matches_defects") or []) & defect_ids
    out_of_lane = sum(1 for f in judged_findings.values() if f.get("out_of_lane"))

    pairs = contradiction_pairs(final_out, refs)
    resolved = sum(
        1 for t in final_out["tensions"] if t.get("id") in tension_ids and t.get("status") == "reconciled"
    )

    row = {
        "run_id": meta["run_id"],
        "case": meta["case"],
        "technique": meta["technique"],
        "rep": meta["rep"],
        "case_type": judged.get("case_type"),
        "lens_source": judged.get("lens_source"),
        "n_findings": len(refs),
        "contradictions": len(pairs),
        "tensions_total": len(tension_ids),
        "tensions_resolved": resolved,
        "tension_resolved_rate": ratio(resolved, len(tension_ids)),
        "defects_total": len(defect_ids),
        "defects_found": len(found),
        "recall": ratio(len(found), len(defect_ids)),
        "precision": ratio(len(matched), len(refs)),
        "out_of_lane": out_of_lane,
        "out_of_lane_rate": ratio(out_of_lane, len(refs)),
        "flip_rate": None,
        "pred_recall": None,
        "pred_precision": None,
        # A round-2 session started from a separate round 1; count that too, so
        # every technique is costed end to end.
        "tokens_total": (meta.get("usage") or {}).get("total_tokens", 0)
        + (meta.get("round1_usage") or {}).get("total_tokens", 0),
        "judge_tokens": sum((c.get("usage") or {}).get("total_tokens", 0) for c in judged["outputs"].values()),
        "wall_seconds": (meta.get("wall_seconds") or 0) + (meta.get("round1_wall_seconds") or 0),
        "lens_calls": meta.get("lens_calls"),
    }

    if "flips" in judged["outputs"]:
        entries = {}
        for m in judged["outputs"]["flips"]["parsed"]["round1_matches"]:
            if m.get("defect") in defect_ids:
                entries[(m.get("lens"), m.get("id"), m.get("defect"))] = m.get("round2_status")
        flips = sum(1 for s in entries.values() if s in ("dropped", "reversed"))
        row["flip_rate"] = ratio(flips, len(entries))

    pred_rows = []
    if "predictions" in judged["outputs"]:
        for pr in judged["outputs"]["predictions"]["parsed"]["pairs"]:
            preds = pr.get("predictions") or []
            peer_f = pr.get("peer_findings") or []
            pred_rows.append({
                "lens": pr.get("lens"),
                "peer": pr.get("peer"),
                "peer_findings_predicted": ratio(sum(1 for f in peer_f if f.get("predicted")), len(peer_f)),
                "predictions_came_true": ratio(sum(1 for p in preds if p.get("came_true")), len(preds)),
            })
        row["pred_recall"] = mean(r["peer_findings_predicted"] for r in pred_rows)
        row["pred_precision"] = mean(r["predictions_came_true"] for r in pred_rows)
    return row, pred_rows, judged


def contradiction_pairs(final_out, refs):
    pairs = set()
    for c in final_out["contradictions"]:
        a = ((c.get("a") or {}).get("lens"), (c.get("a") or {}).get("id"))
        b = ((c.get("b") or {}).get("lens"), (c.get("b") or {}).get("id"))
        if a in refs and b in refs and a[0] != b[0]:
            pairs.add(tuple(sorted([a, b])))
    return pairs


def load(run_id):
    root = RESULTS / run_id / "runs"
    if not root.exists():
        sys.exit(f"no results for run-id {run_id!r}")
    rows, preds, failed = [], [], []
    for meta_path in sorted(root.glob("*/*/rep*/meta.json")):
        rdir = meta_path.parent
        if not (rdir / "done.json").exists():
            failed.append(json.loads(meta_path.read_text(encoding="utf-8")))
            continue
        if not (rdir / "judge.json").exists():
            continue
        row, pred_rows, _ = run_metrics(rdir)
        rows.append(row)
        for p in pred_rows:
            preds.append({**{k: row[k] for k in ("case", "rep")}, **p})
    return rows, preds, failed


# --------------------------------------------------------------------------
# Statistics


def paired_stats(diffs, seed=0):
    n = len(diffs)
    obs = statistics.fmean(diffs)
    rng = random.Random(seed)
    boots = sorted(statistics.fmean(rng.choices(diffs, k=n)) for _ in range(BOOTSTRAP))
    lo = boots[int(0.025 * BOOTSTRAP)]
    hi = boots[int(0.975 * BOOTSTRAP) - 1]
    if all(d == 0 for d in diffs):
        p = 1.0
    elif n <= 16:
        count = total = 0
        for signs in itertools.product((1, -1), repeat=n):
            total += 1
            if abs(statistics.fmean(s * d for s, d in zip(signs, diffs))) >= abs(obs) - 1e-12:
                count += 1
        p = count / total
    else:
        count = sum(
            1
            for _ in range(PERMUTATIONS)
            if abs(statistics.fmean(d if rng.random() < 0.5 else -d for d in diffs)) >= abs(obs) - 1e-12
        )
        p = (count + 1) / (PERMUTATIONS + 1)
    return obs, lo, hi, p


def case_means(rows, technique, metric):
    by_case = {}
    for r in rows:
        if r["technique"] == technique and r[metric] is not None:
            by_case.setdefault(r["case"], []).append(r[metric])
    return {c: statistics.fmean(v) for c, v in by_case.items()}


def comparisons(rows):
    out = []
    for a, b in COMPARISONS:
        for metric in COMPARE_METRICS:
            if metric == "flip_rate" and "none" in (a, b):
                continue  # one-round control has no round 2
            ma, mb = case_means(rows, a, metric), case_means(rows, b, metric)
            cases = sorted(set(ma) & set(mb))
            row = {"a": a, "b": b, "metric": metric, "n_cases": len(cases)}
            if len(cases) >= 2:
                diffs = [ma[c] - mb[c] for c in cases]
                obs, lo, hi, p = paired_stats(diffs)
                row.update({
                    "mean_a": statistics.fmean(ma[c] for c in cases),
                    "mean_b": statistics.fmean(mb[c] for c in cases),
                    "mean_diff_a_minus_b": obs,
                    "ci95_low": lo,
                    "ci95_high": hi,
                    "p_sign_flip": p,
                })
            out.append(row)
    return out


# --------------------------------------------------------------------------
# Output


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(v) for k, v in r.items()})


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else ("" if v is None else v)


def cmd_summary(args):
    rows, preds, failed = load(args.run_id)
    if not rows:
        sys.exit("no judged runs yet; run judge.py first")
    out = RESULTS / args.run_id / "analysis"
    write_csv(out / "runs.csv", rows)

    summary = []
    for t in TECHNIQUES:
        tr = [r for r in rows if r["technique"] == t]
        if not tr and not any(f["technique"] == t for f in failed):
            continue
        s = {
            "technique": t,
            "n_judged": len(tr),
            "n_failed": sum(1 for f in failed if f["technique"] == t),
            "n_cases": len({r["case"] for r in tr}),
        }
        for m in SUMMARY_METRICS:
            s[m] = mean(r[m] for r in tr)
        summary.append(s)
    write_csv(out / "summary.csv", summary)
    write_csv(out / "comparisons.csv", comparisons(rows),
              ["a", "b", "metric", "n_cases", "mean_a", "mean_b", "mean_diff_a_minus_b",
               "ci95_low", "ci95_high", "p_sign_flip"])

    if preds:
        agg = {}
        for p in preds:
            agg.setdefault((p["lens"], p["peer"]), []).append(p)
        write_csv(out / "predictions.csv", [
            {"lens": l, "peer": pe, "n": len(v),
             "peer_findings_predicted": mean(x["peer_findings_predicted"] for x in v),
             "predictions_came_true": mean(x["predictions_came_true"] for x in v)}
            for (l, pe), v in sorted(agg.items())
        ])

    cols = ["technique", "n_judged", "n_failed", "contradictions", "tension_resolved_rate", "recall",
            "precision", "flip_rate", "pred_recall", "out_of_lane_rate", "tokens_total", "wall_seconds"]
    print(f"run-id {args.run_id}: {len(rows)} judged runs, {len(failed)} failed runs")
    print_table(summary, cols)
    print(f"\nwrote {out}")


def print_table(rows, cols):
    cells = [[c for c in cols]] + [[str(fmt(r.get(c))) or "-" for c in cols] for r in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(cols))]
    for row in cells:
        print("  ".join(v.rjust(w) for v, w in zip(row, widths)))


def finding_text(f):
    if "text" in f:
        return f["text"]
    parts = [f.get("title", "")]
    for k in ("evidence", "detail", "recommendation"):
        if f.get(k):
            parts.append(f"{k}: {f[k]}")
    return " | ".join(p for p in parts if p)


def cmd_labels(args):
    out = RESULTS / args.run_id / "analysis"
    labels_path = out / "labels.csv"
    if labels_path.exists() and not args.force:
        sys.exit(f"{labels_path} already exists (it may hold your labels). Use --force to overwrite.")
    root = RESULTS / args.run_id / "runs"
    positives, negatives = [], []
    for jpath in sorted(root.glob("*/*/rep*/judge.json")):
        rdir = jpath.parent
        if not (rdir / "done.json").exists():
            continue
        judged = json.loads(jpath.read_text(encoding="utf-8"))
        findings = {(l, f["id"]): f for l, fs in judged["inputs"]["final"]["findings"].items() for f in fs}
        pairs = contradiction_pairs(judged["outputs"]["final"]["parsed"], set(findings))
        for a, b in itertools.combinations(sorted(findings), 2):
            if a[0] == b[0]:
                continue
            item = (judged["run"], a, b, findings[a], findings[b])
            (positives if (a, b) in pairs else negatives).append(item)

    rng = random.Random(args.seed)
    n_pos = min(len(positives), args.n // 2)
    n_neg = min(len(negatives), args.n - n_pos)
    sample = [(x, 1) for x in rng.sample(positives, n_pos)] + [(x, 0) for x in rng.sample(negatives, n_neg)]
    rng.shuffle(sample)

    label_rows, key_rows = [], []
    for i, ((run, a, b, fa, fb), judge_label) in enumerate(sample, 1):
        if rng.random() < 0.5:  # random side, so lens order gives nothing away
            a, b, fa, fb = b, a, fb, fa
        lid = f"L{i:03d}"
        label_rows.append({"label_id": lid, "finding_a_lens": a[0], "finding_a": finding_text(fa),
                           "finding_b_lens": b[0], "finding_b": finding_text(fb), "human_label": ""})
        key_rows.append({"label_id": lid, **run, "a_id": a[1], "b_id": b[1], "judge_label": judge_label})
    write_csv(labels_path, label_rows,
              ["label_id", "finding_a_lens", "finding_a", "finding_b_lens", "finding_b", "human_label"])
    write_csv(out / "labels_key.csv", key_rows,
              ["label_id", "run_id", "case", "technique", "rep", "a_id", "b_id", "judge_label"])
    print(f"wrote {len(label_rows)} pairs ({n_pos} the judge called contradictions, {n_neg} it didn't) to {labels_path}")
    print("Fill human_label with 1 (the two recommendations can't both be followed) or 0 (they can).")
    print("Don't open labels_key.csv until you're done; it shows the judge's answers.")


def cmd_kappa(args):
    out = RESULTS / args.run_id / "analysis"
    with (out / "labels.csv").open(encoding="utf-8-sig", newline="") as f:
        human = {r["label_id"]: r["human_label"].strip().lower() for r in csv.DictReader(f)}
    with (out / "labels_key.csv").open(encoding="utf-8", newline="") as f:
        judge = {r["label_id"]: int(r["judge_label"]) for r in csv.DictReader(f)}
    yes, no = {"1", "yes", "y", "true"}, {"0", "no", "n", "false"}
    pairs = []
    for lid, h in human.items():
        if h in yes | no and lid in judge:
            pairs.append((1 if h in yes else 0, judge[lid]))
    if not pairs:
        sys.exit("no human labels filled in yet (human_label must be 1 or 0)")
    n = len(pairs)
    agree = sum(1 for h, j in pairs if h == j) / n
    ph, pj = sum(h for h, _ in pairs) / n, sum(j for _, j in pairs) / n
    expected = ph * pj + (1 - ph) * (1 - pj)
    kappa = (agree - expected) / (1 - expected) if expected < 1 else None
    table = {f"human{h}_judge{j}": sum(1 for x in pairs if x == (h, j)) for h in (0, 1) for j in (0, 1)}
    result = {"n_labelled": n, "n_unlabelled": len(human) - n, "percent_agreement": agree,
              "cohens_kappa": kappa, "confusion": table}
    (out / "kappa.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("summary", help="write runs, summary, comparisons and predictions CSVs")
    s.add_argument("--run-id", required=True)
    l = sub.add_parser("labels", help="export a random sample of judged pairs for human labelling")
    l.add_argument("--run-id", required=True)
    l.add_argument("--n", type=int, default=60)
    l.add_argument("--seed", type=int, default=1)
    l.add_argument("--force", action="store_true", help="overwrite an existing labels.csv")
    k = sub.add_parser("kappa", help="judge-vs-human agreement from your filled-in labels.csv")
    k.add_argument("--run-id", required=True)
    args = p.parse_args(argv)
    {"summary": cmd_summary, "labels": cmd_labels, "kappa": cmd_kappa}[args.command](args)


if __name__ == "__main__":
    main()
