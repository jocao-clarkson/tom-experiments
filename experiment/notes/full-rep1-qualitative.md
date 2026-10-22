# Qualitative analysis: full run, rep 1 (24 tension cases, 70 tensions)

Written by a Sonnet subagent from the judged runs (its ad-hoc scripts aren't committed). All numbers below are computed from results/full/runs/*/*/rep1/judge.json, lens_outputs.json. Status counts per technique (70 tensions each):

| technique | reconciled | compatible | conflict | one_side_only |
|---|---|---|---|---|
| baseline | 33 | 27 | 9 | 1 |
| second-round | 44 | 23 | 2 | 1 |
| debate | 43 | 22 | 4 | 1 |
| ptu | 42 | 26 | 0 | 2 |

## Summary

- Any round-2 step (second-round, debate, ptu) lifts reconciled by about +9 to +11 tensions over baseline; the differences among the three round-2 techniques (44 / 43 / 42) are one or two tensions. That is smaller than the judge noise: 4 to 5 of the "reconciled" calls per technique were decided 2-1, and the same finding text gets different labels across techniques (see Q5, case-25 T3).
- Overlap is large. 28 tensions are reconciled by all four, 19 by none; only 23 of 70 differ at all. 7 are won by all three round-2 techniques but not baseline. The three round-2 techniques differ on a handful of scattered tensions (second-round vs debate: 4 vs 3 exclusive; debate vs ptu: 7 vs 6; second-round vs ptu: 7 vs 5). No tension type (lens pair) is consistently won by one technique. Architecture is the reconciling lens in 23-26 of the reconciled cases in every technique.
- Baseline-reconciled tensions: 33. Second-round lost 1 (case-11 T2), debate 1 (case-13 T2, shared with second-round), PTU 3 (case-02 T2, case-03 T1, case-22 T3). PTU's losses are the largest, and in two of them the judge text says the facts are split across several findings (PTU findings often defer with "covered by COV-1 and CON-1").
- Second-round and debate behave alike because the visible effect of round 2 is the same: a lens that had a conflicting "natural fix" in baseline sees the peer's reconciling finding and adopts it (case-20 T1 RSK-1, case-30 T1, case-08 T2 COV-1). Debate rarely changes anyone's mind: of 356 DEBATE stances 311 are "defend" and 45 "concede", and the DEBATE block is stripped before the judge, so only the revised findings count. Debate leaves 4 clashes where second-round leaves 2, consistent with lenses defending their side.
- PTU's zero clash is real in the data but is not strong evidence that predictions "anticipate" conflicts. Of the 11 tensions where baseline or debate clashed, PTU reconciled 6 and rated 5 compatible, none dropped. Compatible, not reconciled, is the typical PTU outcome when the others clash. Conflict predictions (`conflicts_with_mine`) came true in only 4 of those 11 tensions, versus 33 of 59 others, so there is no sign they track the clash tensions.
- The more plausible mechanism for PTU: peer-awareness changes how each finding is written. 54% of PTU final findings cite another lens's ID (vs 22% second-round, 20% debate), and 20% say "peer(s)". Findings carry caveats about the peer's side (case-03 T2: ARC-5/ARC-6 already note that the queue payload persists and logs the raw token; baseline had no such caveat). A finding that internalises the peer's constraint cannot "clash" with it, but it often does not commit to the full reconciliation either, so the judge says compatible. This fits "hedge/cover both sides" but "either/alternatively" wording is NOT more frequent in PTU (81 "either" vs 68 second-round / 57 debate / 88 baseline), so the hedging is cross-referencing, not option lists. Unclear how much is causal.
- PTU volume: findings are 1149 vs 1019 (debate), 1106 (second-round), 1001 (baseline). PTU round 1 was 993, same as baseline; the extra ~156 findings appear in round 2. Average finding length is 759 chars (PTU) vs 683 (debate), 741 (second-round), 758 (baseline), so length per finding is mostly unchanged; total text is ~25% above debate.
- Judge concerns: non-unanimous votes were baseline 12, second-round 6, debate 10, ptu 8 (strict 2-1: 11, 6, 10, 8; baseline has one 1-1-1). Near-identical findings received different labels (case-25 T3), and several "reconciled" evidence strings admit a gap ("It does not name user.ValidatePassword", "weak point").
- Technique leakage is severe for a blind judge or labeller: baseline findings contain 0 cross-lens ID references and no "round-1/peer" wording; second-round, debate and PTU findings contain "round-1 COV-7", "Four other lenses also flagged this", "peers CON-1 and RSK-1", "I raise my severity to match". PTU is the most identifiable.

Per-technique 2-1 split counts (non-unanimous / strict 2-1 / of which the final status was "reconciled"): baseline 12 / 11 (+1 three-way) / 3; second-round 6 / 6 / 1; debate 10 / 10 / 5; ptu 8 / 8 / 4.

## Q1. Per-tension status table

Legend: REC reconciled, COMP unreconciled_compatible, CLASH unreconciled_conflict, ONE one_side_only. Order: baseline, second-round, debate, ptu. Vote-split markers are omitted here.

```
case-01 T1 REC  REC  REC   REC       case-01 T2 REC REC REC REC     case-01 T3 COMP COMP COMP COMP
case-02 T1 COMP REC  COMP  COMP      case-02 T2 REC REC REC COMP    case-02 T3 REC REC REC REC
case-03 T1 REC  REC  REC   COMP      case-03 T2 CLASH COMP CLASH COMP  case-03 T3 REC REC REC REC
case-05 T1 REC  REC  REC   REC       case-05 T2 COMP COMP COMP ONE  case-05 T3 REC REC REC REC
case-06 T1 COMP COMP COMP  COMP      case-06 T2 REC REC REC REC     case-06 T3 REC REC REC REC
case-08 T1 REC  REC  REC   REC       case-08 T2 CLASH REC REC REC   case-08 T3 COMP COMP COMP COMP
case-09 T1 COMP COMP COMP  COMP      case-09 T2 CLASH CLASH CLASH COMP
case-10 T1 REC  REC  REC   REC       case-10 T2 REC REC REC REC     case-10 T3 COMP REC REC REC
case-11 T1 REC  REC  REC   REC       case-11 T2 REC COMP REC REC    case-11 T3 REC REC REC REC
case-12 T1 COMP COMP COMP  COMP      case-12 T2 REC REC REC REC
case-13 T1 COMP REC  REC   COMP      case-13 T2 REC COMP COMP REC   case-13 T3 CLASH REC REC REC
case-15 T1 REC  REC  REC   REC       case-15 T2 COMP COMP COMP COMP case-15 T3 COMP COMP REC COMP
case-16 T1-T3 COMP in all four techniques
case-18 T1 COMP COMP COMP  COMP      case-18 T2 COMP COMP COMP REC  case-18 T3 COMP REC COMP REC
case-19 T1 REC  REC  REC   REC       case-19 T2 CLASH REC REC REC   case-19 T3 CLASH REC REC REC
case-20 T1 CLASH REC REC   REC       case-20 T2 COMP REC COMP REC   case-20 T3 COMP REC REC REC
case-21 T1 REC  REC  REC   REC       case-21 T2 REC REC REC REC     case-21 T3 COMP COMP COMP COMP
case-22 T1 CLASH COMP REC  COMP      case-22 T2 COMP COMP COMP REC  case-22 T3 REC REC REC COMP
case-23 T1 REC  REC  REC   REC       case-23 T2 COMP CLASH CLASH COMP  case-23 T3 REC REC REC REC
case-25 T1 ONE  ONE  ONE   ONE       case-25 T2 REC REC REC REC     case-25 T3 COMP COMP CLASH REC
case-26 T1 COMP REC  COMP  COMP      case-26 T2 COMP COMP COMP COMP case-26 T3 REC REC REC REC
case-28 T1-T3 REC in all four
case-29 T1 REC  REC  REC   REC       case-29 T2 COMP COMP COMP COMP case-29 T3 REC REC REC REC
case-30 T1 CLASH REC REC   COMP      case-30 T2 COMP COMP COMP COMP case-30 T3 REC REC REC REC
```

Pattern counts over reconciled (T/F) for [baseline, SR, debate, ptu]:
- reconciled by all four: 28; by none: 19.
- by SR, debate and PTU but not baseline: 7 (case-08 T2, 10 T3, 13 T3, 19 T2, 19 T3, 20 T1, 20 T3; baseline was CLASH or COMP).
- Only PTU reconciled: 3 (case-18 T2, case-22 T2, case-25 T3). Only second-round: 2 (case-02 T1, case-26 T1). Only debate: 2 (case-15 T3, case-22 T1). Reconciled by baseline and all but one round-2 technique: PTU missing in 3, SR missing in 1 (case-11 T2), and one pattern [T,F,F,T] (case-13 T2, SR and debate missing).
- Pairwise agreement of labels: SR-debate 61/70, SR-PTU 55/70, debate-PTU 53/70, baseline-SR 52/70, baseline-debate 56/70, baseline-PTU 50/70.

Noise vs systematic:
- Reconciliation by lens pair (reconciled counts, baseline / SR / debate / PTU): architecture+risk (n=15) 7/11/10/9; architecture+consistency (13) 8/9/8/9; architecture+spec-coverage (7) 4/6/6/6; architecture+tests (4) 1/3/3/3; consistency+risk (15) 7/7/7/8; risk+spec-coverage (7) 3/5/6/4; consistency+tests (4) 3/3/3/3; risk+tests (4) 0/0/0/0; spec-coverage+tests (1) 0/0/0/0. Round 2 helps mostly where architecture is one party (a lens with a concrete code fact it can supply). Consistency+risk and risk+tests tensions do not benefit from any technique. Differences among round-2 techniques within a pair are 0 to 2; I see no pair where one technique consistently wins. The one hint is risk+spec-coverage (debate 6, PTU 4), n=7, not conclusive.
- Per-case sums [baseline, SR, debate, PTU] show the same scatter: case-20 [0,3,2,3], case-19 [1,3,3,3], case-18 [0,1,0,2], case-02 [2,3,2,1], case-03 [2,2,2,1].
- So I read the second-round / debate / PTU differences as noise, with the caveat that rep 1 is a single sample.

Baseline-reconciled tensions "lost" by round-2 techniques:
- case-11 T2: second-round COMP.
- case-13 T2: second-round and debate COMP (PTU kept it).
- case-02 T2, case-03 T1, case-22 T3: PTU COMP. For case-03 T1 the PTU judge text says ARC-4 "comes closest ... But it never says the shared instance gets config.linkTtlMinutes (24h)"; the 30-minute default "sits in separate findings (ARC-7, CON-1, COV-3)". For case-02 T2 the PTU judge text says "No finding commits to scaling by each currency's exponent" (the lens asked the spec owner to choose instead).

## Q2. Why second-round and debate look the same

- Same round 1: second-round and debate reuse the baseline round-1 run, so they differ only in the round-2 prompt. Their final labels agree on 61/70 tensions and 40 of 44/43 reconciled ones overlap.
- What reconciled findings in round 2 look like: where baseline did not reconcile and a round-2 technique did (13 for SR, 11 for debate), the reconciling finding is mostly the same finding id as in baseline but with a substantially rewritten recommendation (text similarity < 0.6 in 9 of 13 SR cases and 7 of 11 debate cases), or an unchanged reconciling finding whose clashing peer finding was changed (case-19 T2 ARC-3 is 0.98 similar in debate and reconciling in baseline too; in baseline RSK-4 clashed, in debate RSK-4 was revised and listed among the supporting side). Examples:
  - case-20 T1: baseline RSK-1 recommended "a bespoke outbox table with its own background loop" (clash with ARC-3). In both SR and debate RSK-1 now says to enqueue with tasks.enqueue in the same transaction and call push.send_silent, which is the reconciliation; the judge credits RSK-1.
  - case-30 T1: baseline COV-3/CON-1/ARC-5 said count all statuses (clash with RSK-6's expiry window). SR: CON-1 "defers to CON-9", which counts pending rows only within upload_expiry_s (900 s). Debate: RSK-6 kept, CON-1 added to the same side, no clash.
  - case-08 T2: baseline COV-1 recommended nested {"api_key": {...}} metadata (clash). In SR and debate COV-1 recommends flat key_id/name/scopes via AuditLog.record.
- Debate argumentation does show up, but in a way that does not help beyond second-round: round-2 text such as "The job-queue fix proposed by ARC-4 would persist the raw token" (case-03 T2 RSK summary) and "RSK-5: ... see RSK-12 for the payload caveat" appears in the findings, but ARC-4 stays unchanged ("defend"), so the clash persists (case-03 T2, case-09 T2, case-23 T2, case-25 T3). Debate has 311 "defend" and 45 "concede" stances across 150 lens-round-2 outputs. Findings flips: of ~640 matched seeded-defect findings 9 were weakened and 1 dropped in debate (PTU: 2 weakened, 2 dropped), so almost nothing is withdrawn.
- Finding counts: debate round 2 = 1019 vs baseline 1001 (almost no new findings; positions are defended), second-round = 1106. Debate findings are also shorter (683 vs 741 chars). A plausible reading: the debate frame trades extra findings for defending, which gives it a similar reconciled count but 2 more clashes than second-round. Unclear whether that difference is real (4 vs 2 clashes).

## Q3. PTU's zero clash rate

Tensions where baseline or debate clashed (11 distinct): PTU status
- REC (6): case-08 T2, case-13 T3, case-19 T2, case-19 T3, case-20 T1, case-25 T3.
- COMP (5): case-03 T2, case-09 T2, case-22 T1, case-23 T2, case-30 T1.
- one_side_only / neither: 0. Nobody visibly dropped a side. (Separately, ptu's two one_side_only are case-05 T2, where no PTU finding mentions the event bus, so side A has no findings, and case-25 T1, one_side_only in all techniques.)

What the PTU findings did instead of clashing:
- case-03 T2 (baseline and debate CLASH): PTU ARC-5 keeps enqueue send_mail with the link in the payload but ARC-6 (written in round 1, before seeing peers) flags "the link containing the raw token is stored in the jobs table and logged" and suggests redacting or alternatively "send inline"; RSK-7 suggests token id or encrypted token. The judge: "The recommendations could be followed together, but none meets (a), (b) and (c)". Baseline had no payload caveat at all, so ARC-4 clashed with RSK-5/12. The PTU lens covered both sides but did not propose the token-free job kind.
- case-09 T2: debate clash was RSK-4 treating 404 as transient. PTU risk finding RSK-2 limits continuation to network errors and 5xx and makes 4xx fatal, i.e. the risk lens converged on the reconciling rule but never tied it to the id-field bug, hence COMP.
- case-23 T2: SR/debate clash was RSK-3/COV-7 "now() inside SQL" vs the injected clock. PTU TST-4 notes "if expiry moves into the DB, the fake must take the same clock", a caveat that removes the clash but no finding proposes consume(tokenHash, at).
- case-30 T1: PTU RSK-8 "only recommends documenting the consequence and getting it accepted" for the stuck-at-20 problem. Side A (count all statuses) effectively wins and side B is downgraded to a note. This is the closest to "drop one side" even though the judge said COMP.
- case-22 T1: PTU RSK-2/ARC-4 write all columns and mask the email; judge notes CON-11 says a masked file cannot replay the email, so (c) not met; COMP.
- Reconciles: case-19 T2/T3, case-20 T1, case-08 T2, case-13 T3 are reconciles that every round-2 technique reached; PTU is not special there. case-25 T3 is the only tension where PTU reconciled and the other round-2 techniques did not (see Q4 and Q5).

Did predictions anticipate the conflict?
- Prediction totals (all pairs): 1589 will_flag true, 69 will_flag false; 145 conflicts_with_mine came true, 252 did not (37% hit rate).
- For the 11 clash tensions: a true conflict prediction for the lens pair exists in 4 of 11; for the other 59 tensions in 33 of 59. No enrichment, so there is no evidence predictions specifically foresaw the clash.
- Anecdotes that point toward anticipation: case-03 T2 architecture predicted "Conflict with ARC-6: never put raw token in persisted job payload" (marked came_true false, the judge matching it against peer findings) and produced ARC-6 itself in round 1. case-09 T2 risk predicted the consistency lens "treats field name as naming inconsistency rather than functional bug" (false) and the PTU risk lens ended with a rule that matches the reconciliation. So predictions plausibly shape round-1 wording, but the data cannot isolate this.
- Hedging: PTU final findings often defer ("No peer raised this", "covered by COV-1 and CON-1", "Four peer lenses raised the same bug"). That reduces explicit contradiction (no clash) and also reduces self-contained reconciling findings (more COMP, 3 baseline reconciliations lost). The longer, more numerous findings and slightly lower precision are consistent with this, but "either/alternatively" counts are not higher, so I would call the hedging explanation plausible, not shown.

## Q4. Illustrative tensions where PTU and debate differ

1. case-25 T3 (PTU REC, debate CLASH, SR/baseline COMP). Envelope vs flat error body. Debate ARC-3: "Decide the shape explicitly. If the spec's flat body is required, add one shared helper in httpx ... Otherwise amend R3 to use httpx.Error with details.field" and COV-1 explicitly "keep the flat body" -> clash. PTU ARC-3 has near-identical advice ("Decide at spec level whether R3 and AC4 should use {"error":...}. If the flat body must stay, add a shared httpx helper ... Either way, use the spec codes") and the judge reconciles unanimously. Mechanism: not a clear PTU effect. The two ARC-3 texts are nearly the same; the label differs because debate's COV-1 held the line and PTU's COV-1 did not rule it out. Looks like judge variance plus a peer-aware softening of the coverage lens.
2. case-22 T1 (debate REC, PTU COMP, baseline CLASH, SR COMP). Dead-letter file PII vs replay. Debate CON-14 says "masking or omitting customer_email ... relies on the fact that R3 does not store email, so replay does not need it" -- a single finding that carries the fact that resolves it. PTU RSK-2/ARC-4 mask the email and log only ids but "Neither relies on ... the refunds table having no email" and CON-11 says masked file cannot replay. Mechanism: a debate lens defended its side with a specific fact; PTU findings reach the compatible solution without the fact.
3. case-30 T1 (debate REC, PTU COMP, baseline CLASH). Counting pending uploads. Debate keeps RSK-6 (lazy 900 s window, no scheduled task); PTU's risk lens produced RSK-8 "document the consequence and get it accepted" and the coverage side kept count-all. Mechanism: in PTU the risk lens, aware of the spec's out-of-scope list (and, in the other findings, the coverage lens's claim), shrank its recommendation to a note, which removes the clash by weakening one side, not by reconciling. In debate the risk lens defended the stronger fix.
4. case-03 T2 / case-23 T2 / case-09 T2 (debate CLASH, PTU COMP). Described in Q3: PTU findings carry the peer's constraint inside the finding (ARC-6 payload caveat, TST-4 fake-clock caveat, 4xx-fatal rule), debate findings leave the original recommendation standing next to a rebuttal.
5. Reverse direction (PTU worse): case-03 T1 and case-02 T2 (debate REC, PTU COMP). In case-03 T1 the PTU reuse finding ARC-4 omits the 24 h shared-instance TTL fact that the reconciliation relies on; the 30 minute default is in other findings. PTU findings frequently cross-reference rather than restate, and the judge requires one finding to cover both concerns.

## Q5. Judge-quality observations

- Non-unanimous votes (non-unanimous, strict 2-1, reconciled by 2-1): baseline 12, 11, 3 (one 1-1-1); second-round 6, 6, 1; debate 10, 10, 5; ptu 8, 8, 4. The 2-1 reconciled calls are within one or two tensions of the technique gaps (SR 44, debate 43, PTU 42), so individual reconciled counts cannot be separated by this judge in one rep.
- Same text, different label: case-25 T3 (above). Also case-18 T2 has three techniques at COMP with 3 of 3 non-unanimous votes in one technique (marker SSS); case-09 T2, case-02 T1, case-21 T3, case-26 T2 have double splits.
- "Reconciled" calls whose evidence admits a gap: PTU case-06 T2 ("It never mentions the auth.Tenant pin on that signature"), case-08 T1 ("does not mention compare_digest or the 600k iteration default"), case-13 T3 ("It does not name user.ValidatePassword"; and the reconciling lens is consistency, whose CON-4 omits the exported-function fact), case-18 T3 ("The verify check on graceEndsAt is carried only by reference to RSK-1, which is a weak point"). Debate case-08 T1 and case-06 T3 and SR case-30 T1 ("does not say that complete should reject stale pending rows") are in the same category. About a quarter of reconciled evidence strings contain such a caveat (debate 17/43, baseline 13/33, SR 13/44, PTU 9/42 by a loose regex), so PTU is not judged more leniently by this proxy.
- Strictness cuts the other way too: judge says compatible when facts are spread over several findings (case-22 T2 baseline/SR/debate, case-03 T1 PTU). The rule "one finding must cover (a), (b) and (c)" penalises distributed coverage.
- Clash determination depends on which finding is picked as the reconciler: case-22 T2 debate lists COV-3 as reconciling and COV-7 as the clash and then says neither counts ("COV-7 is not a clash"), leaving internally inconsistent structured fields (recon/clash populated while status is COMP).

## Q6. Technique leakage to a blind judge or labeller

Regex counts over final findings in the 24 tension cases (n findings: baseline 1001, SR 1106, debate 1019, PTU 1149):
- Finding text citing another lens's finding ID: baseline 0, second-round 232 (21%), debate 208 (20%), PTU 620 (54%).
- "round 1/round-1/round1": baseline 0, SR 99, debate 15, PTU 64.
- "peer(s)": baseline 0, SR 44, debate 63, PTU 232.
- "lens(es)" naming another lens: baseline 1, SR 83, debate 18, PTU 66.
- "N other lenses ... independently / same conclusion": baseline 0, SR 14, debate 9, PTU 45.
- Examples: SR case-16 COV-1 "All five lenses raised this in round 1"; SR case-06 ARC-6 "This is a blocker in four other lenses. I raise my severity to match"; debate case-15 ARC-1 "Four lenses independently flagged this as a blocker, so I am raising my ..."; debate case-22 CON-9 "This replaces my round-1 CON-9"; PTU case-13 ARC-6 "My round-1 claim that no fakes exist was wrong"; PTU case-09 RSK-8 "I accept it on the strength of three peers' consistent citation of output.ts. I did not read output.ts"; PTU case-09 CON-11 "the test lens will probably say more about it" (a prediction leaking into a finding).
- So baseline is trivially identifiable (no cross-references), and PTU is distinguishable from SR/debate by density of peer language and by prediction-flavoured phrasing; debate by "my earlier finding", "peers' fix of ... creates this problem". The judge sees these texts; the evidence strings in judge output also say things like "CON-1 itself defers to CON-9". Whether the judge was biased is unclear, but any human labelling on these texts is not blind. Stripping ID cross-references and "round/peer" sentences before judging would be needed for a blinded re-judge.

## Caveats
- One rep; 70 tensions; 3-vote judge with ~15% non-unanimous.
- "Similarity to baseline" for second-round/debate compares ids with the baseline round 1, which is valid since they reuse it; ids may be renumbered in round 2, so low similarity can mean renumbering. For PTU, baseline ids are not comparable (own round 1), so I did not use similarity for PTU.
- Strict 2-1 vs non-unanimous is defined by `votes` in the judge output (3 votes per tension).
