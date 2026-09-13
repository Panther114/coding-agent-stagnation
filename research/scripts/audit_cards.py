"""Audit the generated annotation cards for bytes that break text readers.

One reader reported that a card contained a stray NUL byte, which made the read tool treat the
file as binary.  If that is not isolated, some readers may have seen truncated cards.  This
script measures how widespread it is and whether affected cards show more disagreement in the
gold labels.

Usage: python scripts/audit_cards.py
"""
from __future__ import annotations

import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

CARDS = "data/annotations/tb2/cards_dense"
BAD_BYTES = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x0b, 0x0c, 0x0e, 0x0f}


def main() -> None:
    names = sorted(f for f in os.listdir(CARDS) if f.endswith(".md"))
    print(f"cards: {len(names)}")
    offenders = []
    for n in names:
        with open(os.path.join(CARDS, n), "rb") as fh:
            data = fh.read()
        hits = {b for b in BAD_BYTES if b in data}
        if 0x00 in hits:
            offenders.append((n, len(data), data.count(0x00), data.index(0x00)))
        elif hits:
            offenders.append((n, len(data), 0, -1))
    print(f"cards containing control bytes: {len(offenders)}")
    for n, size, zeros, off in offenders[:20]:
        print(f"  {n:56} size={size:7d} NULs={zeros:3d} first_at={off}")
    if not offenders:
        return

    # does the contamination correlate with label disagreement?
    adj = {a["card_id"]: a for a in csv.DictReader(
        open("data/annotations/tb2/adjudicated.csv", encoding="utf-8"))}
    bad_ids = {os.path.splitext(n)[0] for n, _, _, _ in offenders}
    stats = {}
    for tag, ids in (("contaminated", bad_ids),
                     ("clean", {os.path.splitext(n)[0] for n in names} - bad_ids)):
        rows = [a for a in adj.values() if a["card_id"] in ids]
        multi = [a for a in rows if int(a["n_reads"]) > 1]
        tied = [a for a in multi if a["gold"] == "UNCERTAIN"]
        stats[tag] = (len(rows), len(multi), len(tied))
        print(f"  {tag:14} gold windows={len(rows):4d}  multiply read={len(multi):3d}  "
              f"tied={len(tied):3d}  tie rate={100*len(tied)/max(1,len(multi)):.1f}%")
    print("\nA tie rate for contaminated cards much higher than for clean ones would mean the")
    print("bad bytes hurt the labels; a similar rate means the defect was cosmetic.")


if __name__ == "__main__":
    main()
