"""Size the orphaned-label defect: labels on disk whose cards are absent from every index."""
import collections
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = "../datasets/annotations/tb2"
IDX = ("cards_index.csv", "dense_cards_index.csv", "dense2_cards_index.csv")

idx = {}
for f in IDX:
    p = os.path.join(D, f)
    if os.path.exists(p):
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        idx[f] = rows
        kinds = dict(collections.Counter(r.get("kind", "") for r in rows))
        print(f"{f:26} rows={len(rows):5d}  kinds={kinds}")
    else:
        print(f"{f:26} MISSING")

allidx = set()
for rows in idx.values():
    allidx |= {r["card_id"] for r in rows}
print(f"\nunion of index ids: {len(allidx)}")

src = open("scripts/build_gold.py", encoding="utf-8").read()
used = re.findall(r'"((?:cards|dense|dense2)_?[a-z_]*index\.csv)"', src)
print(f"indices build_gold.py actually reads: {sorted(set(used))}")

lab = set()
for f in sorted(os.listdir(D)):
    if f.startswith("labels_") and f.endswith(".csv"):
        for r in csv.DictReader(open(os.path.join(D, f), encoding="utf-8")):
            if r.get("card_id"):
                lab.add(r["card_id"])
print(f"\nlabelled card ids on disk: {len(lab)}")
print(f"labelled and indexed (usable): {len(lab & allidx)}")
print(f"labelled but NOT indexed (orphaned): {len(lab - allidx)}")

gold = {a["card_id"] for a in csv.DictReader(open(os.path.join(D, "adjudicated.csv"), encoding="utf-8"))}
print(f"gold windows: {len(gold)}")
print(f"labels that would become newly usable if the missing index were added: "
      f"{len((lab - allidx) & lab)}")

# how much would the gold set grow?
cands = lab & allidx
print(f"\ncards that could enter the gold set: {len(cands)} (currently {len(gold)})")
per_traj = collections.Counter(c.split("_tb2_")[-1].rsplit("_", 1)[0] for c in (allidx - gold))
print(f"trajectories that would gain windows: {len(per_traj)}")
print("largest gains:", per_traj.most_common(5))
