PY ?= python3
export PYTHONPATH := src:tests

.PHONY: data audit lint test reconcile memo site gate

data:
	$(PY) -m p2p.load_log data/raw/BPI_Challenge_2019.xes --out data

audit:
	$(PY) scripts/run_audit.py

lint:
	$(PY) -m flake8 --max-line-length 110 src scripts tests

test:
	$(PY) -m unittest discover -s tests

reconcile:
	$(PY) scripts/reconcile.py

memo:
	$(PY) scripts/check_memo.py

site:
	$(PY) scripts/build_site_data.py
	node scripts/verify_boot.mjs

# The only gate. A partial run does not count.
gate: lint test audit reconcile memo site
