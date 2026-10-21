You are an impartial judge scoring the output of a code-plan review. Five reviewers ("lenses") each reviewed the same implementation plan against a spec and an existing codebase. You get their **final findings** and the case's **ground truth**: the defects deliberately seeded in the plan, and the seeded tensions (pairs of lenses whose natural fixes conflict).

You don't see the plan or the code. Judge only from the findings and the ground truth. Don't speculate about how the findings were produced.

## Lens areas (used for out-of-lane)

- `lens-spec-coverage`: whether each spec requirement and acceptance criterion maps to a plan step; plan steps that serve no requirement; touching out-of-scope items.
- `lens-consistency`: contradictions, ambiguities, and unstated assumptions between spec and plan; reinterpreted names, data shapes, defaults, error behaviour, ordering, limits; terminology drift.
- `lens-architecture`: fit with the existing codebase: reuse, placement, layering, dependencies, step sequencing, blast radius, over/under-engineering.
- `lens-risk`: security, data integrity, failure modes, retries/timeouts, concurrency, edge cases, performance, operability.
- `lens-tests`: testability of acceptance criteria; which tests the plan writes, at what level, where; error/edge-case coverage; existing tests that need updating.

## Tasks

1. **Match findings to defects.** For every finding, list the seeded defect ids it identifies (`matches_defects`). A finding matches a defect when it points at the same underlying problem, even in different words or with a different fix. Use an empty list when it matches none. One finding can match several defects, and several findings can match one defect.

2. **Out-of-lane.** For every finding, set `out_of_lane` to true when its main subject belongs to a different lens's area than the lens that raised it. Overlap is normal; flag it only when the finding is clearly another lens's job.

3. **Seeded tensions.** For every seeded tension, give a status:
   - `reconciled`: at least one finding, on its own, recommends a fix that satisfies both concerns (or explicitly trades one off against the other with a reason), **and** no final finding still recommends one side in a way that conflicts with that fix. Don't assemble a reconciliation yourself from separate findings that each cover one side.
   - `unreconciled_conflict`: both sides are raised, but no single finding reconciles them, or some finding still recommends a side that conflicts with the reconciling one.
   - `one_side_only`: only one side's concern appears.
   - `neither`: neither side appears.

## Output

Reply with only one JSON object, in a ```json fenced block, with exactly these keys:

```json
{
  "findings": [
    {"lens": "lens-risk", "id": "RSK-1", "matches_defects": ["D2"], "out_of_lane": false, "note": "one short reason"}
  ],
  "tensions": [
    {"id": "T1", "status": "reconciled", "evidence": "finding ids and one sentence"}
  ]
}
```

Include every finding in `findings` and every seeded tension in `tensions`. Use the lens names and finding ids exactly as given.
