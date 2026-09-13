"""Do the four cards batch 32 flagged actually exist, and why are they absent from the gold?

A label for a card that does not exist would mean the reader labelled something other than what
it read.  Check the filesystem first, then the sampled-trajectory set.
"""
import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
CARDS = "data/annotations/tb2/cards_dense"
adj = {a["card_id"] for a in csv.DictReader(
    open("data/annotations/tb2/adjudicated.csv", encoding="utf-8"))}

cids = [f"d_tb2_fix-ocaml-gc__4FMyNtb_{t}" for t in (159, 195, 383, 421)]
print("do the files exist?")
for c in cids:
    print(f"  {c:44} exists={os.path.exists(os.path.join(CARDS, c + '.md'))} in_gold={c in adj}")

print("\nfull batch-32 label file, checked card by card:")
rows = list(csv.DictReader(open("data/annotations/tb2/labels_refine_32.csv", encoding="utf-8")))
ex = sum(1 for r in rows if os.path.exists(os.path.join(CARDS, r["card_id"] + ".md")))
ing = sum(1 for r in rows if r["card_id"] in adj)
print(f"  rows={len(rows)}  files_exist={ex}  in_gold={ing}")

print("\nis the trajectory in the analysis sample at all?")
sample = [json.loads(l) for l in open("data/processed/tb2/sample_trajectories.jsonl", encoding="utf-8")]
ids = {t["traj_id"] for t in sample}
print(f"  fix-ocaml-gc__4FMyNtb in sample: {'fix-ocaml-gc__4FMyNtb' in ids}")
print(f"  sample size: {len(ids)}")
