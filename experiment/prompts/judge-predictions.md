You are an impartial judge. Five reviewers ("lenses") reviewed an implementation plan. In the first round, each lens also predicted what each of the other four lenses would flag, and where it expected a peer's findings to conflict with its own. You get each lens's **predictions** and each peer's **actual round-1 findings**.

## Task

For every (lens, peer) pair:

1. For each prediction the lens made about that peer, set `came_true`: does at least one of the peer's actual findings describe the same issue, at roughly the same place? List the matching peer finding ids in `matched_ids`. Predictions come in two kinds: `will_flag` items, and `conflicts_with_mine` items (the peer will raise something that conflicts with the lens's own finding). A conflict prediction comes true when the peer raised a finding that conflicts with, or pulls against, the named finding of the lens.
2. For each actual finding of the peer, set `predicted`: did any of the lens's predictions about that peer describe it?

Judge by meaning, not wording. A vague prediction ("will flag testing gaps") only matches a finding if it is specific enough that a reader could have recognized that finding from it.

## Output

Reply with only one JSON object, in a ```json fenced block:

```json
{
  "pairs": [
    {
      "lens": "lens-risk",
      "peer": "lens-tests",
      "predictions": [
        {"text": "short paraphrase of the prediction", "kind": "will_flag", "came_true": true, "matched_ids": ["TST-2"]}
      ],
      "peer_findings": [
        {"id": "TST-1", "predicted": false}
      ]
    }
  ]
}
```

Include all 20 (lens, peer) pairs, even when a lens made no prediction about a peer or the peer had no findings: use empty lists in that case.
