"""Window-size sensitivity: how each family's ranking changes with the window length."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
runs = {"w6": ("results/final/tb2_w6_w30", "6"), "w10": ("results/final/tb2_final", "10"),
        "w20": ("results/final/tb2_final", "20"), "w30": ("results/final/tb2_w6_w30", "30")}
mons = ["B2_exact_rep3", "B3_rep_target", "B4_semantic", "B5_novelty", "B6_verification",
        "B7_workspace", "C1_evidence", "C3_evid_sem", "C4_all_hand", "L_sem", "L_evid_sem",
        "L_all_sem", "L_rep", "L_nov", "L_work", "B1_step30"]
print(f"{'monitor':18}" + "".join(f"{k:>18}" for k in runs))
print(f"{'':18}" + "".join(f"{'roc / within':>18}" for _ in runs))
data = {k: json.load(open(os.path.join(v[0], "window_metrics.json"), encoding="utf-8"))
        for k, v in runs.items()}
for m in mons:
    cells = []
    for k, (_, w) in runs.items():
        mm = data[k].get(m, {}).get(w)
        cells.append(f"{mm['roc_auc']:.3f}/{mm.get('within_traj_auc', float('nan')):.3f}"
                     if mm else "       --      ")
    print(f"{m:18}" + "".join(f"{c:>18}" for c in cells))

print("\nper-window detection at a 5% false-stop budget:")
for m in ["B4_semantic", "L_sem", "C3_evid_sem", "L_evid_sem", "B5_novelty", "C1_evidence",
          "B2_exact_rep3", "B7_workspace"]:
    cells = []
    for k, (run, w) in runs.items():
        fr = json.load(open(os.path.join(run, "window_alarm_frontier.json"), encoding="utf-8"))
        rows = fr.get(m, [])
        if isinstance(rows, dict):
            rows = rows.get(w) or []
        pick = next((f for f in rows if abs(f["budget"] - 0.05) < 1e-9), None)
        cells.append(f"{pick['detection_rate']:.2f}/{pick['false_stop_rate']:.2f}"
                     if pick and pick.get("available") else "  --  ")
    print(f"  {m:16}" + "".join(f"{c:>18}" for c in cells))
