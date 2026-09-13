"""Quantify reader disagreement in the gold set: how much of the label set is contested, and
where the contention sits.

This matters for how the detector's numbers should be read. If disagreement concentrates on one
codebook boundary, then the evaluation is effectively conditioned on windows where readers
agreed, and that is worth stating explicitly rather than leaving implicit in the tie rule.
"""
import collections
import csv
import sys

sys.stdout.reconfigure(encoding="utf-8")
adj = list(csv.DictReader(open("../datasets/annotations/tb2/adjudicated.csv", encoding="utf-8")))
single = [a for a in adj if int(a["n_reads"]) == 1]
multi = [a for a in adj if int(a["n_reads"]) > 1]
tied = [a for a in multi if a["gold"] == "UNCERTAIN"]
binary = [a for a in adj if a["binary"] != ""]

print(f"gold windows           : {len(adj)}")
print(f"  single independent read: {len(single)}")
print(f"  two or more reads      : {len(multi)}")
print(f"  tie -> UNCERTAIN       : {len(tied)}  "
      f"({100*len(tied)/max(1,len(multi)):.1f}% of multiply-read windows)")
print(f"binary-task windows      : {len(binary)} "
      f"({100*len(binary)/len(adj):.1f}% of all labelled windows)")

print("\nwhat the disagreements are between (pairwise label votes):")
pair = collections.Counter()
for a in multi:
    votes = sorted(set(a["votes"].split("|")))
    if len(votes) > 1:
        pair[" + ".join(votes)] += 1
for k, v in pair.most_common():
    print(f"  {v:3d}  {k}")

print("\nagreement among multiply-read windows (binary task only):")
POS = {"STAGNANT", "DONE_REDUNDANT"}
agree = dis = 0
for a in multi:
    vals = [v for v in a["votes"].split("|")]
    b = {1 if v in POS else (0 if v in {"PRODUCTIVE", "REGRESSION"} else None) for v in vals}
    b = {x for x in b if x is not None}
    if len(b) == 1:
        agree += 1
    elif len(b) > 1:
        dis += 1
print(f"  agreed on binary: {agree}, split on binary: {dis} "
      f"({100*agree/max(1,agree+dis):.1f}% binary agreement on multiply-read windows)")

print("\nboundary types touched by disagreement:")
fam = collections.Counter()
for a in multi:
    votes = set(a["votes"].split("|"))
    if len(votes) > 1:
        if votes & {"BLOCKED_EXTERNAL"}:
            fam["blocked-external boundary"] += 1
        elif votes & {"DONE_REDUNDANT"}:
            fam["post-completion boundary"] += 1
        elif votes & {"REGRESSION"}:
            fam["regression boundary"] += 1
        else:
            fam["productive/stagnant boundary"] += 1
for k, v in fam.most_common():
    print(f"  {v:3d}  {k}")
