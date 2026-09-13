"""Resolve the sort-order ambiguity in the rank-based card assignment.

Different string orderings (ASCII/ordinal vs culture-aware) disagree on some positions, so the
same "rank 3, 21, 39, ..." instruction can name different files.  This script works out, for
each reader file, which regime its card ids actually match -- evidence beats assumption.

Usage: python scripts/check_sort_regimes.py
"""
from __future__ import annotations

import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
CARDS = "data/annotations/tb2/cards_dense"


def ordinal(names):
    return sorted(names)


def natural(names):
    key = lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]
    return sorted(names, key=key)


def culture(names):
    # approximate .NET/PowerShell culture sort: case-insensitive, punctuation-light
    return sorted(names, key=lambda s: s.lower())


def main() -> None:
    names = [f for f in os.listdir(CARDS) if f.endswith(".md")]
    regimes = {"ordinal": ordinal(names), "natural": natural(names), "culture": culture(names)}
    print(f"cards: {len(names)}")
    base = regimes["ordinal"]
    for tag, order in regimes.items():
        same = sum(1 for a, b in zip(base, order) if a == b)
        print(f"  {tag:9} positions identical to ordinal: {same}/{len(names)}")
        # natural/culture may reorder; report the first few differences
        diff = [(i + 1, base[i], order[i]) for i in range(len(names)) if base[i] != order[i]][:3]
        for rank, a, b in diff:
            print(f"      rank {rank}: ordinal={a}  {tag}={b}")

    print("\nwhich regime does each reader file actually match?")
    rows = []
    for f in sorted(os.listdir("data/annotations/tb2")):
        if not (f.startswith("labels_dense_") and f.endswith(".csv")):
            continue
        ids = [r["card_id"] for r in csv.DictReader(
            open(os.path.join("data/annotations/tb2", f), encoding="utf-8"))]
        if not ids:
            continue
        pos = {os.path.splitext(n)[0]: i for i, n in enumerate(names)}
        idx = sorted(pos[i] for i in ids if i in pos)
        if not idx:
            rows.append((f, len(ids), "no ids resolved", "", ""))
            continue
        matches = []
        for tag, order in regimes.items():
            order_ids = [os.path.splitext(n)[0] for n in order]
            wanted = {order_ids[i] for i in range(len(order_ids)) if (i + 1) % 18 == 3}
            hits = sum(1 for i in ids if i in wanted)
            matches.append((tag, hits / max(1, len(ids))))
        best = max(matches, key=lambda t: t[1])
        rows.append((f, len(ids), best[0], f"{best[1]*100:.0f}%",
                     " ".join(f"{t}:{v*100:.0f}%" for t, v in matches)))
    print(f"  {'file':24}{'rows':>5}  {'best match':<10}{'hit':>5}   all regimes")
    for f, n, best, hit, allr in rows:
        print(f"  {f:24}{n:>5}  {best:<10}{hit:>5}   {allr}")


if __name__ == "__main__":
    main()
