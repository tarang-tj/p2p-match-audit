# Three-way match audit

A procurement controls audit of a real ERP purchase-to-pay log: 251,734 purchase-order items and 1,595,923 events from one multinational company's 2018 purchasing (BPI Challenge 2019).

Before a supplier is paid, three documents should agree: the purchase order, the goods receipt and the invoice. This project checks how often that held, where it broke, and how long payment took. It answers the three questions the company's process owner posed with the dataset:

1. **Which process models describe the data?** Variants per matching rule (`src/p2p/variants.py`). Seven variants cover 80% of the 221,010 invoice-before-GR items.
2. **What is the invoice throughput, matching receipts to invoices to payments?** An order-based matcher (`src/p2p/matching.py`, rules in `docs/matching.md`).
3. **Which purchases stand out?** Fourteen controls across conformance, purchasing discipline, rework and segregation of duties (`src/p2p/controls.py`, definitions in `docs/controls.md`).

Findings memo: [`docs/findings.md`](docs/findings.md). What the data cannot show: [`docs/data-quality.md`](docs/data-quality.md).

## Run

```bash
pip install pandas pyarrow lxml flake8   # Python 3.9+
npm install && npx playwright install chromium-headless-shell
# Put BPI_Challenge_2019.xes in data/raw/ (source in docs/data-quality.md)
make data      # parse XES to parquet (~30 s)
make gate      # lint, tests, audit, reconcile, memo trace, browser probe
python3 -m http.server -d web 8000   # open http://localhost:8000
```

## The gate

`make gate` runs every step below; a partial run does not count.

| Step | What it proves |
|---|---|
| lint | flake8 over src, scripts, tests |
| test | 20 unit tests on hand-built items with known answers. Seven planted bugs (ignoring GR reversals, UTC instead of local dates, skipping invoice cancellations, and others) each turn the suite red |
| audit | Rebuilds every output from the parquet files; byte-identical across runs |
| reconcile | Parsed log equals the publisher's stated counts exactly; each item lands in exactly one flow; no control has more exceptions than items |
| memo | Every number in docs/findings.md traces to out/summary.json |
| site | Headless Chromium at 1440x900 and 375x812: the page renders the data file's numbers, every example tab draws its item, no console errors, no horizontal overflow |

## Layout

```
src/p2p/     load_log, features, controls, matching, variants, summarize, data_quality
scripts/     run_audit, reconcile, check_memo, build_site_data, verify_boot.mjs
tests/       unit tests and a 3-trace XES fixture
web/         static page (no build step); data/site.json is generated
docs/        findings memo, control definitions, matching rule, data quality
```

Values in the log are anonymized by linear scaling, so results are counts and shares of ordered value, never euros. Names of companies, vendors and users are the publisher's anonymized IDs. The source does not name the ERP product, and this project does not claim one.
