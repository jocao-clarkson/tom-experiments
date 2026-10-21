# Experiment: PTU vs debate in the plan-phase gate

**Question.** In the plan phase of `/validation-orchestrator`, does predict-then-update (PTU) reduce contradictions between the five lenses more than debate does, without making the lenses miss real problems?

| Technique | Arm | Lens rounds | What round 2 adds |
| --- | --- | --- | --- |
| `none` | C0 (control) | 1 | nothing; today's gate |
| `second-round` | C1 (control) | 2 | every lens sees all round-1 findings and re-reviews |
| `debate` | D | 2 | defend or concede own conflicting findings, rebut peers |
| `ptu` | PTU | 2 | round 1 also predicts peers; round 2 responds to its surprises |

The technique instructions live in `.claude/skills/validation-orchestrator/techniques/`. Running `/validation-orchestrator` without `technique=` behaves as it did before.

Each run is a fresh headless `claude -p` session in a fresh temp folder, so no context carries over between runs. The folder holds the case's fixture at the root, `specs/feature/spec.md` and `plan.md`, and a copy of this repo's `.claude/`. `ground_truth.json` is never copied into it. Runs are shuffled so cases and techniques are interleaved.

With `technique=` set, the orchestrator stops after the last lens round. It doesn't verify, merge, or write a report, because the judge scores the lens outputs directly from the transcript. A run counts as done when every expected lens output was captured.

**Shared round 1.** For each two-round technique, round 2 runs as its own session, which starts from a finished round 1. `run.py` writes that round 1 into the workspace as `specs/feature/round1-findings.md`, copied from the earlier transcript, plus `round1-briefs.md` with each lens's round-1 brief, and passes `round1=` to the skill. `second-round` and `debate` both start from the `none` run's round 1, because all three use the same standard round-1 brief. PTU's round 1 asks for predictions, so it runs on its own (`stop=round1`) in `ptu/rep<k>/round1/`. This saves two of the three standard round-1 fan-outs per case. It also makes the comparison paired: any difference between `none`, `second-round` and `debate` comes from round 2 alone. A failed round 2 is retried without redoing round 1. `--single-session` runs both rounds in one session, as the first pilots did. Don't mix the two modes in one run-id.

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

- **The cases aren't too easy.** If the `none` arm already has recall near 1, close to 0 contradictions, and most tensions reconciled, the cases can't separate the techniques. Make them harder first.
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

To add reps, run the same commands with `--reps 2`, then `--reps 3`, under the same run-id. Rep 1 is already done, so only the new rep runs.

**Resuming.** Run the same command again. Runs with a `done.json` are skipped, and failed runs are retried. A finished round 1 is never redone. `run.py` stops at the first failure that looks like a usage limit, and after 3 failures in a row of any kind. Wait for the limit to reset, then run the same command again. `judge.py` resumes the same way. A session cut off by the limit wastes what it used, so start big batches right after your limit resets.

`--workers 2` runs two orchestrators at once, and each starts five lenses in parallel, so up to 10 Sonnet subagents run at a time. Use `--workers 1` if you hit limits quickly.

## Usage per run

With shared round 1 (the default):

| Technique | Lens calls it runs (Sonnet) | Orchestrator sessions | Judge calls (Sonnet) |
| --- | --- | --- | --- |
| `none` | 5 (round 1, shared) | 1 | 1 (final) |
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

A round-2 run's `meta.json` has `round1_usage` and `round1_wall_seconds` from the round 1 it started from. `analyze.py` adds them to `tokens_total` and `wall_seconds`, so every technique is costed end to end, even though the `none` round 1 is only paid for once. To estimate the full run's usage, add up `tokens_total` for the `none` run plus the round-2 session tokens for each technique from the pilot, then multiply by 30 per rep.

## Metrics

The judge runs as separate `claude -p --model sonnet` sessions in an empty folder, with the fixed prompts in `prompts/`.

- **final** (every run) sees only the final findings, as parsed `FINDINGS` sections, plus the seeded defects and tensions. It never sees the technique name or any summary, prediction, debate, or surprise block.
- **flips** (C1, D, PTU) sees the round-1 and round-2 findings, with the same blinding.
- **predictions** (PTU only) sees the predictions and the peers' round-1 findings. It can't be blinded, because the predictions are PTU's own output.

| Metric | Definition |
| --- | --- |
| `contradictions` (main) | Pairs of final findings from different lenses whose recommendations can't both be followed |
| `tension_resolved_rate` | Seeded tensions the judge marks `reconciled` ÷ seeded tensions |
| `recall` | Seeded defects matched by at least one final finding ÷ seeded defects |
| `precision` | Final findings that match a seeded defect ÷ all final findings. Strict: real but unseeded issues count against it. |
| `flip_rate` | Round-1 findings that matched a defect and were then `dropped` or `reversed` in round 2 ÷ those matched findings |
| `pred_recall`, `pred_precision` | PTU: share of each peer's findings that were predicted; share of predictions that came true. Per lens and peer in `predictions.csv`. |
| `out_of_lane_rate` | Final findings whose main subject is another lens's area ÷ all final findings |
| `tokens_total`, `wall_seconds` | From the `claude -p` result |

`comparisons.csv` pairs runs by case (averaging reps within a case) for PTU vs D, PTU vs C1, D vs C1, and each vs C0. Each row has the mean difference (a − b), a bootstrap 95% CI over cases, and a paired sign-flip permutation p-value. The p-value is exact when there are 16 or fewer cases, and uses 20,000 random permutations otherwise.

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

## Layout

```
experiment/
  cases/case-NN/        fixture/, spec.md, plan.md, ground_truth.json (AUTHORING.md: how they were written)
  prompts/              judge-final.md, judge-flips.md, judge-predictions.md
  run.py                runs the gate; also the fake claude for --mock
  judge.py              judges finished runs
  analyze.py            summary / labels / kappa
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
