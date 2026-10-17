# Raw output file

When `technique` is set, write `validation-plan.raw.json` in the same folder as the report, before you start step 3 (verify and merge). It records what the lenses returned, **exactly as they returned it**. A judge uses it to measure contradictions, which the merged report hides.

```json
{
  "technique": "none | second-round | debate | ptu",
  "phase": "plan",
  "spec": "<path>",
  "plan": "<path>",
  "rounds": {
    "1": {
      "lens-spec-coverage": "<full round-1 output, verbatim>",
      "lens-consistency": "...",
      "lens-architecture": "...",
      "lens-risk": "...",
      "lens-tests": "..."
    },
    "2": {
      "lens-spec-coverage": "<full round-2 output, verbatim>",
      "...": "..."
    }
  },
  "surprises": {
    "lens-spec-coverage": "<the YOUR SURPRISES text you sent this lens, verbatim>",
    "...": "..."
  },
  "lens_errors": {
    "<lens name>": "<what went wrong, if a lens failed or timed out>"
  }
}
```

Rules:

- Each value in `rounds` is the lens's whole reply as a string, with nothing fixed, trimmed, or merged. Predictions, debate blocks, and surprise responses stay inside it.
- `technique=none` has only round `"1"`. Leave out `"surprises"` unless the technique is `ptu`. Leave out `"lens_errors"` if every lens returned.
- Overwrite any earlier raw file for this phase.
