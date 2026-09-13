"""Diagnostics on a frozen run: alarm behaviour per monitor."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")

run = sys.argv[1] if len(sys.argv) > 1 else "results/final/tb2_cv"
w = sys.argv[2] if len(sys.argv) > 2 else "10"

cfg = json.load(open(os.path.join(run, "run_config.json"), encoding="utf-8"))
print({k: cfg[k] for k in ("n_traj", "n_window_rows", "n_annotated_windows", "n_alarm_eval_traj",
                           "n_alarm_eval_traj_with_region", "has_semantic", "folds")})
oc = json.load(open(os.path.join(run, "alarm_outcomes.json"), encoding="utf-8"))
print("\nfirst-alarm outcomes (annotated trajectories):")
for name in sorted(oc):
    d = oc[name].get(w)
    if d:
        print(f"  {name:24} {d}")
desc = json.load(open(os.path.join(run, "descriptive.json"), encoding="utf-8"))
print("\nfree-running alarms at threshold 0.7 (all trajectories):")
for k in sorted(desc):
    if k.endswith("w" + w):
        v = desc[k]
        print(f"  {k.split('|')[0]:24} alarm_rate={v['alarm_rate']:.3f} "
              f"median_step={v['median_alarm_step']} "
              f"median_saved={v['median_steps_saved']} "
              f"pass_all={v['pass_rate_all']:.3f} pass_alarmed={v['pass_rate_among_alarmed']}")
oa = json.load(open(os.path.join(run, "outcome_association.json"), encoding="utf-8"))
print("\nmean-score vs final success (AUC, 0.5 = no information):")
for k in sorted(oa):
    if k.endswith("w" + w):
        print(f"  {k.split('|')[0]:24} auc={oa[k]['auc_mean_score_vs_success']:.3f} n={oa[k]['n']}")
