"""Re-attribute the rows that landed in labels_refine_20.csv under the wrong annotator.

Two annotators were given the same output path.  Their rows are all present, so no annotation was
lost --- the problem is attribution: the gold counts those 14 cards as having been read by
`labels_refine_20.csv` when a different annotator actually read them.  This splits the file into
two reader identities, which is what the gold builder keys on, while keeping every label.

Usage: python scripts/split_collided_batch.py [--apply]
"""
from __future__ import annotations

import collections
import csv
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = "data/annotations/tb2"
SRC = os.path.join(D, "labels_refine_20.csv")
DST = os.path.join(D, "labels_refine_20b.csv")
OWN = "dna-assembly"   # batch 20's own assignment


def main() -> None:
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    hdr = list(rows[0].keys())
    mine = [r for r in rows if OWN in r["card_id"]]
    other = [r for r in rows if OWN not in r["card_id"]]
    print(f"{SRC}: {len(rows)} rows -> {len(mine)} batch-20 rows, {len(other)} other-annotator rows")
    trajs = collections.Counter(r["card_id"].split("_tb2_")[-1].rsplit("_", 1)[0] for r in other)
    for t, n in trajs.items():
        print(f"  re-attributed: {t} ({n} rows)")

    if "--apply" not in sys.argv:
        print("\ndry run; pass --apply to split the file")
        return
    with open(SRC, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=hdr)
        w.writeheader()
        w.writerows(mine)
    with open(DST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=hdr)
        w.writeheader()
        w.writerows(other)
    print(f"\nwrote {len(mine)} rows to {SRC} and {len(other)} rows to {DST}")
    print("every label is preserved; only the reader identity changes")


if __name__ == "__main__":
    main()
