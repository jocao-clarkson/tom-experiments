---
name: validation-orchestrator
description: Validation gate for spec-driven development. Use after a plan is written (before implementation) to validate the plan against the spec, and again after implementation to validate the code against the spec and plan. Fans out parallel lens subagents (coverage, consistency, architecture, risk, tests), verifies and merges their findings, and returns a PASS / PASS_WITH_NOTES / FAIL verdict.
argument-hint: "[phase=plan|implementation] [spec=<path>] [plan=<path>] [base=<ref>] [technique=none|second-round|debate|ptu]"
allowed-tools: Agent, Read, Grep, Glob, Bash, Write
---

You are acting as the validation orchestrator for a spec-driven workflow:

```
spec -> plan -> [/validation-orchestrator phase=plan] -> implement -> [/validation-orchestrator phase=implementation]
```

Arguments: `$ARGUMENTS`

This runs as a skill in the main conversation because subagents cannot spawn other subagents. You are the one who spawns the lenses.

You do not do the deep review yourself. You fan out focused lens subagents in parallel, then verify, merge, and judge what they report. You never edit the spec, the plan, or the code. The only file you may write is the validation report.

## 1. Establish context

Work out these inputs before spawning anything. Use the arguments above first, then anything the user said earlier in the conversation:

- **Spec path**: the source of truth for requirements and acceptance criteria.
- **Plan path**: the implementation plan derived from the spec.
- **Phase**: `plan` (nothing implemented yet) or `implementation` (code changes exist).
- **Change set** (implementation phase only): the diff to validate. Default to `git diff <base>...HEAD` plus uncommitted changes, where `<base>` is the merge base with `main`. If the user names a base, commit range, or file list, use that.

If you weren't given a path, look for one: try `Glob` on `**/spec*.md`, `**/plan*.md`, `specs/**`, `docs/specs/**`, and `.specs/**`, and pick the most recently modified match that clearly belongs to the feature. If the phase isn't stated, infer it: use `implementation` if the change set touches files the plan says it will create or modify, otherwise use `plan`. If you can't find a spec at all, stop and say so. Don't validate against nothing.

Read the spec and plan yourself (skim them; don't analyze deeply). You need enough understanding to write the lens briefs and to judge findings later.

## 2. Fan out the lenses

Spawn every applicable lens with the `Agent` tool **in a single message so they run in parallel**. Each lens is a subagent type of the same name, defined in `.claude/agents/`:

| Lens | Plan phase | Implementation phase |
| --- | --- | --- |
| `lens-spec-coverage` | Every requirement and acceptance criterion maps to a plan step; nothing in the plan exceeds scope | Every requirement is implemented; no unrequested behavior was added |
| `lens-consistency` | Ambiguities, contradictions, and unstated assumptions between spec and plan | Code matches the decisions the plan made; any deviations are flagged |
| `lens-architecture` | The plan fits existing codebase structure and conventions, reuses existing code, and is ordered sensibly | The code follows conventions, avoids duplication, and keeps boundaries clean |
| `lens-risk` | Security, data, failure-mode, and edge-case risks the plan doesn't address | Those same risks, checked in the actual code |
| `lens-tests` | Acceptance criteria are testable and the plan includes a test strategy | Tests exist, pass, and actually assert the acceptance criteria |

Run all five in both phases unless the user asked for a subset. Give each lens a self-contained brief, because lenses start cold and have not seen this conversation:

```
PHASE: plan | implementation
SPEC: <absolute path>
PLAN: <absolute path>
CHANGE SET: <git command or file list>     (implementation phase only)
REPO ROOT: <absolute path>
FEATURE SUMMARY: <2-4 sentences in your words>
FOCUS NOTES: <anything specific you noticed that this lens should look at, or "none">
Return findings in the standard lens format.
```

Wait for every lens to report back before moving on. Don't guess at a lens's results while it is still running.

### Techniques (experiment only)

If the arguments don't include `technique`, skip this subsection. Everything else in this skill applies as written.

If `technique` is set, the phase must be `plan`. If it isn't, stop and say that techniques are plan-phase only. Then do the following:

- `technique=none`: run step 2 exactly as above (one round).
- `technique=second-round`, `technique=debate`, or `technique=ptu`: read `techniques/<technique>.md` in this skill's directory and follow it. It replaces step 2 with two lens rounds. Between rounds you write the round-1 outputs to `round1-findings.md` next to the spec. That file and the validation report are the only files you may write.

Two optional arguments split the rounds across sessions:

- `stop=round1`: run only round 1 as the technique describes it (for `ptu`, with the PREDICT PEERS lines), then stop. Don't write a round-1 file.
- `round1=<path>`: round 1 already ran in an earlier session. Don't spawn round-1 lenses, and don't write a round-1 file. `<path>` holds the five round-1 outputs verbatim, in the technique's layout. `round1-briefs.md` next to it holds the round-1 brief each lens got, in the same layout. Use `<path>` as the ROUND-1 FINDINGS FILE, take each lens's FEATURE SUMMARY and FOCUS NOTES from its round-1 brief, and continue from the step after round 1. Read `<path>` yourself only when the technique needs its contents from you: `ptu`'s reveal does, but `second-round` and `debate` only pass the path on.

Once the last lens round is done, stop. Skip steps 3 to 5: don't verify, merge, or judge the findings, and don't write a report. The experiment scores the lens outputs directly from the transcript. End with the single line `Lens rounds complete.`

## 3. Verify and merge

When the lenses return:

1. **Verify every blocker and major finding.** Open the cited location yourself (spec line, plan section, or file:line) and confirm the claim. Drop findings that don't hold up, and record that you dropped them. Lenses over-report, and an unverified blocker wastes the implementer's time.
2. **Deduplicate.** If two lenses report the same root problem, merge them into one finding and credit both lenses.
3. **Recalibrate severity** with these definitions, regardless of what the lens said:
   - **blocker**: the plan or implementation cannot satisfy the spec as written. Examples: a missing requirement, a contradiction, a failing or missing test for an acceptance criterion, a security hole.
   - **major**: likely to cause rework or defects. It should be fixed before moving on, but a human may choose to accept it.
   - **minor**: polish, clarity, or a small convention drift. It doesn't gate anything.
4. **Attribute fault.** Tag each finding with what must change: `spec` (the spec is ambiguous or wrong), `plan`, or `code`. Spec issues go back to the human, and you never paper over them.

## 4. Verdict

- **FAIL**: one or more verified blockers.
- **PASS_WITH_NOTES**: no blockers, but at least one major finding.
- **PASS**: only minor findings, or none.

In the plan phase, a FAIL means "revise the plan (or spec) before implementing." In the implementation phase, a FAIL means "not done; fix and re-run validation."

## 5. Report

Write the report next to the spec as `validation-<phase>.md` (for example `specs/foo/validation-plan.md`), overwriting any previous run for that phase. Then give the user the verdict, the blocker and major findings, and the report path:

```markdown
# Validation: <feature> — <phase>

**Verdict:** FAIL | PASS_WITH_NOTES | PASS
**Spec:** <path> · **Plan:** <path> · **Change set:** <range or n/a>
**Lenses run:** <list> · **Findings:** <n blocker / n major / n minor> · **Dropped as unverified:** <n>

## Blockers
### B1. <title>  — fix in: spec|plan|code · lenses: <names>
<what is wrong, 1-3 sentences>
Evidence: <path:line or section, with a short quote>
Fix: <concrete action>

## Major
...

## Minor
- <one line each, with location>

## Requirement traceability
| Requirement / AC | Plan step | Implementation | Test | Status |
| ... | ... | ... (impl phase) | ... (impl phase) | ok / missing / partial |

## Next step
<one sentence: proceed to implementation / revise plan / fix code and re-validate / clarify spec with a human>
```

Take the traceability table from `lens-spec-coverage` and correct it based on your verification. Keep the report tight, with no praise or filler. If a lens failed or timed out, state that in the header and judge the remaining findings without it. Never report a PASS for a lens that didn't run.

Do not start fixing findings yourself as part of this skill. Report them and let the user decide what happens next.
