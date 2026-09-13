"""Check cards that a reader flagged as codebook-ambiguous, against the adjudicated gold."""
import csv
import sys

sys.stdout.reconfigure(encoding="utf-8")
adj = {a["card_id"]: a for a in csv.DictReader(
    open("../datasets/annotations/tb2/adjudicated.csv", encoding="utf-8"))}

checks = {
    "d_tb2_feal-linear-cryptanalysis__L3Ts8kn_33": "advancing counter read as non-informative",
    "d_tb2_break-filter-js-from-html__J2d7BGR_27": "clearly productive",
    "d_tb2_llm-inference-batching-scheduler__evStmDE_55": "single UNCERTAIN, truncated metrics",
    "d_tb2_db-wal-recovery__rwGVtyu_29": "STAGNANT vs BLOCKED_EXTERNAL",
    "d_tb2_fix-ocaml-gc__awEK6tj_48": "edit/revert churn",
    "d_tb2_fix-ocaml-gc__4FMyNtb_15": "learns config missing",
    "d_tb2_crack-7z-hash__M36nRdr_14": "boundary: search space narrows",
}
print(f"{'card':52}{'gold':16}{'bin':4}{'reads':6}{'votes'}")
for cid, note in checks.items():
    a = adj.get(cid)
    if not a:
        print(f"{cid.split('__')[1]:52}absent")
        continue
    print(f"{cid.split('__')[1]:52}{a['gold']:<16}{a['binary'] or '-':<4}{a['n_reads']:<6}{a['votes']}")

print("\nall UNCERTAIN windows and why they were held out:")
unc = [a for a in adj.values() if a["gold"] == "UNCERTAIN"]
for a in unc[:16]:
    print(f"  {a['traj_id'][:40]:42} votes={a['votes']:<36} reads={a['n_reads']}")
print(f"  ... {len(unc)} UNCERTAIN windows in total")
