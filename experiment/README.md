# Experiment: PTU vs debate in the plan-phase gate

**Question.** In the plan phase of `/validation-orchestrator`, does predict-then-update (PTU) get the five lenses to reconcile conflicting concerns more often than debate does, without making the lenses miss real problems? (The question first asked about reducing contradictions; see "Primary metric" under Metrics for why it changed.)

| Technique | Arm | Lens rounds | What round 2 adds |
| --- | --- | --- | --- |
| `baseline` | C0 (control) | 1 | nothing; today's gate |
| `second-round` | C1 (control) | 2 | every lens sees all round-1 findings and re-reviews |
| `debate` | D | 2 | defend or concede own conflicting findings, rebut peers |
| `ptu` | PTU | 2 | round 1 also predicts peers; round 2 responds to its surprises |

The technique instructions live in `.claude/skills/validation-orchestrator/techniques/`. Running `/validation-orchestrator` without `technique=` behaves as it did before.

Each run is a fresh headless `claude -p` session in a fresh temp folder, so no context carries over between runs. The folder holds the case's fixture at the root, `specs/feature/spec.md` and `plan.md`, and a copy of this repo's `.claude/`. `ground_truth.json` is never copied into it. Runs are shuffled so cases and techniques are interleaved.

With `technique=` set, the orchestrator stops after the last lens round. It doesn't verify, merge, or write a report, because the judge scores the lens outputs directly from the transcript. A run counts as done when every expected lens output was captured.

**Shared round 1.** For each two-round technique, round 2 runs as its own session, which starts from a finished round 1. `run.py` writes that round 1 into the workspace as `specs/feature/round1-findings.md`, copied from the earlier transcript, plus `round1-briefs.md` with each lens's round-1 brief, and passes `round1=` to the skill. `second-round` and `debate` both start from the `baseline` run's round 1, because all three use the same standard round-1 brief. PTU's round 1 asks for predictions, so it runs on its own (`stop=round1`) in `ptu/rep<k>/round1/`. This saves two of the three standard round-1 fan-outs per case. It also makes the comparison paired: any difference between `baseline`, `second-round` and `debate` comes from round 2 alone. A failed round 2 is retried without redoing round 1. `--single-session` runs both rounds in one session, as the first pilots did. Don't mix the two modes in one run-id.

**Orchestrator settings.** `--orchestrator-model` defaults to `opus`, because debate gets blocked with a Sonnet orchestrator. `--orchestrator-effort` defaults to `medium`. It sets `claude -p --effort` for the orchestrator session. Lenses are still Sonnet, set by their agent files. Check on the pilot whether the effort setting also reaches the lenses. If it does, it applies equally to every technique, but it changes what the lenses produce, so keep it the same for the whole experiment.

## Setup (Windows Command Prompt)

```bat
cd %USERPROFILE%\Desktop\tom-experiments
git checkout feature/experiment-setup
py --version
claude --version
```

You need Python 3.10 or newer and Claude Code logged in with your subscription. The scripts use only the standard library, so nothing needs installing. A virtual environment is optional:

```bat
py -m venv .venv
.venv\Scripts\activate
```

**Make sure `claude -p` uses your subscription, not an API key.** If `ANTHROPIC_API_KEY` is set, Claude Code uses it instead, and the runs are billed to the API. Check, and clear it for this window if it prints anything other than `%ANTHROPIC_API_KEY%`:

```bat
echo %ANTHROPIC_API_KEY%
set ANTHROPIC_API_KEY=
```

Run every command below from the repo root.

## 1. Mock check (no usage)

`--mock` replaces `claude -p` with a fake that writes the same files and stream format, so the whole pipeline runs for free:

```bat
py experiment\run.py --run-id mock-check --cases case-01,case-02 --mock
py experiment\judge.py --run-id mock-check --mock
py experiment\analyze.py summary --run-id mock-check
```

The numbers are random. The point is that every stage runs. A run-id stays mock or real for good: the scripts refuse to mix them.

## 2. Pilot: 6 cases x 4 techniques x 1 rep = 24 runs

`--cases pilot` picks 5 tension cases and 1 clean case, deterministically. It reads only the `type` field of each `ground_truth.json`.

```bat
py experiment\run.py --run-id pilot --cases pilot --reps 1 --workers 2
py experiment\judge.py --run-id pilot --workers 2
py experiment\analyze.py summary --run-id pilot
```

Check before the full run:

- **The cases aren't too easy.** If the `baseline` arm already reconciles most tensions, the cases can't separate the techniques on the primary metric. Aim for at most half reconciled (see `cases/AUTHORING.md`, "Difficulty"). Recall near 1 is fine: it's a guardrail and only has to show a drop.
- **Token accounting.** In any `meta.json`, check `usage.models`. If it lists only the orchestrator model, `claude -p` isn't reporting lens (subagent) tokens, and `tokens_total` undercounts.
- **Every lens output was captured.** In `lens_outputs.json`, `complete` should be `true` and `problems` empty. The judge reads lens outputs only from there.
- **A few lens outputs and judge outputs by hand,** to confirm the techniques ran as written.

## 3. Full run: 30 cases x 4 techniques, one rep at a time

Start with 1 rep (120 runs). Analyze it, and add reps only if the techniques are close enough that run-to-run noise could change the conclusion:

```bat
py experiment\run.py --run-id full --cases all --reps 1 --workers 2
py experiment\judge.py --run-id full --workers 2
py experiment\analyze.py summary --run-id full
```

**Run `full`, rep 1, reuses the calibration baselines.** The `baseline` runs for the 24 tension cases were copied from `calib-v2` (case-21 and case-28 from `calib-v3`). They used the same case versions (`case_hash` matches), the same Opus orchestrator at medium effort, and the same skill. Their `meta.json` has `copied_from`. They were re-judged with the current judge. They ran a few hours before the rest of rep 1 instead of interleaved with it, so a small drift between them and the other arms can't be ruled out. The 6 clean-case baselines and all other arms ran in `full` itself.

To add reps, run the same commands with `--reps 2`, then `--reps 3`, under the same run-id. Rep 1 is already done, so only the new rep runs.

**Resuming.** Run the same command again. Runs with a `done.json` are skipped, and failed runs are retried. A finished round 1 is never redone. `run.py` stops at the first failure that looks like a usage limit, and after 3 failures in a row of any kind. Wait for the limit to reset, then run the same command again. `judge.py` resumes the same way. A session cut off by the limit wastes what it used, so start big batches right after your limit resets.

**Unattended.** Add `--wait-for-reset` to `run.py` or `judge.py` to resume on its own. After a usage limit, it sleeps until the limit's reset time (read from claude's output, plus 2 minutes), then runs the same command again. If the reset time isn't in the output, it checks again every 20 minutes. It gives up once the reset falls more than 24 hours after it started. Pass a number of hours to change that, as in `--wait-for-reset 72`. A weekly limit usually lies outside that window, so it ends the loop. Keep the PC awake, for example with `powercfg /change standby-timeout-ac 0`, because sleep pauses the run. For the whole pipeline:

```bat
py experiment\run.py --run-id full --cases all --workers 1 --wait-for-reset 72 && py experiment\judge.py --run-id full --wait-for-reset 72 && py experiment\analyze.py summary --run-id full
```

`--workers 2` runs two orchestrators at once, and each starts five lenses in parallel, so up to 10 Sonnet subagents run at a time. Use `--workers 1` if you hit limits quickly.

## Results: run `full`, rep 1

120 runs (30 cases x 4 techniques), all judged, none failed. Tensions were judged with majority-of-3. Tension metrics cover the 24 tension cases. Comparisons are paired by case, with a bootstrap 95% CI and a sign-flip p (see [Metrics](#metrics)). The CSVs are in `results/full/analysis/`, which is git-ignored.

| Technique | `tension_resolved_rate` | `tension_clash_rate` | `contradictions` | `recall` | `precision` | `n_findings` | `words_per_finding` | `tokens_total` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `baseline` | 0.465 | 0.132 | 1.87 | 0.990 | 0.548 | 39.8 | 124 | 548k |
| `second-round` | **0.618** | 0.035 | 0.47 | 0.995 | 0.531 | 44.6 | 121 | 1,053k |
| `debate` | 0.604 | 0.063 | 0.50 | 0.995 | 0.548 | 40.6 | 112 | 1,051k |
| `ptu` | 0.590 | **0.000** | **0.13** | 0.990 | 0.516 | 46.3 | 124 | 1,148k |

Primary metric, paired differences:

| Comparison | Diff | 95% CI | p | p (Holm) |
| --- | --- | --- | --- | --- |
| `second-round` − `baseline` | +0.153 | [+0.056, +0.264] | 0.019 | 0.093 |
| `debate` − `baseline` | +0.139 | [+0.056, +0.222] | 0.008 | **0.048** |
| `ptu` − `baseline` | +0.125 | [+0.014, +0.250] | 0.093 | 0.37 |
| `ptu` − `debate` | −0.014 | [−0.097, +0.083] | 1.0 | 1.0 |
| `ptu` − `second-round` | −0.028 | [−0.125, +0.056] | 0.77 | 1.0 |
| `debate` − `second-round` | −0.014 | [−0.083, +0.056] | 1.0 | 1.0 |

`p (Holm)` corrects for the 6 comparisons on each metric (`p_holm` in `comparisons.csv`).

What it shows:

- **A second round helps, and the format of that round doesn't detectably matter.** All three two-round techniques reconcile 12–15 points more tensions than `baseline`. After Holm correction only `debate` − `baseline` stays below 0.05 (0.048), so the effect of a second round is likely but rests on one rep. PTU, debate and plain second-round can't be told apart: the PTU vs debate CI spans about ±9 points. Most of the gain seems to come from lenses reading each other's round-1 findings.
- **PTU never left a clash.** `tension_clash_rate` was 0 for PTU, against 0.063 for debate (diff −0.063, CI [−0.125, −0.014], p = 0.12, Holm 0.48) and 0.132 for `baseline` (p = 0.007, Holm 0.040). PTU also had the fewest contradictions (0.13 per run vs 0.50 for debate, p = 0.08). The direction is consistent, but the p-values from one rep fall short of firm.
- **PTU's guardrails are slightly worse.** Compared with debate, PTU has lower precision (−0.032, p = 0.01), about 6 more findings per run (p < 0.001) that are 12 words longer each, about 9% more tokens (p = 0.01), and 73 s more wall time per run. Debate has the shortest findings of any arm.
- **Recall is at the ceiling** (0.99–0.995 for every arm), so defect detection doesn't separate the techniques.
- **PTU predictions:** a lens predicted about 46% of each peer's round-1 findings (`pred_recall` 0.463), and over 80% of its predictions came true. Architecture and consistency findings were the hardest to predict (35–40%), and tests findings the easiest (about 58–63%).

Blinded re-judge (`judge.py --blind`, `analysis-blind/`): tension statuses re-judged after the findings were rewritten to remove references to peers, rounds and other findings.

| Technique | Same status as original | Gained `reconciled` | Lost `reconciled` | `tension_resolved_rate` | `tension_clash_rate` |
| --- | --- | --- | --- | --- | --- |
| `baseline` | 63/70 | 4 | 3 | 0.479 (was 0.465) | 0.104 (was 0.132) |
| `second-round` | 67/70 | 1 | 2 | 0.604 (was 0.618) | 0.035 (same) |
| `debate` | 68/70 | 1 | 1 | 0.604 (same) | 0.076 (was 0.063) |
| `ptu` | 67/70 | 0 | 2 | 0.563 (was 0.590) | 0.014 (was 0) |

| Comparison (blinded) | `tension_resolved_rate` diff | 95% CI | p (Holm) |
| --- | --- | --- | --- |
| `second-round` − `baseline` | +0.125 | [+0.056, +0.208] | 0.045 |
| `debate` − `baseline` | +0.125 | [+0.042, +0.222] | 0.15 |
| `ptu` − `baseline` | +0.083 | [−0.056, +0.222] | 1.0 |
| `ptu` − `debate` | −0.042 | [−0.125, +0.042] | 1.0 |

- **No sign the leak biased the judge.** Blinding changed 3–7% of statuses in the round-2 arms and 10% in `baseline`, which had nothing to blind. That is about the judge's own run-to-run disagreement (89% agreement between two majority-of-3 scores), so the changes look like judge noise, not a correction of bias.
- **The overall picture holds:** a second round adds about 12 points of reconciliation, and the three round-2 techniques can't be told apart.
- **Which single comparison is significant isn't stable.** Originally `debate` − `baseline` passed Holm and `second-round` − `baseline` didn't. Blinded, it's the other way round. Treat "a second round helps" as likely, not established.
- **PTU's clash result weakens.** PTU now has 1 clash (0.014). Against `baseline` it's p = 0.03 uncorrected but 0.18 after Holm, and against `debate` 0.60 after Holm. PTU's reconciled rate fell slightly, and it's no longer clearly above `baseline`.
Qualitative read ([notes/full-rep1-qualitative.md](notes/full-rep1-qualitative.md)):

- **The round-2 differences look like noise.** 28 of 70 tensions are reconciled by all four techniques and 19 by none. The round-2 techniques each win only 2–7 tensions the others miss, scattered across cases and lens pairs. Round 2 helps most where architecture is one side of the tension. Risk+tests tensions are never reconciled by any technique.
- **Second-round and debate share a mechanism.** A lens that held a conflicting fix sees the peer's finding and adopts it. Debate rarely changes minds: its stances are 311 "defend" to 45 "concede", and the debate block isn't judged.
- **PTU avoids clashes by writing peer-aware findings, mostly without reconciling.** Of the 11 tensions where baseline or debate clashed, PTU reconciled 6 and left 5 compatible. Its conflict predictions didn't single out those tensions (they came true in 4 of 11, against 33 of 59 elsewhere). Instead, 54% of PTU's final findings cite another lens's finding, against about 20% for second-round and debate. PTU findings carry the peer's caveat, so they can't clash, but they often don't commit to the full fix. PTU also lost 3 tensions that baseline had reconciled, against 1 each for the others, because it spread the needed facts across findings that cross-reference each other.
Caveats specific to this run:

- **One rep and 24 tension cases.** Differences of a few points are within noise.
- **The primary metric was chosen after the pilot** (see [Primary metric](#primary-metric-tension-reconciliation)).
- **The tension-case baselines came from calibration** (see the reuse note above).
- **For `ptu` − `baseline`, the CI excludes 0 but p = 0.09 (Holm 0.37).** The bootstrap and the permutation test disagree at the margin, so treat that effect as suggestive.
- **The original judge wasn't blind to technique in practice.** Round-2 findings cite peers and round 1, and PTU does so most. The blinded re-judge above found no sign this biased the statuses.
- **Judge noise is the same size as the round-2 gaps.** 6–12 tensions per technique were decided 2–1, and near-identical findings sometimes got different statuses (case-25 T3).
- **The tension judge has been checked against a second model, not a human.** On every tension in the 35 sampled runs, Opus agreed with the blinded Sonnet judge on reconciled-or-not for 95% (kappa 0.90), with no lean toward any technique (see [Cross-model check](#cross-model-check-in-place-of-human-labels)). Both models use the same checklist, so a flaw in the checklist would get past this check.
- **One stray prediction row.** One PTU run has a single lens-consistency prediction about itself (n = 1 in `predictions.csv`). It doesn't affect the per-run metrics.
- **One slow outlier.** `case-06/debate` took 847 s against a typical 70–90 s, but finished normally.

Cost: the 126 orchestrator sessions took four 5-hour usage windows on a Max plan, and the judging (about 7 Sonnet calls per run) took about three more. Before adding reps, weigh that cost against the size of the gap you're trying to resolve. At ±9 points, three reps are unlikely to separate PTU from debate on the primary metric. They would firm up the clash-rate difference. A human check of judge labels (`analyze.py labels` / `kappa`) costs no usage.

## Usage per run

With shared round 1 (the default):

| Technique | Lens calls it runs (Sonnet) | Orchestrator sessions | Judge calls (Sonnet) |
| --- | --- | --- | --- |
| `baseline` | 5 (round 1, shared) | 1 | 1 (final) |
| `second-round` | 5 (round 2) | 1 | 2 (final, flips) |
| `debate` | 5 (round 2) | 1 | 2 (final, flips) |
| `ptu` | 10 (own round 1, round 2) | 2 | 3 (final, flips, predictions) |

| Batch | Runs | Lens calls | Orchestrator sessions | Judge calls |
| --- | --- | --- | --- | --- |
| Pilot | 24 | 150 | 30 | 48 |
| Full, 1 rep | 120 | 750 | 150 | 240 |
| Full, 3 reps | 360 | 2,250 | 450 | 720 |

With `--single-session`, every two-round technique makes 10 lens calls in 1 session: 35 lens calls per case and rep instead of 25.

Round-2 lens calls are larger than round-1 calls, because each round-2 lens reads all five round-1 outputs from `specs/feature/round1-findings.md`. The round-2 briefs give the file's path instead of pasting the outputs: pasting them into all five briefs made Opus retype about 50-65k tokens per run. With shared round 1, `run.py` writes the file. With `--single-session`, the orchestrator writes it, `run.py` copies it into the run folder, and `meta.json` → `round1_file.verbatim` records per lens whether it matches the round-1 output in the transcript. In a smoke test, Opus copied one sentence wrong. PTU round-1 calls are slightly larger too, because they include predictions.

A round-2 run's `meta.json` has `round1_usage` and `round1_wall_seconds` from the round 1 it started from. `analyze.py` adds them to `tokens_total` and `wall_seconds`, so every technique is costed end to end, even though the `baseline` round 1 is only paid for once. To estimate the full run's usage, add up `tokens_total` for the `baseline` run plus the round-2 session tokens for each technique from the pilot, then multiply by 30 per rep.

## Metrics

The judge runs as separate `claude -p --model sonnet` sessions in an empty folder, with the fixed prompts in `prompts/`.

- **final** (every run) sees only the final findings, as parsed `FINDINGS` sections, plus the seeded defects and tensions. It never sees the technique name or any summary, prediction, debate, or surprise block. It matches findings to defects and checks out-of-lane.
- **tensions** (tension cases) sees the final findings and the seeded tensions, with the same blinding. For each tension it works through a fixed checklist: list each side's findings, look for one finding that names both concerns, recommends a fix satisfying both, and relies on the fact the reconciliation needs, then check that no other finding clashes with it. It's judged `--tension-votes` times (default 3), and each tension takes the majority status. Ties, possible only with an even count, go against `reconciled`.
- **contradictions** (every run) sees only the final findings, without even the ground truth. It groups findings by what their recommendation changes, then checks cross-lens pairs within each group.
- **flips** (C1, D, PTU) sees the round-1 and round-2 findings, with the same blinding.
- **predictions** (PTU only) sees the predictions and the peers' round-1 findings. It can't be blinded, because the predictions are PTU's own output.
- **blinded tensions** (`judge.py --blind`, tension cases) re-judges tensions after a Sonnet call rewrites the final findings to drop references to other lenses' findings, peers, rounds, predictions and debate, keeping the technical content (`prompts/judge-blind.md`). All four techniques are rewritten the same way, baseline included. The rewrite is cached in `blind_findings.json` and the statuses go to `judge_blind.json`; `judge.json` is untouched. `analyze.py summary --run-id full --blind` scores tensions from it into `analysis-blind/`, plus `blind_agreement.csv`, which compares each tension's blinded and original status. It exists because round-2 findings revealed their technique (see the qualitative notes). On one PTU run, it cut findings with such references from 35 of 47 to 4, and those 4 only cite the same lens's other findings, as baseline findings also do.

### Primary metric: tension reconciliation

**`tension_resolved_rate` is the primary metric,** and everything else is secondary. This was decided after the pilot and calibration and before the full run. Any write-up should say so.

The original primary metric was `contradictions`. The pilot and calibration showed that one-round lenses rarely make recommendations that clash outright. Instead, each lens fixes its own side of a tension and nobody combines the fixes. Contradiction counts sat near zero in every arm, which leaves nothing for a technique to reduce. Judged twice with identical instructions inside the `final` task, the pilot's contradictions also didn't overlap at all: 9 pairs each, none shared. With their own task they agree much better (Jaccard 0.60 across 3 repeats), but they stay rare. Reconciliation captures the failure that does happen. `baseline` reconciled 1 of 7 tensions in the calibration cases that followed the authoring rules, which leaves room for the techniques to differ.

Its limits: it only covers the tensions we seeded, and its judge has to see the ground truth. A technique could also inflate it with long findings that try to cover every concern. Report it next to the guardrails, which are `precision`, `n_findings`, `words_per_finding` and `out_of_lane_rate`. A rise in reconciliation that comes with longer, less precise findings isn't a clean win. Check the judge's consistency on tension statuses with `judge_agreement.py --task final` before relying on small differences. On 5 calibration runs judged 3 times each, the reconciled-or-not call agreed for 9 of 11 tensions, the full status for 8 of 11, and the defect matches for 97% of findings. The disagreements were borderline cases where one finding came close to the combined fix. On the full calibration (24 cases, 70 tensions, judged 4 times inside `final`), only 46 of 70 agreed. That's too noisy for the primary metric, so tension statuses moved to their own checklist task with majority-of-3. Measure that score's agreement with `judge_agreement.py --task tensions --reps 6 --majority 3`, which compares two independent majority-of-3 scores.

Tension statuses: `reconciled` means one finding gives a fix that satisfies both concerns, and no finding still pushes a conflicting side. `unreconciled_conflict` means both sides are raised and their recommendations clash. `unreconciled_compatible` means both sides are raised and could both be followed, but nobody combined them. `one_side_only` and `neither` cover the rest.

| Metric | Definition |
| --- | --- |
| `tension_resolved_rate` (primary) | Seeded tensions the judge marks `reconciled` ÷ seeded tensions |
| `tension_clash_rate` | Seeded tensions marked `unreconciled_conflict` ÷ seeded tensions; `tension_uncombined_rate` is the same for `unreconciled_compatible` |
| `contradictions` | Pairs of final findings from different lenses whose recommendations can't both be followed, from the `contradictions` task |
| `words_per_finding` | Mean words per final finding (guardrail) |
| `recall` | Seeded defects matched by at least one final finding ÷ seeded defects |
| `precision` | Final findings that match a seeded defect ÷ all final findings. Strict: real but unseeded issues count against it. |
| `flip_rate` | Round-1 findings that matched a defect and were then `dropped` or `reversed` in round 2 ÷ those matched findings |
| `pred_recall`, `pred_precision` | PTU: share of each peer's findings that were predicted; share of predictions that came true. Per lens and peer in `predictions.csv`. |
| `out_of_lane_rate` | Final findings whose main subject is another lens's area ÷ all final findings |
| `tokens_total`, `wall_seconds` | From the `claude -p` result |

`comparisons.csv` pairs runs by case (averaging reps within a case) for PTU vs D, PTU vs C1, D vs C1, and each vs C0. Each row has the mean difference (a − b), a bootstrap 95% CI over cases, and a paired sign-flip permutation p-value. The p-value is exact when there are 16 or fewer cases, and uses 20,000 random permutations otherwise. `p_holm` applies a Holm correction across the 6 comparisons within each metric. Use it for any claim about the primary metric.

## Checking the judge against a human

```bat
py experiment\analyze.py labels --run-id pilot --n 60
```

This writes `results\pilot\analysis\labels.csv`. Half the rows are pairs the judge called contradictions, and half are cross-lens pairs it didn't. The rows are shuffled, and neither the technique nor the judge's answer is shown. Including non-contradiction pairs is what makes kappa meaningful: if every row were a judged contradiction, kappa couldn't be computed.

Fill in `human_label` with `1` if the two recommendations can't both be followed, or `0` if they can. Don't open `labels_key.csv` until you're done. Then run:

```bat
py experiment\analyze.py kappa --run-id pilot
```

`labels` won't overwrite an existing `labels.csv` unless you pass `--force`.

### Tension statuses (the primary metric)

```bat
py experiment\analyze.py labels --run-id full --task tensions --blind
```

This samples 40 (run, tension) items, 10 per technique: 5 the judge called `reconciled` and 5 it didn't. Each item gets its own file in `results\full\analysis\tension_items\`, with the tension, its two fixes and the reconciled fix, all the run's final findings, and the status definitions the judge uses. The technique isn't shown. For each item, read its file and fill `human_status` in `tension_labels.csv` with one of `reconciled`, `unreconciled_conflict`, `unreconciled_compatible`, `one_side_only` or `neither`. Optionally put the reconciling finding's id in `human_reconciling`. Don't open `tension_labels_key.csv` until you're done. Then run:

```bat
py experiment\analyze.py kappa --run-id full --task tensions
```

It writes `tension_kappa.json`, with agreement and Cohen's kappa for the full status and for reconciled-or-not, reconciled agreement per technique, and the confusion counts. Each item has about 40 findings, so budget a few minutes per item. Use `--n 24` for a smaller sample.

Two limits:
- **The 50/50 sampling inflates `reconciled`** relative to the run, so read the agreement as the judge's accuracy on each kind of call, not as an estimate of the reconciled rate.
- **Use `--blind`.** It shows the blinded findings from `judge.py --blind` and scores you against the blinded judge. Without it, round-2 findings that mention peers or round 1 can reveal that an item isn't `baseline`.

### Cross-model check (in place of human labels)

The human labels turned out to be too slow to fill in, so a second model labelled the same items instead:

```bat
py experiment\cross_judge.py --run-id full --workers 3 --wait-for-reset
```

Opus judges the 35 runs behind the 40 sampled items. It gets the same blinded inputs, prompt and majority-of-3 as the Sonnet judge in `judge_blind.json`, and the script compares the two. It writes `tension_cross_opus.csv` and `tension_cross_opus.json`, from 105 Opus calls. It finished without hitting a usage limit.

| | n | status agreement | status kappa | reconciled agreement | reconciled kappa |
|---|---|---|---|---|---|
| 40 sampled items | 40 | 85% | 0.72 | 93% | 0.85 |
| every tension in those 35 runs | 103 | 89% | 0.81 | 95% | 0.90 |

What it shows:
- **The two models agree closely on the primary metric.** Reconciled-or-not agrees about as well as two Sonnet majority-of-3 scores agree with each other (89% full status). So the score doesn't hinge on a quirk of Sonnet.
- **Opus is slightly more lenient.** Of the 5 reconciled disagreements among the 103 tensions, Opus credited `reconciled` in 4: 2 in `baseline`, 1 in `ptu` and 1 in `second-round`. Sonnet credited it in 1, in `ptu`. Neither model favours a technique. If Opus were the judge, the `baseline` rate would rise slightly, which would shrink the round-2 advantage a little rather than grow it.
- **The other disagreements are `unreconciled_compatible` vs `unreconciled_conflict`.** There were 5 of them, and they don't affect the primary metric.

Its limit: both models apply the same checklist to the same inputs, so they would share any error in the checklist itself, such as how strictly it reads "on its own". This check rules out Sonnet-specific errors; it isn't a human check.

## Layout

```
experiment/
  cases/case-NN/        fixture/, spec.md, plan.md, ground_truth.json (AUTHORING.md: how they were written)
  prompts/              judge-final.md, judge-flips.md, judge-predictions.md
  run.py                runs the gate; also the fake claude for --mock
  judge.py              judges finished runs
  analyze.py            summary / labels / kappa
  cross_judge.py        second-model check of the blinded tension judge
  results/<run-id>/     git-ignored
    config.json
    runs/<case>/<technique>/rep<k>/
      transcript.jsonl  lens_outputs.json  meta.json  done.json  judge.json
    analysis/           runs.csv  summary.csv  comparisons.csv  predictions.csv  labels.csv  labels_key.csv  kappa.json
```

## Caveats

- The cases and ground truth were written by Claude subagents, from the same model family as the lenses, so the seeded problems may be ones Claude finds easily. The pilot partly checks this. Reading a few cases yourself is the better check.
- Each run allows the orchestrator `Skill, Agent, Read, Grep, Glob, Bash, Write` through `--allowedTools`, scoped to its temp folder. The tests lens may run Bash there.
- A lens that conceded in debate, or updated in PTU, may still mention the peer in its finding text. The judge's blinding can't hide that.
