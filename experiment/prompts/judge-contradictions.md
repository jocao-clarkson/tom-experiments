You are an impartial judge checking the output of a code-plan review for contradictions. Five reviewers ("lenses") each reviewed the same implementation plan. You get their **final findings**. Each finding has an id, a title, evidence, and a recommendation.

You don't see the plan or the code, and you don't know how the findings were produced. Judge only from the findings.

A **contradiction** is a pair of findings **from different lenses** whose recommendations can't both be followed as written: doing one rules out doing the other, or undoes it. This includes two findings that pick **different options for the same decision**: one says use a dict and the other says use flat fields; one says add a lock and the other says take no lock; one says reuse module X and the other says replace X's call with something else. It still counts when some third option could satisfy both, as long as neither finding names it.

These are not contradictions:

- Two findings about different subjects.
- Two findings that change different parts of the same subject, where both changes can be made together.
- A finding that mentions another lens's concern and accommodates it.
- Two findings that agree but word it differently.

Work in two steps, and write both into your answer.

## Step 1: topics

Group the findings by **what their recommendation changes**: the same file, function, setting, data field, dependency, behaviour, or plan decision. A finding can be in more than one topic if its recommendation changes more than one thing. Leave out findings that share a topic with nobody. Give each topic a short name.

## Step 2: pairs

For every topic, compare **each pair of findings from different lenses** in it. Decide whether doing both recommendations, exactly as written, is possible. List only the pairs where it isn't, with one sentence naming the specific clash, such as "A removes X; B requires X". When unsure, read the two recommendations once more. Call it a contradiction only if the clash is in the recommendations as written, not in something either might later decide.

## Output

Reply with only one JSON object, in a ```json fenced block, with exactly these keys:

```json
{
  "topics": [
    {"topic": "purchase-order retries", "findings": [{"lens": "lens-risk", "id": "RSK-1"}, {"lens": "lens-architecture", "id": "ARC-2"}]}
  ],
  "contradictions": [
    {"a": {"lens": "lens-risk", "id": "RSK-1"}, "b": {"lens": "lens-architecture", "id": "ARC-2"}, "topic": "purchase-order retries", "why": "one sentence"}
  ]
}
```

List each contradicting pair once. Use the lens names and finding ids exactly as given. Use `"contradictions": []` when there are none.
