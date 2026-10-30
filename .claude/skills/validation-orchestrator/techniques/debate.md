# Technique: debate (D)

Two lens rounds. In round 2, each lens defends or concedes its own conflicting findings and rebuts peer findings it disagrees with.

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

INSTRUCTIONS FOR ROUND 2 (debate):
You are <lens name>. Read the whole ROUND-1 FINDINGS FILE first. It holds all five lenses'
round-1 outputs, verbatim. Your own round-1 output is its "=== <lens name> ===" block.
1. For every finding of yours that conflicts with a peer's finding (the two recommendations
   can't both be followed, or the peer's finding undermines yours), either DEFEND it with
   reasons grounded in the spec, plan, or code, or CONCEDE it.
2. For every peer finding you disagree with, REBUT it with reasons.
3. Then give your final findings. Keep the id of any round-1 finding you keep (even if you
   edit it). Give new findings new ids. Leave out findings you conceded.

Return the standard lens format, followed by this block:

DEBATE:
- re: <your finding id>
  conflicts_with: <peer finding id>
  stance: defend | concede
  reason: <why>
- rebut: <peer finding id>
  reason: <why you disagree>

Write `DEBATE: none` if nothing of yours conflicts and you disagree with no peer finding.
```

The round-2 FINDINGS are the final findings.
