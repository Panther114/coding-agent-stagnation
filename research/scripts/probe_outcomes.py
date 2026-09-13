"""What execution-outcome signals exist in the raw data?

Skips trials whose `steps` field is null (many are), and reports signal prevalence over real steps.
"""
from __future__ import annotations

import collections
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import pyarrow.parquet as pq

RAW = "data/raw/tb2/train-00000-of-00002.parquet"
pf = pq.ParquetFile(RAW)
print(f"raw shard: {pf.metadata.num_rows} trials")

SIGNALS = {
    "returncode_tag": re.compile(r"<returncode>\s*(-?\d+)\s*</returncode>", re.I),
    "exit_kw": re.compile(r"\{exit=(-?\d+)\}"),
    "exit_word": re.compile(r"exit[_ ]?(?:code|status)[=: ]+(-?\d+)", re.I),
    "pytest_passed": re.compile(r"\b(\d+)\s+passed\b", re.I),
    "pytest_failed": re.compile(r"\b(\d+)\s+failed\b", re.I),
    "error_summary": re.compile(r"ERROR SUMMARY:\s*(\d+)\s*errors?", re.I),
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "segfault": re.compile(r"Segmentation fault|SIGSEGV", re.I),
    "build_ok": re.compile(r"build (?:succeeded|complete|completed successfully)", re.I),
    "tests_ok": re.compile(r"\b(?:all tests passed|tests? (?:passed|ok))\b", re.I),
    "no_leaks": re.compile(r"definitely lost:\s*0 bytes", re.I),
    "solved_marker": re.compile(r"Hello,\s*CompCert|solution\.txt", re.I),
}

counts = collections.Counter()
steps_seen = 0
valid_rows = 0
null_rows = 0
for batch in pf.iter_batches(batch_size=64, columns=["trial_name", "steps", "reward"]):
    for r in batch.to_pylist():
        blob = r.get("steps")
        if not blob:
            null_rows += 1
            continue
        try:
            steps = json.loads(blob)
        except Exception:
            null_rows += 1
            continue
        if not steps:
            null_rows += 1
            continue
        valid_rows += 1
        for s in steps:
            if not isinstance(s, dict):
                continue
            text = str(s.get("obs") or "") + "\n" + str(s.get("msg") or "")
            steps_seen += 1
            for name, pat in SIGNALS.items():
                if pat.search(text):
                    counts[name] += 1

print(f"trials with usable steps: {valid_rows}   null/empty: {null_rows}")
print(f"steps scanned: {steps_seen}")
print("\nsignal prevalence across steps:")
for name in SIGNALS:
    n = counts[name]
    print(f"  {name:16} {n:7d}  ({100*n/max(1,steps_seen):5.2f}%)")

print("\nis ANY execution signal present in most trials?")
