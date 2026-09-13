"""Headline numbers for the overview, read from the frozen run."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
w = json.load(open("results/final/tb2_v5/window_metrics.json", encoding="utf-8"))
print("window metrics at w=10 (global ROC / within-run AUC):")
for m in ("B4_semantic", "B5_novelty", "C3_evid_sem", "C4_all_hand", "B2_exact_rep3",
          "C1_evidence", "B6_verification", "B7_workspace", "B1_step30"):
    x = w.get(m, {}).get("10")
    if x:
        print(f"  {m:16} {x['roc_auc']:.3f} / {x['within_traj_auc']:.3f}")

r = json.load(open("results/final/tb2_v5/within_run_robustness.json", encoding="utf-8"))
b = r["vs_step_budget"]["best"]
mm = r["per_monitor"][b]
print(f"\nwithin-run robustness (best monitor = {b}):")
print(f"  runs with both classes     : {mm['runs']}")
print(f"  median within-run AUC      : {mm['median']:.3f}")
print(f"  above chance               : {mm['wins']} vs {mm['losses']}, sign test p={mm['sign_p']:.4f}")
print(f"  reaches 0.70               : {mm['share_ge_0_70']*100:.0f}% of runs")
ties = [m for m, v in r["per_monitor"].items() if abs(v["median"] - 0.5) < 1e-9]
print(f"  monitors with median 0.500 : {len(ties)} of {len(r['per_monitor'])}")
v = r["variance"]
print(f"  per-task positive-rate AUC : {v['task_rate_auc']:.3f} (task identity is not the signal)")
print(f"  tasks that never stagnate  : {v['zero_tasks']}")

pc = json.load(open("results/final/tb2_v5/paired_comparisons.json", encoding="utf-8"))
print("\npaired vs the best monitor (trajectory-clustered):")
for k, val in list(pc["pairs"].items())[:6]:
    star = "*" if val.get("p_value", 1) < 0.05 else " "
    print(f"  {k:38} delta={val['delta']:+.3f} p={val.get('p_value', float('nan')):.3f} {star}")

agg = json.load(open("results/final/redaction.json", encoding="utf-8"))
print(f"\ncorpus redaction: {100*agg['share']:.1f}% of observations, {100*agg['mean_per_traj']:.1f}% per run")
