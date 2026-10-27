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
