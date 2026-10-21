# Technique: second-round (control C1)

Two lens rounds. Round 2 shows each lens everyone's round-1 findings, with no theory-of-mind or debate framing.

## Round 1

Run step 2 of the skill exactly as written: all five lenses in parallel, standard briefs. Keep every lens's full output verbatim.

## Save round 1

Skip this step if you were given `round1=` or `stop=round1`.

Once all five round-1 outputs are back, use `Write` once to save them to `round1-findings.md` in the spec's directory, in this layout:

```
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
```

Copy the outputs exactly as the lenses returned them. Don't summarize or reorder them. Write this file once and never paste its contents into a brief: the round-2 briefs refer to it by path, so you don't repeat it five times.

## Round 2

Spawn all five lenses again **in a single message**. Each round-2 lens is a fresh subagent of the same type. Give each one this brief:

```
PHASE: plan
ROUND: 2
SPEC: <absolute path>
PLAN: <absolute path>
REPO ROOT: <absolute path>
FEATURE SUMMARY: <same text as round 1>
FOCUS NOTES: <same text as round 1>
ROUND-1 FINDINGS FILE: <absolute path of round1-findings.md>

INSTRUCTIONS FOR ROUND 2:
You are <lens name>. Read the whole ROUND-1 FINDINGS FILE first. It holds all five lenses'
round-1 outputs, verbatim. Your own round-1 output is its "=== <lens name> ===" block.
Re-review the plan with these round-1 findings available, then give your final findings.
Keep the id of any round-1 finding you keep (even if you edit it). Give new findings new ids.
Return findings in the standard lens format.
```

The round-2 outputs are the final findings.
