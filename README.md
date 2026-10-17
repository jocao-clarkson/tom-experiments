# tom-experiments

A validation gate for spec-driven development, built from Claude Code skills and subagents.

```
spec -> plan -> /validation-orchestrator phase=plan -> implement -> /validation-orchestrator phase=implementation
```

Run the validation step twice. Run it once after the plan is written, to catch gaps before any code exists. Run it again after implementation, to check the code against both the spec and the plan.

## Usage

From Claude Code in this repo:

```
/validation-orchestrator phase=plan spec=specs/foo/spec.md plan=specs/foo/plan.md
/validation-orchestrator phase=implementation spec=specs/foo/spec.md plan=specs/foo/plan.md base=main
```

All arguments are optional. Without them, the skill looks for a spec and plan under `specs/`, `docs/specs/`, `.specs/`, or any `spec*.md` / `plan*.md`. It infers the phase from whether the current diff touches files the plan names. If it can't find a spec, it stops.

The result is a report written next to the spec as `validation-plan.md` or `validation-implementation.md`, with one of three verdicts:

| Verdict | Meaning |
| --- | --- |
| `FAIL` | At least one verified blocker. Revise the plan or spec, or fix the code, then re-run. |
| `PASS_WITH_NOTES` | No blockers, but major findings a human should accept or fix. |
| `PASS` | Minor findings only, or none. |

Each finding is tagged with what has to change: `spec`, `plan`, or `code`. Spec problems go back to a human rather than being worked around.

## Layout

```
.claude/
  skills/
    validation-orchestrator/SKILL.md   # coordinator, runs in the main conversation
  agents/
    lens-spec-coverage.md
    lens-consistency.md
    lens-architecture.md
    lens-risk.md
    lens-tests.md
```

### `validation-orchestrator` (skill)

The orchestrator is a skill, not a subagent, because Claude Code subagents can't spawn other subagents. Running in the main conversation lets it start all five lenses in parallel. It then:

1. Gives each lens a self-contained brief (phase, spec, plan, change set, feature summary, focus notes).
2. Checks every blocker and major finding against the cited file and line itself, and drops claims that don't hold up.
3. Merges duplicates, resets severity to blocker, major, or minor, and assigns each finding to `spec`, `plan`, or `code`.
4. Writes the report, including a requirement traceability table.

It never edits the spec, the plan, or the code.

### Lens subagents

Each lens is a read-only subagent (Read, Grep, Glob, Bash) running on Sonnet. Each returns findings in a fixed format, with severity, fix target, evidence, and a recommendation.

| Lens | Plan phase | Implementation phase |
| --- | --- | --- |
| `lens-spec-coverage` | Every requirement and acceptance criterion maps to a plan step; flags scope creep | Every requirement is implemented and tested; flags unrequested behavior. Builds the traceability table. |
| `lens-consistency` | Contradictions, ambiguities, and unstated assumptions between spec and plan | Code deviates from decisions the plan made |
| `lens-architecture` | Plan fits existing structure and conventions, reuses existing code, is buildable in order | Code follows conventions, avoids duplication, keeps boundaries clean |
| `lens-risk` | Security, data-integrity, failure-mode, concurrency, performance, and edge-case risks the plan misses | The same risks, checked in the actual code |
| `lens-tests` | Acceptance criteria are testable; the plan has a credible test strategy | Runs the tests; checks they exist, pass, and actually assert the acceptance criteria |
