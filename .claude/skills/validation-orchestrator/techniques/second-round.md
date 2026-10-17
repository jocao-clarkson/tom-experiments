# Technique: second-round (control C1)

Two lens rounds. Round 2 shows each lens everyone's round-1 findings, with no theory-of-mind or debate framing.

## Round 1

Run step 2 of the skill exactly as written: all five lenses in parallel, standard briefs. Keep every lens's full output verbatim.

## Round 2

Once all five round-1 outputs are back, spawn all five lenses again **in a single message**. Each round-2 lens is a fresh subagent of the same type. Give each one this brief:

```
PHASE: plan
ROUND: 2
SPEC: <absolute path>
PLAN: <absolute path>
REPO ROOT: <absolute path>
FEATURE SUMMARY: <same text as round 1>
FOCUS NOTES: <same text as round 1>

ROUND-1 FINDINGS FROM ALL FIVE LENSES (verbatim):
=== lens-spec-coverage ===
<full round-1 output>
=== lens-consistency ===
<full round-1 output>
=== lens-architecture ===
<full round-1 output>
=== lens-risk ===
<full round-1 output>
=== lens-tests ===
<full round-1 output>

INSTRUCTIONS FOR ROUND 2:
You are <lens name>. Your own round-1 output is the "=== <lens name> ===" block above.
Re-review the plan with these round-1 findings available, then give your final findings.
Keep the id of any round-1 finding you keep (even if you edit it). Give new findings new ids.
Return findings in the standard lens format.
```

Paste the round-1 outputs exactly as the lenses returned them. Don't summarize or reorder them, and use the same lens order for every lens.

The round-2 outputs are the final findings that steps 3 to 5 use.
