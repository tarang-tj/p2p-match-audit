# Control definitions

Each control is evaluated per purchase-order item (one XES trace). "Applies to" is the denominator; an item outside it is reported as not applicable, never as passing. Code: `src/p2p/controls.py`. Tests: `tests/test_controls.py`.

Net goods receipts = Record Goods Receipt minus Cancel Goods Receipt. Net invoices = Record Invoice Receipt plus Record Subsequent Invoice minus Cancel Invoice Receipt.

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
