# Purchase-to-pay compliance review, 2018

To: Process owner, purchase-to-pay
From: Tarang Jammalamadaka
Data: BPI Challenge 2019 event log (one multinational coatings company, purchase orders submitted in 2018). 251,734 purchase-order items, 1,595,923 events, 76,349 purchase documents. Names and values are anonymized by the publisher, so this memo reports counts and shares of ordered value, never euros.

## Bottom line

The system-enforced part of three-way matching works: on items that require a goods receipt before invoicing, an invoice was never recorded first (0 of 15,182 items). The gaps sit where people can work around the system. Three are worth acting on. One spend area, Trading & End Products, is the largest contributor to the first two.

## Finding 1: orders raised after the invoice

3,693 items (1.47%) carry a vendor invoice dated before the purchase-order item existed. They hold 4.98% of ordered value. This is the classic after-the-fact PO: the order documents a purchase that already happened, so the approval it represents came too late to stop anything.

It is concentrated, not spread out. One vendor, vendorID_0550, accounts for 1,215 of the 3,693 items, and 96.2% of that vendor's items were ordered after invoicing. All but one of them are trading products. By spend area, Trading & End Products has 1,472 such items, a 6.6% rate against 1.47% overall. Of the 3,693, 605 are 2-way items (billed without a goods receipt), all in one company, where invoice-first is close to how that flow is used.

Action: give vendorID_0550 a framework agreement or blanket order so the order exists before the invoice, and add an after-the-fact flag to the invoice-entry screen for trading products.

## Finding 2: invoices paid with no goods received

On 3-way items, an invoice should only be cleared once goods have arrived. 674 items (0.29% of 236,192 3-way items) had an invoice cleared with no surviving goods receipt, either because none was ever posted or because it was cancelled. A further 89 items were cleared before their first receipt. The share is small but the risk is direct: payment for goods that may never have arrived.

Trading & End Products again leads with 266 of the 674. One trading vendor, vendorID_0246, accounts for 232 of them (7.29% of its items) and also appears in the invoice-cancellation and after-the-fact lists.

Action: block clearing on 3-way items while net goods receipts are zero, and review vendorID_0246's open items first.

## Finding 3: one person recording an invoice and clearing it

2,526 items (1.00%) had the same person record the invoice and clear it for payment. These conflicts come from 15 people, and the busiest accounts for 29.91% of them. Separately, 3,825 items had the same person create the order and record the goods receipt, across 46 people. No one both created an item and recorded its invoice.

One account was excluded first. user_000 creates purchase-order items in the same minute as the shopping-cart system in 99.31% of its cases, so it behaves like an interface, not a person. Counting it would have raised the create-and-receive figure to 5,149.

Action: remove the clearing permission from the 15 invoice clerks, or route their manual clearings through a second approver. For create-and-receive, check whether the 46 users are small-site buyers who also run receiving, which may be an accepted, documented exception.

## Payment timing

Payment is a weekly run: 75.06% of clearings happen on a Thursday, and one account performs 85.58% of all clearings, on just 94 days. Once an item is payable (the later of receipt and invoice), the median wait to clearing is 28.0 days on invoice-after-GR items and 42.1 days on invoice-before-GR items.

Invoices whose payment block had to be removed clear later: 37.5 days against 24.1 on invoice-after-GR items, and 50.8 against 37.9 on invoice-before-GR items. The log does not record why a block was set, so this is an association, not a cause. On invoice-after-GR items a block cannot mean "waiting for goods", which points to price or quantity mismatches.

Method matters here. On 1,915 items with several paid invoices, measuring first receipt to last payment gives a median of 94.0 days. Matching each invoice to its own receipt and payment gives 32.1 days. A dashboard built on the first method would report recurring-billing items as badly late when they are not.

## What this data cannot show

Amounts cannot be matched. The challenge description says invoice values on an item add up to the item's worth. In the file, 99.15% of invoice events repeat the item's value, and of 9,644 items with two or more invoices only 6 add up. Every check in this memo therefore uses counts and dates. A value-based three-way match needs the source system's invoice amounts.

Also: 318 events predate 2018 (the earliest is 1948), 25.01% of events have no recorded user, and the reason behind a payment block is not in the log.
