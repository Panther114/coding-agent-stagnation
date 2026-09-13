"""Did readers apply the ``boundary`` flag consistently?

One reader stated an explicit rule (productive work immediately both before and after the
window); others used "the window mixes two phases".  This measures how much the flag varies
across readers, because a flag applied inconsistently cannot be used to exclude or reweight
windows.
"""
from __future__ import annotations

import collections
import csv
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = "data/annotations/tb2"


def main() -> None:
    per_reader = {}
    for f in sorted(os.listdir(D)):
        if not (f.startswith("labels_") and f.endswith(".csv")):
            continue
        rows = list(csv.DictReader(open(os.path.join(D, f), encoding="utf-8")))
        if not rows:
            continue
        bc = next((k for k in rows[0] if k and k.startswith("boundary")), None)
        if not bc:
            continue
        vals = [(r.get(bc) or "").strip().lower() for r in rows]
        vals = [v for v in vals if v in {"true", "false"}]
        if vals:
            per_reader[f] = sum(1 for v in vals if v == "true") / len(vals)

    rates = list(per_reader.values())
    if not rates:
        print("no boundary column found")
        return
    rates.sort()
    print(f"readers reporting a boundary flag: {len(rates)}")
    print(f"  min {rates[0]:.2f}  median {rates[len(rates)//2]:.2f}  max {rates[-1]:.2f}")
    print(f"  overall share of windows flagged boundary: "
          f"{sum(rates)/len(rates):.2f}")

    print("\nfive most boundary-heavy readers:")
    for f, r in sorted(per_reader.items(), key=lambda kv: -kv[1])[:5]:
        print(f"  {f:26} {r:.2f}")
    print("five least boundary-heavy readers:")
    for f, r in sorted(per_reader.items(), key=lambda kv: kv[1])[:5]:
        print(f"  {f:26} {r:.2f}")

    # is the flag unanimous on multiply-read cards?
    flags = collections.defaultdict(set)
    for f in sorted(os.listdir(D)):
        if not (f.startswith("labels_") and f.endswith(".csv")):
            continue
        rows = list(csv.DictReader(open(os.path.join(D, f), encoding="utf-8")))
        if not rows:
            continue
        bc = next((k for k in rows[0] if k and k.startswith("boundary")), None)
        if not bc:
            continue
        for r in rows:
            v = (r.get(bc) or "").strip().lower()
            if v in {"true", "false"} and r.get("card_id"):
                flags[r["card_id"]].add(v)
    multi = {c: v for c, v in flags.items() if len(v) > 1}
    agree = sum(1 for v in flags.values() if len(v) == 1)
    print(f"\ncards with a boundary flag: {len(flags)}")
    print(f"  same flag from every reader: {agree}")
    print(f"  readers disagreed on the flag: {len(multi)}")
    print("\nA large disagreement count means the flag is reader-specific and should not be")
    print("used to filter or reweight windows in any reported metric.")


if __name__ == "__main__":
    main()
