# Technique: debate (D)

Two lens rounds. In round 2, each lens defends or concedes its own conflicting findings and rebuts peer findings it disagrees with.

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

INSTRUCTIONS FOR ROUND 2 (debate):
You are <lens name>. Your own round-1 output is the "=== <lens name> ===" block above.
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

Paste the round-1 outputs exactly as the lenses returned them. Don't summarize or reorder them, and use the same lens order for every lens.

The round-2 FINDINGS are the final findings.
