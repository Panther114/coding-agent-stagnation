"""Write the redaction artifact the paper reads.

Two numbers, because the first one used to be wrong.  The share of *steps with an observation*
that show a bare reference instead of output is 25.5%; averaged per trajectory it is 29.7%.  The
figure reported earlier (22.4%) divided by all steps, including ones that never had an
observation, so it understated what a reader actually sees.  The tie rates are the operative
consequence: how often two independent readers disagree, by how much redaction the window's card
contains.

Usage: python scripts/measure_redaction.py [--write]
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
PH = re.compile(r"^\$[A-Za-z0-9]{1,4}$")
CARDS = "data/annotations/tb2/cards_dense"
SAMPLES = "data/processed/tb2/sample_trajectories.jsonl"
OUT = "results/final/redaction.json"


def main() -> None:
    tot = bare = tot_all = 0
    per_traj = []
    for line in open(SAMPLES, encoding="utf-8"):
        t = json.loads(line)
        n = r = 0
        for s in t["steps"]:
            tot_all += 1
            obs = (s.get("obs") or "").strip()
            if not obs:
                continue
            n += 1
            if PH.match(obs):
                r += 1
        tot += n
        bare += r
        per_traj.append(r / max(1, n))
    share = bare / max(1, tot)
    print(f"steps: {tot_all}; with an observation: {tot}")
    print(f"  bare reference instead of output: {bare} ({100*share:.1f}%)")
    print(f"  mean per-trajectory share: {sum(per_traj)/len(per_traj):.3f} "
          f"(the earlier 22.4% divided by all steps and understated this)")

    PH2 = re.compile(r'obs="\$[A-Za-z0-9]{1,4}"')
    density = {}
    for n in os.listdir(CARDS):
        if n.endswith(".md"):
            txt = open(os.path.join(CARDS, n), encoding="utf-8", errors="replace").read()
            density[os.path.splitext(n)[0]] = len(PH2.findall(txt))
    adj = list(csv.DictReader(open("data/annotations/tb2/adjudicated.csv", encoding="utf-8")))
    buckets = []
    print("\ntie rate by placeholders in the window's card:")
    for lo, hi, tag in ((0, 0, "0"), (1, 5, "1-5"), (6, 15, "6-15"), (16, 999, "16+")):
        sel = [a for a in adj if lo <= density.get(a["card_id"], 0) <= hi]
        multi = [a for a in sel if int(a["n_reads"]) > 1]
        tied = [a for a in multi if a["gold"] == "UNCERTAIN"]
        rate = len(tied) / max(1, len(multi))
        buckets.append({"label": tag, "windows": len(sel), "multi": len(multi),
                        "tied": len(tied), "tie_rate": rate})
        print(f"  {tag:6} gold={len(sel):5d} multi={len(multi):4d} tied={len(tied):3d} "
              f"tie={100*rate:5.1f}%")

    if "--write" in sys.argv:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump({"share": share, "steps": tot, "bare": bare,
                   "mean_per_traj": sum(per_traj) / len(per_traj), "buckets": buckets},
                  open(OUT, "w", encoding="utf-8"), indent=2)
        print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
