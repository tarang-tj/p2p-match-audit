"""Gate: every number in docs/findings.md must come from the audit outputs.

Collects every numeric value in out/summary.json (and the breakdown CSVs it
embeds) in the formats a writer would use, then fails on any number in the
memo that is not among them, unless it is on the short allowlist below with
a reason.
"""
import json
import re
import sys
from pathlib import Path

ALLOW = {
    "2018": "year of the data",
    "2019": "dataset name",
    "1948": "earliest event year; data_quality.time_window.first_event",
    "0550": "vendor id", "0246": "vendor id", "0000": "user id", "0003": "company id",
    "3": "count of findings in prose",
}
NUM = re.compile(r"(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")


def leaves(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from leaves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from leaves(v)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield obj


def forms(x):
    out = {str(x)}
    if float(x).is_integer():
        out |= {f"{int(x):,}", str(int(x))}
    for d in (1, 2):
        out.add(f"{x:.{d}f}")
        out.add(f"{x * 100:.{d}f}")  # ratios stored as 0..1
    return out


def main() -> int:
    summary = json.loads(Path("out/summary.json").read_text())
    known = set()
    for v in leaves(summary):
        known |= forms(v)
    known |= {k.split(".")[0] for k in ALLOW}
    memo = Path("docs/findings.md").read_text()
    missing = [n for n in NUM.findall(memo) if n not in known and n not in ALLOW]
    for n in missing:
        print("MEMO FAIL: number not traceable to out/summary.json:", n)
    if not missing:
        print(f"memo ok: {len(NUM.findall(memo))} numbers traced")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
