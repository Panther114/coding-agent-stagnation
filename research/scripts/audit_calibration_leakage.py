"""How widespread is calibration against other readers' label files?

Some readers reported anchoring their conventions on earlier readers' outputs.  If that is common,
the annotation set carries correlated error: a reader that copies a convention inherits its
mistakes instead of averaging them out.  This scans every reader's reason text and any notes for
references to sibling label files, the gold file, or other readers' verdicts, and reports which
cards are affected.

Usage: python scripts/audit_calibration_leakage.py
"""
from __future__ import annotations

import collections
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = "data/annotations/tb2"

PATTERNS = {
    "sibling label file": re.compile(r"labels_(?:dense|refine|p2|r\d)[\w]*\.csv", re.I),
    "gold file": re.compile(r"adjudicated\.csv", re.I),
    "another reader": re.compile(r"labels_dense_\d+|labels_refine_\d+|labels_p2_s\d+", re.I),
    "agreement stats": re.compile(r"agreement\.json|cross_round|cohen_kappa", re.I),
    "gold regions": re.compile(r"gold_regions|cards_index\.csv", re.I),
}

files = [f for f in sorted(os.listdir(D)) if f.startswith("labels_") and f.endswith(".csv")]
hits = collections.defaultdict(list)
cards = collections.defaultdict(set)
for f in files:
    txt = open(os.path.join(D, f), encoding="utf-8", errors="replace").read()
    for tag, pat in PATTERNS.items():
        found = pat.findall(txt)
        if found:
            hits[tag].append((f, len(found)))
            try:
                for r in csv.DictReader(open(os.path.join(D, f), encoding="utf-8")):
                    if r.get("card_id"):
                        cards[tag].add(r["card_id"])
            except Exception:
                pass

print(f"reader files scanned: {len(files)}")
for tag in PATTERNS:
    fs = hits.get(tag, [])
    print(f"  {tag:20} files={len(fs):3d}  cards in those files={len(cards.get(tag, ())):5d}")
    for f, n in fs[:6]:
        print(f"      {f} ({n} mentions)")

# how many gold windows carry a label produced by a reader that referenced another file?
adj = list(csv.DictReader(open(os.path.join(D, "adjudicated.csv"), encoding="utf-8")))
allref = set()
for tag in PATTERNS:
    allref |= cards.get(tag, set())
touched = [a for a in adj if a["card_id"] in allref]
print(f"\ngold windows whose card was labelled in a file that references another file: "
      f"{len(touched)} of {len(adj)} ({100*len(touched)/max(1,len(adj)):.1f}%)")
multi = [a for a in touched if int(a["n_reads"]) > 1]
tied = [a for a in multi if a["gold"] == "UNCERTAIN"]
print(f"  of those, multiply read: {len(multi)}, tied: {len(tied)}")
