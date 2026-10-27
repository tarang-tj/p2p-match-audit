# Matching receipts, invoices and payments

The challenge's second question: when one item has several goods receipts and several invoices, which belong together, and how long does payment take? Code: `src/p2p/matching.py`. Tests: `tests/test_matching.py`.

## Rule

1. A cancellation reverses the most recent open document of its kind. Cancel Goods Receipt removes the latest receipt; Cancel Invoice Receipt removes the latest invoice.
2. The k-th surviving invoice pairs with the k-th surviving goods receipt. On invoice-before-GR items the invoice may come first, giving a negative receipt-to-invoice lag.
3. Events are applied in time order. A Clear Invoice that follows a Cancel Invoice Receipt, before any new invoice is recorded, is the clearing of the reversal and stays unmatched; it cannot take an older open invoice. Any other clearing pairs with the earliest invoice still open at that moment. If a cancelled invoice had already been cleared, that clearing also becomes unmatched.
4. Record Subsequent Invoice counts as an invoice (it can be cleared) but takes no goods-receipt slot.
5. Payable time = the later of the paired receipt and invoice. Time to pay = clearing minus payable time. For 3-way items, only invoices paired with a receipt enter the timing figures.

Amounts are not used because the per-event value field does not hold invoice amounts (see data-quality.md).

## Baseline it beats

First receipt to last clearing per item, which is what a simple dashboard computes. On 1,860 items with two or more paid, receipt-paired invoices, that gives a median of 94.1 days. The median over their 6,502 invoices, each measured from payable to cleared, is 34.3 days.

## Known limits

- Order-based pairing assumes the vendor bills receipts in sequence. If a vendor invoices the second delivery before the first, the lags of those two invoices swap, but the item's totals are unchanged.
- After a reversal, the re-entered invoice pairs with the first surviving receipt, so its receipt-to-invoice lag can look long. Example: item 2000000005_00001 on the web page.
- 6,169 items have at least one unmatched clearing (7,313 clearings in all), counted per item, including items whose invoices were all reversed.
