# Verifier report: p2p-match-audit (2026-10-26)

Scratch scripts (written from scratch, no import of src/p2p except where noted as the comparison side):
/private/tmp/claude-501/-Users-tarangjammalamadaka/08158cf1-a8e5-449d-a916-bd0a56aa8ff2/scratchpad/{raw_count.py,indep.py,chk2.py,mv3.py,pick.py,q.py}

## 1. Commit and gate
VERIFIED. `git log --oneline -5` -> `3d55308 feat: three-way match audit of the BPI 2019 purchase-to-pay log` (only commit). `git status --short | wc -l` -> 0 before and after the gate.
`make gate` -> EXIT=0. Tail: flake8 clean; `Ran 20 tests ... OK`; `reconcile ok: {'items': 251734, 'events': 1595923, 'purchase_documents': 76349, 'activities': 42, 'human_users': 607, 'batch_users': 20}`; `memo ok: 63 numbers traced`; `boot ok: desktop 1440x900 and mobile 375x812`.
Byte-identical outputs: out/*.csv, out/summary.json, web/data/site.json are tracked and the tree stayed clean after the gate rebuilt them.
Tests have teeth (mutations in a scratch copy): ignore Cancel GR -> FAILED; ignore Cancel IR -> FAILED; drop `t <= clr` -> FAILED; Amsterdam->UTC in features.py -> FAILED. Baseline OK.

## 2. Publisher counts
VERIFIED. Fetched https://icpmconference.org/2019/?p=302: "76,349 purchase documents", "251,734 items", "1,595,923 events", "42 activities", "627 users (607 human users and 20 batch users)".
Raw XES regex count: traces 251734, events 1595923, activities 42, user_ 607, batch_ 20 (plus NONE). Purchasing Document distinct = 76350 including the header global default "UNKNOWN", so 76,349 real. Parquet matches identically.

## 3. Findings numbers (independent pandas)
a VERIFIED: 3,693; vendorID_0550 1,215 of 1,263 = 96.2%; 605 2-way, all companyID_0003; TEP 1,472 of 22,292 = 6.6%.
b VERIFIED: 674; TEP 266; vendorID_0246 232 (of 3,182 = 7.29%).
c VERIFIED: 2,526 items, 15 users; create+GR 3,825 (46 users) excl user_000, 5,149 incl; create+IR 0.
d VERIFIED: 99.31% of 1,439 user_000 creates.
e VERIFIED: Thursday 75.06% of 194,393; user_002 85.58% on 94 Amsterdam days.
f VERIFIED: 99.15%; 9,644 items with 2+ IR, 6 within 1.0.
g VERIFIED: 0 of 15,182.

## 4. Matching
Hand-paired 3 items (2000000157_00002, 4507003646_00010, 2000000047_00001 first 3 clears and 05-28 cancel chain): identical to project match_case. All 6 site.json examples match my matcher incl. unmatched counts. My matcher reproduces 1,915 items, naive 94.0, matched 32.1 (median of per-item medians, GR-paired invoices only), cleared counts 297/13,110/173,833.
REFUTED: docs/matching.md "4,524 items have at least one unmatched clearing; they are counted, not dropped." Actual 6,046 items (7,153 clearings). 1,522 items whose invoices were all reversed (1,902 clearings) are dropped, because run_audit.py:75-76 counts from the per-surviving-invoice frame.
Undocumented: the rule includes "Record Subsequent Invoice" as an invoice; matching.md does not say so (without it: 2,256 items, 93.7, 33.2).

## 5. Wording
- findings.md F3 "the busiest accounts for 29.91% of them": 786/2,628 user-item pairs; per item it is 786/2,526 = 31.12%.
- findings.md F1 "All but one of them are trading products": all 1,215 are trading; the "one" is among the vendor's other 48 items.
- "605 ... all in one company": every 2-way item in the log (1,044) is companyID_0003, so trivially true.
- Causal/speculative: "the approval it represents came too late to stop anything"; "which points to price or quantity mismatches" (the same memo says block reasons are not in the log); "The system-enforced part ... works" (0 count is consistent, not proof of enforcement).
- No ERP vendor named (grep SAP/Oracle: none).
Not checked: block-effect medians (37.5/24.1/50.8/37.9), variants claim (7 variants / 80%), 4.98% value share.

## Pass 2 (commit f827595)

Scripts: /private/tmp/claude-501/-Users-tarangjammalamadaka/08158cf1-a8e5-449d-a916-bd0a56aa8ff2/scratchpad/{p2match.py,sod2.py,mutate_copy.py}. p2match.py is written from the matching.md rule text and has two readings of rule 3: `flag` (word for word) and `counter` (one unmatched clearing per cancellation).

1. VERIFIED. `make gate` -> `Ran 23 tests ... OK`, `reconcile ok`, `memo ok: 67 numbers traced`, `boot ok`, EXIT=0; the tree is clean afterwards.
2. Matching.
   - REFUTED (doc vs code, narrow): rule 3 says "A Clear Invoice that follows a Cancel Invoice Receipt, before any new invoice is recorded, is the clearing of the reversal and stays unmatched". The code (`pending_reversals += 1` / `-= 1`) marks only ONE clearing per cancellation as unmatched. Any later clearings before a new invoice still take older open invoices. Example 4507000238_00150: IR 01-23, IR 02-10, Cancel IR 02-22, then Clear 03-08, 03-15, 04-05. Read word for word, all 3 clearings are unmatched; the code leaves only 1 unmatched. 230 items differ between the two readings.
   - With the doc read word for word: 6,169 items, 7,554 unmatched clearings, 1,850 items, naive median 94.07, 6,454 invoices, per-invoice median 34.76, block medians 38.5/24.1.
   - The suite stays GREEN when I mutate the code to the word-for-word reading (`pending_reversals = 1`, no decrement), so no test pins this choice.
   - Rules 1, 2, 4 and 5 match the code.
   - VERIFIED, published numbers under the code's (counter) reading: 6,169 items, 7,313 clearings; 1,860 items; naive median 94.09 (94.1); 6,502 invoices; median 34.32 (34.3).
3. VERIFIED. Invoice + clear: 169,525 items, 2,526 conflicts (1.49%), 15 users, top user_015 at 31.12%. Create + receive: 3,825 of 183,031 (2.09%), 46 users. Create + invoice: 0 conflicts out of 187,369.
4. VERIFIED. Block medians: after GR 38.9 (n 3,193) vs 24.1 (n 9,696); before GR 50.85 (exact 50.8476, so 50.8) vs 37.92 (n 48,124 / 125,135). Throughput: 28.0 (n 12,889) and 42.17 (n 173,259), matching out/throughput.csv.
5. VERIFIED. Nine planted bugs: run on a scratch copy (mutate.py chdirs into the real repo and rewrites its files, so I pointed a copy of it at /scratchpad/mut2). Result: all 9 RED, restored GREEN, and the copy is identical to the repo src afterwards. The after-the-fact value share is 4.98%, recomputed.
   Remaining wording issues, minor: "Clearing runs weekly" is stated as fact on a 75% Thursday share; "would report recurring-billing items as badly late when they are not" asserts lateness is not real.
   Still not checked: README "Seven variants cover 80% of the 221,010 invoice-before-GR items".

**Status:** DONE_WITH_CONCERNS
**Summary:** Gate green (23 tests, 9/9 mutations red), and every published Pass-2 number reproduces exactly with my own code under the code's reading of rule 3. matching.md rule 3 describes a different behaviour from the code, and the tests do not tell the two apart.
**Concerns/Blockers:** REFUTED: matching.md rule 3 wording vs code (one unmatched clearing per cancellation; 230 items, 241 clearings differ). UNVERIFIABLE: README variants claim. No cross-model review run.
