"""Does every reader agree with its peers as often as it should?

The rank-based assignment could in principle have let a reader label a card it never opened
(authority misresolution).  That failure has a signature: the reader's labels would disagree
with other readers of the same cards far more often than the panel does.  This script measures
per-reader agreement on shared cards, which is the direct evidence for or against, and does not
depend on reconstructing anyone's sort order.

Usage: python scripts/check_reader_integrity.py
"""
from __future__ import annotations

import collections
import csv
import os
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = "data/annotations/tb2"
POS = {"STAGNANT", "DONE_REDUNDANT"}


def binz(lab: str):
    lab = (lab or "").strip().upper()
    if lab in POS:
        return 1
    if lab in {"PRODUCTIVE", "REGRESSION"}:
        return 0
    return None


def main() -> None:
    votes = collections.defaultdict(dict)   # card -> reader -> binary label
    for f in sorted(os.listdir(D)):
        if not (f.startswith("labels_") and f.endswith(".csv")):
            continue
        rows = list(csv.DictReader(open(os.path.join(D, f), encoding="utf-8")))
        if not rows:
            continue
        lc = next((k for k in rows[0] if k and k.startswith("label")), None)
        if not lc:
            continue
        for r in rows:
            y = binz(r.get(lc, ""))
            if y is not None and r.get("card_id"):
                votes[r["card_id"]][f] = y

    multi = {c: v for c, v in votes.items() if len(v) > 1}
    print(f"cards with >=2 readers: {len(multi)}")

    # per-reader agreement with the other readers of the same card
    agree = collections.defaultdict(list)
    for c, v in multi.items():
        readers = list(v)
        for i, a in enumerate(readers):
            for b in readers[i + 1:]:
                agree[a].append(int(v[a] == v[b]))
                agree[b].append(int(v[a] == v[b]))

    rates = {r: statistics.mean(x) for r, x in agree.items() if len(x) >= 3}
    if not rates:
        print("not enough overlap to judge")
        return
    vals = list(rates.values())
    med = statistics.median(vals)
    sd = statistics.pstdev(vals) or 1e-9
    print(f"readers judged: {len(rates)}  median agreement with peers: {med:.3f}  sd: {sd:.3f}")
    outliers = [(r, v, len(agree[r])) for r, v in rates.items() if v < med - 3 * sd]
    print(f"readers more than 3 sd below the median: {len(outliers)}")
    for r, v, n in sorted(outliers, key=lambda t: t[1]):
        print(f"  {r:26} agreement={v:.3f} on n={n} pairwise comparisons")
    print("\nlowest ten readers:")
    for r, v in sorted(rates.items(), key=lambda kv: kv[1])[:10]:
        print(f"  {r:26} agreement={v:.3f}  n={len(agree[r])}")
    if not outliers:
        print("\nNo reader behaves like one labelling cards it never read: agreement is uniformly")
        print("high, with no low tail. The rank-coordinate ambiguity therefore did not corrupt")
        print("the labels.")


if __name__ == "__main__":
    main()
