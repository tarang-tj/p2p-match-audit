# Code review: p2p-match-audit @ 3d55308

Scope: src/p2p/*.py, scripts/*.py, scripts/verify_boot.mjs, web/app.js, web/flow-chart.js, tests/*.py, docs/controls.md, docs/matching.md. Read-only. Every finding was checked against data/*.parquet with throwaway scripts (not committed).

## Overall

Most controls match docs/controls.md exactly. These checks came back clean: timezone handling for after_the_fact_po (all 219,919 vendor-invoice events are 23:59 Amsterdam, at both 21:59 and 22:59 UTC), NaT comparisons, the `.where(applies)` NaN denominators, the sort by (timestamp, seq) (file order never goes back in time, so seq breaks ties correctly), and the SoD role sets. The problems are in how some numbers are labeled or what they are divided by, one gap in a matching rule, and one test that cannot fail.

## High

H1. The SoD rates use every item as the denominator, which breaks the doc's own denominator rule.
- src/p2p/controls.py:113 (SoD series are never `.where`-masked) -> summarize.py:36-41.
- docs/controls.md:3 says an item outside "Applies to" is "not applicable, never as passing". SoD gives every one of the 251,734 items a False when it can't conflict, including consignment, never-invoiced and batch-only items.
- Real data: sod_invoice_and_clear has 2,526 / 251,734 = 1.00% (published in findings.md Finding 3). Only 169,525 items have a human in both roles, which gives 1.49%. sod_create_and_receive is 3,825 / 251,734 = 1.52%, against 2.09% on the 183,031 items that have a human creator and a human receiver.
- Fix: `applies = roles[left].map(bool) & roles[right].map(bool)` after reindex, return `flag.where(applies)`, and state "Applies to" in the SoD table in controls.md.

H2. `test_clean_item_trips_nothing` cannot fail for 8 of its 14 columns.
- tests/test_controls.py:75 `any(v is True for v in row)`. The rows hold `numpy.bool_`, and `np.True_ is True` is False.
- Shown on the "sod" row, which has 3 True flags: `any(v is True ...)` returns False. Columns after_the_fact_po through sod_* are all `bool_`.
- Fix: `self.assertFalse((row == True).any())`.

## Medium

M1. The "matched per-invoice median 32.1 days" is a median of per-item medians, not a per-invoice median.
- summarize.py:80-87; docs/matching.md:16, docs/findings.md:41, web/app.js:121 all call it per invoice.
- Real data, same 1,915 items: the pooled per-invoice median ready_to_clear is 34.0 days over 6,681 invoices. 32.1 is the median of item medians.
- The naive 94.0 is roughly comparable: the span over matched pairs only gives 93.2. Fix: report the pooled 34.0, or rename the figure to "median of per-item medians".

M2. Matching rule 3 lets a reversal's clearing take an older live invoice.
- matching.py:51-56. Clearings are matched only after every cancellation has already been applied, against the final surviving list. So the "invoice, cancel, clear, re-enter, clear" clearing that docs/matching.md:9 says comes out unmatched only does so when no older open invoice exists.
- Real data: 2,020 clearings fall within 10 minutes after a Cancel Invoice Receipt with no invoice in between. 222 of them, on 209 items, are paired to a surviving invoice. Example 2000000047_00001: Cancel IR 2018-02-27 13:34, Clear 13:35. That clearing is assigned to an earlier open invoice, and every later clearing on the item shifts by one slot.
- Effect on headline medians: small (222 of 187,240 cleared). The per-item pairings and lags on those items are wrong.
- Fix: run one pass in time order. Clear against invoices open at that moment, and on Cancel IR remove the latest invoice; if it was already cleared, release its clearing as unmatched. Add a test with two open invoices plus a reversal.

M3. block_effect labels each item as blocked or not, but the memo describes invoices.
- summarize.py:109 `blocked = n_unblock > 0` marks every invoice on the item as blocked. findings.md:39 says "Invoices whose payment block had to be removed".
- Real data: 2,673 of the 51,884 "blocked" cleared invoices sit on items with more cleared invoices than Remove Payment Block events.
- Fix: reword it as "invoices on items with a removed block", or attach each unblock to an invoice by time.

## Low

L1. cleared_without_gr uses net_gr at the end of the log, but the doc says "while" (controls.py:42).
- 735 items had a clearing while their running net GR was <= 0. Only 1 of those is missed by both conformance controls: 4507041862_00020 (GR, cancel, IR, clear 11-08, GR 11-19).
- About 28 flagged items had a receipt at clearing time that was cancelled afterwards.
- Fix: reword the doc ("at the end of the log") or test at clearing time.

L2. Record Subsequent Invoice takes a GR slot in k-th pairing (matching.py:40). 167 events on 159 items; Cancel IR pops a subsequent invoice 9 times. This is undocumented and the numbers are negligible.

L3. Invoices with no paired GR still count in ready_to_clear: 148 cleared invoices on 3way_after_gr and 476 on 3way_before_gr. For them ready = ir (matching.py:81, DataFrame.max skips NaT). throughput_table (summarize.py:62) mixes these in, while naive_vs_matched drops them.

L4. build_site_data matches examples on CORE events (no SUBSEQUENT_INVOICE, scripts/build_site_data.py:55,73), while the audit uses `_RELEVANT`. None of the 6 current examples is affected, but the two can diverge.

L5. Text on the page that doesn't come from the data:
- app.js:20 says "`${ex.pairs.length}` receipts, each matched to its own invoice and payment". pairs.length is the number of surviving invoices, and they need not all be cleared or have a GR. It is true for 2000000014_00001 only by chance.
- app.js:94 ("No one both created an item and recorded its invoice") and app.js:118 ("about two weeks later") are hard-coded. That goes against the file's header ("nothing typed in by hand"), and the gate cannot catch them going stale.

L6. innerHTML interpolation: app.js:65 (c.title, c.family), :90 (interface user names taken from the log), :100 (label/sub), :116-138. All of it comes from our own JSON, so there is no exploit today. The user names are log-derived strings, so `textContent` or escaping would be safer if the input ever changes.

L7. check_memo.py:34-41 accepts any memo number that appears anywhere in summary.json (including x100 and 1-2 decimal forms). A wrong number that happens to match an unrelated leaf passes. Example: "15 people" would also pass from any value 15 or 0.15.

## Verified clean
- after_the_fact_po: local-date comparison is correct in winter and summer. No item lacks Create PO (0 NaT first_po).
- ir_before_gr_gr_based = 0 / 15,182 is real. No 3-way-after item has only a subsequent invoice.
- Cancels with nothing open (1,077 GR, 867 IR) are no-ops in matching and give net < 0 in features (1,044 / 837 items). Every control treats that correctly (<= 0 and > 0 tests).
- cleared_without_gr (674) and cleared_before_gr (89) don't overlap, so "a further 89" in the memo is correct.
- value_share_pct denominator = all-item value (996,818,747; no NaN or negative values). This matches "share of ordered value" in the memo.

**Status:** DONE_WITH_CONCERNS
**Summary:** Controls compute what the doc says, but SoD rates use all items as the denominator (1.00% vs 1.49%) and a test cannot fail. "Per-invoice 32.1 days" is actually a median of item medians (pooled 34.0), and matching rule 3 misassigns 222 reversal clearings.
**Concerns/Blockers:** No source files were modified. I did not run `make gate` again; numbers come from rebuilding facts/matched from the parquet files with current code.
