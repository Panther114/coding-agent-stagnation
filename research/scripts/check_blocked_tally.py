"""Tally how every window a reader called BLOCKED_EXTERNAL was finally resolved."""
import csv
import sys

sys.stdout.reconfigure(encoding="utf-8")
adj = list(csv.DictReader(open("data/annotations/tb2/adjudicated.csv", encoding="utf-8")))
rows = [a for a in adj if "BLOCKED_EXTERNAL" in a["votes"]]
unanimous = [a for a in rows if a["gold"] == "BLOCKED_EXTERNAL" and int(a["n_reads"]) > 1]
single = [a for a in rows if a["gold"] == "BLOCKED_EXTERNAL" and int(a["n_reads"]) == 1]
tied = [a for a in rows if a["gold"] == "UNCERTAIN"]
other = [a for a in rows if a not in unanimous + single + tied]

print(f"windows with at least one BLOCKED_EXTERNAL vote: {len(rows)}")
print(f"  multiply-read, unanimous, kept as BLOCKED_EXTERNAL : {len(unanimous)}")
print(f"  single read, kept as BLOCKED_EXTERNAL              : {len(single)}")
print(f"  tied with a dissenting label, held out             : {len(tied)}")
print(f"  dissenting label won the majority                  : {len(other)}")
for a in other:
    print(f"      {a['traj_id'][:44]:46} votes={a['votes']:<34} gold={a['gold']}")
print(f"\ngold BLOCKED_EXTERNAL total: {sum(1 for a in adj if a['gold'] == 'BLOCKED_EXTERNAL')}")
