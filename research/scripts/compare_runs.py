"""Side-by-side window metrics for two runs."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
runs = sys.argv[1:] or ["results/final/tb2_v2", "results/final/tb2_v3"]
w = "10"
monitors = ["B2_exact_rep3", "B3_rep_target", "B4_semantic", "B4_sem_diversity", "B5_novelty",
            "B6_verification", "B7_workspace", "C1_evidence", "C1_evidence_rel", "C2_evid_ver",
            "C3_evid_sem", "C4_all_hand", "L_rep", "L_nov", "L_sem", "L_evid", "L_evid_sem",
            "L_all_hand"]
data = {r: json.load(open(f"{r}/window_metrics.json", encoding="utf-8")) for r in runs}
print(f"{'monitor':22}" + "".join(f"{r.split('/')[-1][:14]:>18}" for r in runs))
print(f"{'':22}" + "".join(f"{'roc/within':>18}" for _ in runs))
for m in monitors:
    cells = []
    for r in runs:
        mm = data[r].get(m, {}).get(w)
        cells.append(f"{mm['roc_auc']:.3f}/{mm.get('within_traj_auc', float('nan')):.3f}"
                     if mm else "      --      ")
    print(f"{m:22}" + "".join(f"{c:>18}" for c in cells))
