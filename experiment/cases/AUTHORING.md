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
