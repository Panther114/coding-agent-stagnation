"""Consolidate the exploratory-variation question and check how the gold resolved these cases."""
import collections
import csv
import sys

sys.stdout.reconfigure(encoding="utf-8")
adj = {a["card_id"]: a for a in csv.DictReader(
    open("data/annotations/tb2/adjudicated.csv", encoding="utf-8"))}

print("batch 32's flagged windows:")
for cid, why in {
    "d_tb2_fix-ocaml-gc__4FMyNtb_159": "edit_revert",
    "d_tb2_fix-ocaml-gc__4FMyNtb_195": "repeat_read",
    "d_tb2_fix-ocaml-gc__4FMyNtb_421": "no_tool_text_loop",
    "d_tb2_fix-ocaml-gc__4FMyNtb_383": "DONE_REDUNDANT",
    "d_tb2_fix-ocaml-gc__4FMyNtb_33": "repeated grep variants, PRODUCTIVE low conf",
}.items():
    a = adj.get(cid)
    if not a:
        print(f"  {cid.split('__')[1]:30} absent from gold")
        continue
    print(f"  {cid.split('__')[1]:30} gold={a['gold']:<15} bin={a['binary'] or '-':<3} "
          f"reads={a['n_reads']} votes={a['votes']:<30} ({why})")

print("\nhow many gold windows are windows of 'repeated search with overlapping results',")
print("i.e. labelled STAGNANT with detail repeat_search or repeat_read:")
c = collections.Counter(a["detail"] for a in adj.values() if a["gold"] == "STAGNANT")
for k, v in c.most_common():
    print(f"  {k or '(no detail)':26} {v}")

print("\nthe 4FMyNtb trajectory in gold:")
rows = [a for a in adj.values() if "4FMyNtb" in a["traj_id"]]
print(f"  windows={len(rows)} labels={dict(collections.Counter(a['gold'] for a in rows))}")
print(f"  n_steps={rows[0]['n_steps'] if rows else '?'} reward={rows[0]['reward'] if rows else '?'}")
