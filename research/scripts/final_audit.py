"""Batch 31, and a final audit of every reader file: coverage, agreement, and anomalies."""
from __future__ import annotations

import collections
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = "data/annotations/tb2"
adj = {a["card_id"]: a for a in csv.DictReader(
    open(os.path.join(D, "adjudicated.csv"), encoding="utf-8"))}

rows = list(csv.DictReader(open(os.path.join(D, "labels_refine_31.csv"), encoding="utf-8")))
print(f"labels_refine_31: {len(rows)} rows "
      f"labels={dict(collections.Counter(r['label'] for r in rows))}")
pres = [r for r in rows if r["card_id"] in adj]
agree = sum(1 for r in pres if adj[r["card_id"]]["gold"] == r["label"])
print(f"  in gold: {len(pres)} of {len(rows)}; agreement: {agree}/{len(pres)}")
for r in pres:
    a = adj[r["card_id"]]
    if a["gold"] != r["label"]:
        print(f"    differs: {r['card_id'].split('__')[1]:14} reader={r['label']:<17} "
              f"gold={a['gold']:<17} reads={a['n_reads']} votes={a['votes']}")

print("\nthe neighbouring pair it distinguished:")
for t in (93, 97):
    a = adj.get(f"d_tb2_fix-code-vulnerability__7wXM79N_{t}")
    if a:
        print(f"  step {t:>3} gold={a['gold']:<17} bin={a['binary'] or '-':<3} "
              f"reads={a['n_reads']} votes={a['votes']}")

print("\n=== final audit of all reader files ===")
files = sorted(f for f in os.listdir(D) if f.startswith("labels_") and f.endswith(".csv"))
tot_rows = tot_in_gold = tot_agree = 0
orphan_files = []
odd_columns = []
for f in files:
    rr = list(csv.DictReader(open(os.path.join(D, f), encoding="utf-8")))
    if not rr:
        continue
    # label column name varies slightly across rounds; find it rather than assume
    lc = next((k for k in rr[0] if k and k.strip().lower().startswith("label")), None)
    if lc is None:
        odd_columns.append((f, list(rr[0])[:6]))
        continue
    ids = [r["card_id"] for r in rr if r.get("card_id")]
    ing = [i for i in ids if i in adj]
    ag = sum(1 for r in rr if r.get("card_id") in adj
             and adj[r["card_id"]]["gold"] == (r.get(lc) or "").strip())
    tot_rows += len(ids)
    tot_in_gold += len(ing)
    tot_agree += ag
    if not ing:
        orphan_files.append(f)
print(f"reader files: {len(files)}")
print(f"files with no recognisable label column: {len(odd_columns)}")
for f, cols in odd_columns[:5]:
    print(f"  {f}: {cols}")
print(f"label rows: {tot_rows}")
print(f"  resolving to a gold window: {tot_in_gold} ({100*tot_in_gold/max(1,tot_rows):.1f}%)")
print(f"  agreeing with the gold: {tot_agree} "
      f"({100*tot_agree/max(1,tot_in_gold):.1f}% of resolvable rows)")
print(f"files contributing nothing to the gold: {len(orphan_files)} {orphan_files}")
print(f"\ngold windows: {len(adj)}")
