You are editing code-review findings so that a later judge can't tell how they were produced. Five reviewers ("lenses") each reviewed the same implementation plan. Some of them may have seen each other's findings, in one or more rounds. You get every final finding.

Rewrite each finding's text fields (`title`, `evidence`, `detail`, `recommendation`, or `text`) so that it reads as if its lens wrote it alone, in a single pass. Remove or rephrase:

- references to other findings by id (`CON-2`, `ARC-5`, `see RSK-12`), including lists such as "(CON-2, ARC-5, RSK-3)";
- mentions of other lenses or reviewers ("the risk lens", "peers", "four lenses reached the same conclusion", "as architecture says");
- mentions of rounds, earlier versions, predictions or debate ("in round 1", "my earlier claim was wrong", "I concede", "I defend", "I raise my severity to match", "no peer raised this", "the test lens will probably say more");
- statements that the finding agrees with, defers to, replaces or is covered by another finding.

When such a reference carries technical content, keep the content and drop only the attribution. For example, "Adopt CON-9's rule: count pending rows only within upload_expiry_s" becomes "Count pending rows only within upload_expiry_s." When a sentence only defers to another finding without stating anything itself ("covered by COV-1 and CON-1"), delete it.

Keep everything else exactly: every technical fact, file name, line quote, number, requirement id (R4, AC3) and recommendation, and the finding's own meaning, scope and strength. Don't add facts, fixes or caveats, don't merge or split findings, and don't fix mistakes. If a finding has nothing to remove, copy its fields unchanged. A finding's own id may appear in its text; references to the same lens's other findings (same prefix) also count as references to remove.

## Output

Reply with only one JSON object, in a ```json fenced block, with every finding in the input order and the same `lens` and `id`, and only the text fields the input finding has:

```json
{
  "findings": [
    {"lens": "lens-risk", "id": "RSK-1", "title": "...", "evidence": "...", "detail": "...", "recommendation": "..."}
  ]
}
```
