# Technique: ptu (predict-then-update)

Two lens rounds. In round 1, each lens also predicts its peers. The orchestrator then reveals what the peers actually found and where each lens's predictions missed. In round 2, each lens revises in light of those surprises.

## Round 1 (findings + predictions)

Run step 2 of the skill with the standard brief, plus these lines at the end of each lens's brief:

```
PREDICT PEERS: yes
After your findings, include the PREDICTIONS block from your output format. For each of the
other four lenses, predict what it will flag in this plan, and where you expect its findings
to conflict with yours. Make your own findings first, independently of the predictions.
```

Keep every lens's full output verbatim, including the PREDICTIONS block.

## Reveal (orchestrator)

For each lens L, work out L's **surprises** by comparing L's PREDICTIONS with the four peers' actual round-1 FINDINGS:

- **Unpredicted:** each peer finding that none of L's `will_flag` predictions for that peer describes (same issue, roughly the same place). Cite the peer finding id.
- **Didn't happen:** each of L's `will_flag` or `conflicts_with_mine` predictions that no actual peer finding matches.

Judge matches by meaning, not exact wording. Number the surprises S1, S2, and so on, separately for each lens. Do this yourself. Don't spawn anything for it.

## Round 2 (update)

Spawn all five lenses again **in a single message**. Each round-2 lens is a fresh subagent of the same type. Give each one this brief:

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

YOUR SURPRISES:
- S1 (unpredicted): <peer> <finding id>: <one line>
- S2 (didn't happen): you predicted <peer> would <prediction>; nothing like it was found
...

INSTRUCTIONS FOR ROUND 2 (update):
You are <lens name>. Your own round-1 output, including your predictions, is the
"=== <lens name> ===" block above.
1. For each surprise, say whether it changes your view of the plan and why.
2. Then give your final findings. Keep the id of any round-1 finding you keep (even if you
   edit it). Give new findings new ids.
3. Do not drop or weaken a real issue in your own area just to agree with a peer. Change a
   finding only when the surprise shows you were wrong about the spec, plan, or code.
Do not include a PREDICTIONS block this round.

Return the standard lens format, followed by this block:

SURPRISE RESPONSES:
- surprise: S1
  changes_view: yes | no
  why: <reason>
```

Paste the round-1 outputs exactly as the lenses returned them, PREDICTIONS blocks included. Don't summarize or reorder them, and use the same lens order for every lens. If a lens has no surprises, write `YOUR SURPRISES: none` and `SURPRISE RESPONSES: none`.

The round-2 FINDINGS are the final findings that steps 3 to 5 use. Predictions, surprises, and surprise responses go in the raw file only.
