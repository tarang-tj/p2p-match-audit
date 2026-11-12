# Control definitions

Each control is evaluated per purchase-order item (one XES trace). "Applies to" is the denominator; an item outside it is reported as not applicable, never as passing. Code: `src/p2p/controls.py`. Tests: `tests/test_controls.py`.

Net goods receipts = Record Goods Receipt minus Cancel Goods Receipt. Net invoices = Record Invoice Receipt plus Record Subsequent Invoice minus Cancel Invoice Receipt.

"Cancel Subsequent Invoice" is left out of net invoices on purpose. The log has 491 of them against only 167 "Record Subsequent Invoice" events, and 477 of the 491 occur on an item with no subsequent invoice open to cancel. Their position says what they are: the most common sequences are invoice receipt, then Cancel Subsequent Invoice, then one or two clearings (313 of them directly follow an invoice receipt and 428 are directly followed by a clearing). A real reversal would not be paid afterwards; an adjustment document (a credit or debit memo against the invoice) would. The challenge documentation does not define the activity, so this reading comes from event order, not from the source. Counting them as cancellations would create "cleared with no net invoice" exceptions on items whose invoice was paid.

## Conformance: does the item follow its own matching rule?

| Key | Exception when | Applies to | Why it matters |
|---|---|---|---|
| ir_before_gr_gr_based | First invoice receipt is earlier than the first goods receipt, or there is no receipt | 3-way, invoice after GR | GR-based invoice verification should make this impossible; 0 is consistent with the system enforcing it |
| cleared_without_gr | At the end of the log, at least one invoice was cleared and net goods receipts are zero | Both 3-way flows | Payment for goods with no surviving proof of delivery |
| cleared_before_gr | First clearing is earlier than the first goods receipt | Both 3-way flows | The block that should hold an early invoice did not hold |
| gr_on_2way | Any goods receipt | 2-way | Flow misclassified, or an unneeded step |
| invoice_on_consignment | Any invoice receipt or clearing | Consignment | Consignment is settled outside the PO |
| invoices_exceed_receipts | Net invoices greater than net receipts, with at least one receipt | Both 3-way flows | Review signal, not proof: partial invoicing can legitimately split one receipt |

## Purchasing discipline

| Key | Exception when | Applies to |
|---|---|---|
| after_the_fact_po | The first vendor invoice date is earlier than the PO item's creation date, both as Europe/Amsterdam calendar dates | All items |
| price_change_after_invoice | The last Change Price event is later than the first invoice receipt | All items |

Vendor invoice events are all stamped 23:59 Amsterdam time (219,919 of 219,919), so they carry a date only. Comparing UTC dates would misclassify items created just after local midnight; `tests/test_controls.py` pins this with a dedicated case.

## Rework and process

| Key | Exception when |
|---|---|
| invoice_cancelled | At least one Cancel Invoice Receipt |
| gr_cancelled | At least one Cancel Goods Receipt |
| payment_block_removed | At least one Remove Payment Block. Reported as process volume: on invoice-before-GR items the block is the designed way an early invoice waits for goods |

## Segregation of duties

A conflict needs one human user (named `user_NNN`) in both roles on the same item. Batch jobs, `NONE`, and interface accounts are excluded. The denominator is the items where a person performed both steps; elsewhere the control is not applicable.

| Key | Roles |
|---|---|
| sod_create_and_receive | Create Purchase Order Item and Record Goods Receipt |
| sod_create_and_invoice | Create Purchase Order Item and Record Invoice Receipt |
| sod_invoice_and_clear | Record Invoice Receipt and Clear Invoice |

Interface accounts are detected, not listed by hand (`data_quality.interface_users`): a human-named user with at least 100 PO creations, 95% or more of which fall in the same minute as an SRM shopping-cart event on the same item. In this log that is user_000 alone.

## In the browser

`web/audit.js` is the same 14 controls in JavaScript, so the live page can run them on a seeded random 5,000 items (`web/data/sample.json`, built by `scripts/build_sample.py`). The interface accounts ship with the sample, because they are detected on the full log and 5,000 items are too few to detect them. Two checks keep the port honest: the builder refuses a sample whose Python flags differ from the full-log run, and `tests/test_browser_parity.py` requires `audit.js` to give the Python answer on every flag of every sampled item and of 17 hand-built edge items. The first screen counts the 13 rule controls; payment_block_removed is process volume and is left out of that count.
