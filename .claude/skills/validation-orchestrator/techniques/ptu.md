# Technique: ptu (predict-then-update)

Two lens rounds. In round 1, each lens also predicts its peers. The orchestrator then reveals what the peers actually found and where each lens's predictions missed. In round 2, each lens revises in light of those surprises.

## Round 1 (findings + predictions)

Run step 2 of the skill with the standard brief, plus these lines at the end of each lens's brief:

```
PREDICT PEERS: yes
The five lenses reviewing this plan in parallel are:
- lens-spec-coverage: every requirement and acceptance criterion maps to a plan step; nothing exceeds scope
- lens-consistency: ambiguities, contradictions, and unstated assumptions between spec and plan
- lens-architecture: fit with existing codebase structure and conventions, reuse, sensible ordering
- lens-risk: security, data, failure-mode, and edge-case risks the plan doesn't address
- lens-tests: acceptance criteria are testable and the plan has a test strategy
After your findings, include the PREDICTIONS block from your output format. For each of the
other four lenses above, by exactly that name, predict what it will flag in this plan, and
where you expect its findings to conflict with yours. Make your own findings first,
independently of the predictions.
```

Copy the peer list exactly as written. Keep every lens's full output verbatim, including the PREDICTIONS block.

## Reveal (orchestrator)

For each lens L, work out L's **surprises** by comparing L's PREDICTIONS with the four peers' actual round-1 FINDINGS:

- **Unpredicted:** each peer finding that none of L's `will_flag` predictions for that peer describes (same issue, roughly the same place). Cite the peer finding id.
- **Didn't happen:** each of L's `will_flag` or `conflicts_with_mine` predictions that no actual peer finding matches.

Judge matches by meaning, not exact wording. Number the surprises S1, S2, and so on, separately for each lens. Do this yourself. Don't spawn anything for it.

## Save round 1

Skip this step if you were given `round1=` or `stop=round1`.

Use `Write` once to save all five round-1 outputs to `round1-findings.md` in the spec's directory, in this layout:

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

Copy the outputs exactly as the lenses returned them, PREDICTIONS blocks included. Don't summarize or reorder them. Write this file once and never paste its contents into a brief: the round-2 briefs refer to it by path, so you don't repeat it five times.

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
ROUND-1 FINDINGS FILE: <absolute path of round1-findings.md>

YOUR SURPRISES:
- S1 (unpredicted): <peer> <finding id>: <one line>
- S2 (didn't happen): you predicted <peer> would <prediction>; nothing like it was found
...

INSTRUCTIONS FOR ROUND 2 (update):
You are <lens name>. Read the whole ROUND-1 FINDINGS FILE first. It holds all five lenses'
round-1 outputs, verbatim. Your own round-1 output, including your predictions, is its
"=== <lens name> ===" block.
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

If a lens has no surprises, write `YOUR SURPRISES: none` and `SURPRISE RESPONSES: none`.

The round-2 FINDINGS are the final findings.
