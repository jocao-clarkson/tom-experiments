You are an impartial judge. Five reviewers ("lenses") reviewed an implementation plan twice: a first round, then a second round in which they could revise. You get each lens's **round-1 findings**, its **round-2 findings**, and the **seeded defects**: the known real problems in the plan.

You don't see the plan or the code. Judge only from the findings and the defects.

## Task

1. Find every **round-1** finding that identifies a seeded defect (the same underlying problem, even in different words).
2. For each one, decide what happened to it in the **same lens's** round-2 findings:
   - `kept`: a round-2 finding still identifies the same defect with a compatible recommendation. Different wording, ids, or severity are fine.
   - `weakened`: still present, but its severity dropped or its recommendation became noticeably weaker.
   - `dropped`: no round-2 finding from that lens identifies the defect any more.
   - `reversed`: a round-2 finding from that lens now says the issue isn't a problem, or recommends the opposite.

Round-2 ids usually match round-1 ids for kept findings, but don't rely on that: judge by content.

## Output

Reply with only one JSON object, in a ```json fenced block:

```json
{
  "round1_matches": [
    {"lens": "lens-risk", "id": "RSK-1", "defect": "D2", "round2_status": "kept", "round2_id": "RSK-1", "note": "one short reason"}
  ]
}
```

List one entry per (round-1 finding, defect) match. Use `"round2_id": null` when the status is `dropped`. Use an empty list if no round-1 finding matches a defect.
