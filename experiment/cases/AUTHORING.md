# Case authoring spec

The test cases are for an experiment on a plan-phase validation gate. Five "lens" reviewers each read a spec, a plan, and a small existing codebase, then report problems with the plan:

| Lens | Area |
| --- | --- |
| `lens-spec-coverage` | Every spec requirement and acceptance criterion maps to a plan step; plan steps that serve no requirement (scope creep); touching explicit out-of-scope items |
| `lens-consistency` | Contradictions, ambiguities, and unstated assumptions between spec and plan; plan reinterpreting spec names, data shapes, defaults, error behavior, ordering, limits; terminology drift |
| `lens-architecture` | Fit with the existing codebase: reuse of existing modules, file placement, layering/boundaries, new dependencies, step sequencing, blast radius on shared code, over/under-engineering |
| `lens-risk` | Security, data integrity, failure modes (timeouts, retries), concurrency, edge cases, performance, operability |
| `lens-tests` | Acceptance criteria are testable; the plan names which tests, at what level, where; error and edge cases covered; existing tests that need updating |

The experiment measures whether the lenses contradict each other, so most cases contain **seeded tensions**: places where two lenses' natural fixes pull against each other.

## Layout

Each case is a folder `experiment/cases/case-NN/` (two-digit number):

```
case-NN/
  fixture/            # the existing codebase the plan changes
  spec.md
  plan.md
  ground_truth.json
```

The runner copies `fixture/` to the root of a fresh repo and puts `spec.md` and `plan.md` under `specs/feature/`. **`ground_truth.json` is never shown to the lenses or the orchestrator.**

## fixture/

- A tiny but realistic codebase: 4 to 8 source files, plus a test file or two and the project's test config (`pyproject.toml`/`pytest.ini`, `package.json`, `go.mod`, and so on). Vary the language across cases (Python, TypeScript, Go).
- It must have conventions a plan could break. Examples: an existing HTTP client with retry and backoff, a shared validation helper, a repository/service layering rule, a logging helper that redacts fields, an error-type hierarchy, a config loader, a migration folder.
- It should look like ordinary working code. Don't use comments that point at problems ("TODO: insecure", "don't reuse this"), and don't include anything that mentions the experiment.

## spec.md (250 to 450 words)

A feature spec in the style of a real team doc: a goal, numbered functional requirements (R1, R2, ...), acceptance criteria (AC1, AC2, ...), non-functional constraints, and an out-of-scope list.

## plan.md (500 to 700 words, for every case)

An implementation plan for the spec: an overview, 8 to 12 numbered steps naming the files they touch, a test strategy section, and a rollout/notes section. **Clean and tension plans must look alike** in length, structure, confidence, and level of detail. A reader must not be able to tell which is which from length or tone.

## Seeded defects

A defect is a concrete, checkable problem in the plan, relative to the spec or the fixture: a missing requirement, a contradiction with the spec, rebuilding a helper that already exists in the fixture, an unbounded retry, a vague untestable acceptance criterion, and so on. Each defect must be detectable from the three inputs alone. Write defects into the plan naturally, never flagged.

## Seeded tensions

A tension is a pair of lenses whose **natural fixes conflict**. If both lenses flag their defect and each recommends the obvious fix, the two recommendations can't both be followed as written. A reconciled answer exists, but only if someone notices the conflict. Examples:

- Risk wants the plan to add retries to a call. Consistency notices that the spec/plan assumes the downstream write happens once, and the endpoint isn't idempotent.
- Tests wants e2e coverage of a flow. The spec has a delivery constraint (a date, a "no new infrastructure" rule, or a CI time budget) that rules out the obvious way to add it.
- Architecture wants the plan to reuse an existing fixture module. Risk considers that module unsafe for this use (it logs request bodies, has no timeout, or trusts input).
- Spec-coverage wants a requirement fully implemented. Architecture or risk sees that the only way to do it in this plan crosses a layering boundary or widens attack surface.

Some tensions must be **subtle**. In those, the conflict only shows up once you look at the fixture code, or the two fixes conflict on a detail (an ordering, a default, a limit), not head-on.

## Difficulty

In the pilot, a single round of the five lenses found every seeded defect and reconciled every tension, so the cases couldn't separate the techniques. One lens could usually see both sides of a tension and propose the reconciliation itself. For example, the existing client the architecture lens told the plan to reuse also had the per-call `retries=0` override that settled the risk lens's concern. Tension cases must follow these rules:

- **Split the evidence.** For each tension, put the fact behind side A and the fact behind side B in different places, each in its own lens's area. For example, side A rests on a spec non-functional constraint, and side B rests on a fixture detail two files away from the code the plan changes, such as a default in a helper, a side effect in a shared module, or a CI setting. No single file, spec section, or plan step should show both.
- **Each side's obvious fix must look complete.** To the lens that raises it, its natural fix should look correct and finished. The conflict only shows up when the two fixes are put together.
- **The reconciliation must need the other side's fact.** It must not be a one-parameter tweak sitting right next to the problem, like an override on the same function. Prefer reconciliations that a lens can only reach by using a fact from the other lens's area: an ordering, a limit, a default, a flag, or a narrower scope.
- **Don't hint at the conflict.** No plan sentence should mention both concerns, and no spec line should foreshadow the clash.
- **Keep the reconciling fact out of the reusing lens's file.** When one side's natural fix is "reuse module X", the detail that makes the plain reuse unsafe, and the switch or variant that fixes it, must not both sit in X. Put the hazard in a caller, a config default, or a shared helper X depends on. In the calibration, both cases that broke this rule (a cache's refresh-on-hit default in the cache's own file; an output helper's indentation in the helper itself) were still fully reconciled by a single lens.
- **Prefer 3 tensions per case,** with lens pairs that differ across the case's tensions, so a case doesn't rely on one lens pair.
- **Defects don't need to be hidden.** Recall is a guardrail: it only has to show a drop, so a baseline at 100% recall is fine. Mix subtle and head-on defects naturally, and spend the difficulty budget on the tensions.
- **Don't telegraph defects.** Avoid plan phrasing that invites scrutiny ("for simplicity", "we assume", "temporarily"). Write the plan with the same confidence everywhere.

Target, checked with a `baseline`-only run: at most half of tensions reconciled. In the first calibration, cases that followed these rules reconciled 1 of 7 tensions; the two that broke the reuse rule below reconciled 4 of 4.

## ground_truth.json

```json
{
  "case_id": "case-NN",
  "type": "tension",
  "domain": "api",
  "defects": [
    {
      "id": "D1",
      "description": "What is wrong, specific enough for a judge to match a reviewer's finding to it.",
      "location": "plan.md step 4; fixture/src/http_client.py",
      "expected_lenses": ["lens-risk"],
      "severity": "major"
    }
  ],
  "tensions": [
    {
      "id": "T1",
      "lenses": ["lens-risk", "lens-consistency"],
      "related_defects": ["D1", "D2"],
      "description": "Why the two natural fixes conflict.",
      "lens_a_fix": "The fix lenses[0] would naturally recommend.",
      "lens_b_fix": "The fix lenses[1] would naturally recommend.",
      "reconciliation": "What a final set of findings looks like when the conflict has been explicitly reconciled.",
      "subtle": false
    }
  ]
}
```

Rules:

- `type` is `tension` or `clean`. `domain` is one of `api`, `data-pipeline`, `auth`, `cli`, `mobile-backend`.
- `expected_lenses` has 1 or 2 entries. `severity` is `blocker`, `major`, or `minor`. Use the lens names exactly as in the table above.
- **Tension cases** have 2 to 4 tensions and 3 to 8 defects. Every tension's `related_defects` must exist, and at least one related defect must expect each of the tension's two lenses.
- **Clean cases** have `"defects": []` and `"tensions": []`. The plan really is sound: it covers the spec, reuses the fixture correctly, handles the realistic risks, and has a credible test strategy. It must still not read as suspiciously perfect.
- The file must be valid JSON.
