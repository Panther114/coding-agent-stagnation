"""Is the blocked-external / stagnation disagreement systematic?

Reports which trajectories produce it, whether one scaffold dominates, and whether the same
readers are on each side -- the difference between "one ordering rule is ambiguous" and "one
reader misapplied it".
"""
import collections
import csv
import sys

sys.stdout.reconfigure(encoding="utf-8")
adj = list(csv.DictReader(open("data/annotations/tb2/adjudicated.csv", encoding="utf-8")))
multi = [a for a in adj if int(a["n_reads"]) > 1]

blk = [a for a in multi if "BLOCKED_EXTERNAL" in a["votes"] and len(set(a["votes"].split("|"))) > 1]
print(f"windows where one reader said BLOCKED_EXTERNAL and another disagreed: {len(blk)}")
for a in blk:
    print(f"  {a['traj_id']:46} {a['agent']:16} votes={a['votes']:<34} gold={a['gold']}")

print("\nby trajectory:")
for tid, n in collections.Counter(a["traj_id"] for a in blk).most_common():
    print(f"  {tid:46} {n}")

print("\nby scaffold:")
for s, n in collections.Counter(a["agent"] for a in blk).most_common():
    print(f"  {s:20} {n}")

print("\nreason text on the two sides (first 130 chars):")
for a in blk[:6]:
    print(f"  {a['card_id'].split('__')[1][:24]:26} gold={a['gold']:<16} {a['reason'][:110]}")
