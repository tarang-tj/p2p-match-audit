# Matching receipts, invoices and payments

The challenge's second question: when one item has several goods receipts and several invoices, which belong together, and how long does payment take? Code: `src/p2p/matching.py`. Tests: `tests/test_matching.py`.

## Rule

1. A cancellation reverses the most recent open document of its kind. Cancel Goods Receipt removes the latest receipt; Cancel Invoice Receipt removes the latest invoice.
2. The k-th surviving invoice pairs with the k-th surviving goods receipt. On invoice-before-GR items the invoice may come first, giving a negative receipt-to-invoice lag.
3. Each Clear Invoice pairs with the earliest surviving, uncleared invoice recorded at or before it. A clearing with no open invoice is counted as unmatched. In the log this is usually the clearing of a reversal: invoice, cancel, clear, re-enter, clear.
4. Payable time = the later of the paired receipt and invoice. Time to pay = clearing minus payable time.

Amounts are not used because the per-event value field does not hold invoice amounts (see data-quality.md).

## Baseline it beats

First receipt to last clearing per item, which is what a simple dashboard computes. On 1,915 items with two or more paid invoices, that gives a median of 94.0 days; the matched per-invoice median is 32.1 days.

## Known limits

- Order-based pairing assumes the vendor bills receipts in sequence. If a vendor invoices the second delivery before the first, the lags of those two invoices swap, but the item's totals are unchanged.
- After a reversal, the re-entered invoice pairs with the first surviving receipt, so its receipt-to-invoice lag can look long. Example: item 2000000005_00001 on the web page.
- 4,524 items have at least one unmatched clearing; they are counted, not dropped.
