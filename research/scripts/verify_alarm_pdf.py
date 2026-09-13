"""Verify the alarm result renders in the PDF, and report where the paper's length sits."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import pypdf

PAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "paper")
PAPER = os.path.normpath(PAPER)

r = pypdf.PdfReader(os.path.join(PAPER, "main.pdf"))
flat = re.sub(r"\s+", "", "".join((p.extract_text() or "") for p in r.pages)).lower()
print(f"pages: {len(r.pages)}")
checks = [
    ("alarm section", "calibratedstagnationalarm"),
    ("detection 53", "53"),
    ("nested 56", "56"),
    ("fa 17", "17"),
    ("fa 18", "18"),
    ("latency 0", "latencyof0steps"),
    ("target met", "betterthanhalftheepisodesdetected"),
    ("two-in-five missed", "twoinfivearemissed"),
    ("adjacent window overlap", "adjacentwindowsoverlap"),
]
for label, key in checks:
    print(f"  {label:26} {'FOUND' if key in flat else 'MISSING'}")

print("\nsource line counts:")
for fn in sorted(os.listdir(PAPER)):
    if fn.endswith(".tex"):
        n = sum(1 for _ in open(os.path.join(PAPER, fn), encoding="utf-8"))
        print(f"  {fn:28} {n:>5}")
