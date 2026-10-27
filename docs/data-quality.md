# Data source and quality

## Source

van Dongen, B.F., Dataset BPI Challenge 2019, 4TU.Centre for Research Data, https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1. Challenge description: https://icpmconference.org/2019/?p=302.

On 2026-10-26, data.4tu.nl did not respond on IPv4 or IPv6, so the XES file was taken from a Kaggle mirror (`aaminaalzeri/bpi-challenge-2019-dataset`, file `BPI_Challenge_2019.xes`, 728,558,522 bytes, SHA-256 `af63bc687fc4152f2123b05c3af7772b37ef3fce2d3f67f812666c9e356baae7`). A mirror can be altered, so `scripts/reconcile.py` checks the parsed log against every figure the publisher states: 251,734 items, 1,595,923 events, 76,349 purchase documents, 42 activities, 607 human and 20 batch users. All match exactly.

License: Creative Commons Attribution 4.0 International (CC BY 4.0), per the DOI's DataCite record (api.datacite.org, rightsIdentifier `cc-by-4.0`), checked 2026-10-26 while data.4tu.nl was down. Changes made: the log was parsed and aggregated; the page and outputs publish counts, shares and six example items, not the raw log.

## What the log cannot support

- **Invoice amounts.** The challenge text says event values sum to the item's worth. In the file, 99.15% of invoice events carry the item's value itself, 98.16% of items have one value on every event, and of 9,644 items with two or more invoices only 6 have invoice values that sum to the item value. Matching therefore uses counts and dates only.
- **Euros.** Values were anonymized by a linear scaling, so only shares of total value are meaningful.
- **Block reasons.** Set Payment Block appears 124 times, while Remove Payment Block appears 57,136 times. Most blocks were set by a step the log does not show, and no reason code is recorded.
- **Dates outside 2018.** 318 events predate 2018 (earliest 1948) and 382 items were created outside 2018. They are kept and disclosed.
- **Users.** 25.01% of events have user NONE: 55.1% of these are vendor invoice dates and 41.3% service entry sheets.

## ERP vendor

The source does not name the ERP product. Activity names ("SRM: ...", "GR-Based Inv. Verif.") look like a standard ERP with a supplier-relationship front end, but this project does not claim a vendor.
