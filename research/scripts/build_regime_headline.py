"""Freeze the regime-level result as the study's headline positive finding.

Collects the label-structure analysis, the position control, and the clustered-bootstrap
episode-level test into one artifact, and emits the LaTeX macros the paper reads.
"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
OUT = "results/final/v2"
os.makedirs(OUT, exist_ok=True)

struct = json.load(open(os.path.join(OUT, "label_structure.json"), encoding="utf-8"))
sig = json.load(open(os.path.join(OUT, "regime_signal.json"), encoding="utf-8"))
cp = json.load(open(os.path.join(OUT, "changepoint_test.json"), encoding="utf-8"))

best = sig["B4_semantic"]
pm = sig["B4_semantic_position_matched"]
pos_proxy_pm = sig["B1_step30_position_matched"]

summary = {
    "n_episodes": struct["n_stagnant_regions"],
    "n_productive_regions": struct["n_productive_regions"],
    "windows_in_episodes": struct["windows_in_stagnant_regions"],
    "episode_median_steps": struct["episode_median_steps"],
    "episode_max_steps": struct["episode_max_steps"],
    "episodes_ge20": struct["episodes_ge20"],
    "episodes_separated": best["separated"],
    "episodes_total": best["episodes"],
    "mean_diff": best["mean_diff"],
    "ci": best["ci"],
    "p": best["p"],
    "pm_separated": pm["separated"],
    "pm_total": pm["episodes"],
    "pm_mean_diff": pm["mean_diff"],
    "pm_ci": pm["ci"],
    "pm_p": pm["p"],
    "proxy_pm_separated": pos_proxy_pm["separated"],
    "proxy_pm_total": pos_proxy_pm["episodes"],
    "detect_global_q80": cp.get("B_q0.8", {}),
    "detect_global_q90": cp.get("B_q0.9", {}),
}
json.dump(summary, open(os.path.join(OUT, "regime_headline.json"), "w", encoding="utf-8"),
          indent=2)

print("=== headline regime result ===")
print(f"  episodes                          {summary['n_episodes']} over "
      f"{struct['trajectories_with_stagnant_region']} runs")
print(f"  median episode length             {summary['episode_median_steps']} steps "
      f"(max {summary['episode_max_steps']})")
print(f"  episodes separated by the monitor {summary['episodes_separated']}/"
      f"{summary['episodes_total']} ({100*summary['episodes_separated']/summary['episodes_total']:.0f}%)")
print(f"  mean score gap                    {summary['mean_diff']:+.3f} "
      f"[{summary['ci'][0]:+.3f}, {summary['ci'][1]:+.3f}] p={summary['p']:.4f}")
print(f"  POSITION-MATCHED                  {summary['pm_separated']}/{summary['pm_total']} "
      f"({100*summary['pm_separated']/summary['pm_total']:.0f}%) "
      f"diff {summary['pm_mean_diff']:+.3f} [{summary['pm_ci'][0]:+.3f}, "
      f"{summary['pm_ci'][1]:+.3f}] p={summary['pm_p']:.4f}")
print(f"  position proxy, same test         {summary['proxy_pm_separated']}/"
      f"{summary['proxy_pm_total']}")
print(f"\nwrote {OUT}/regime_headline.json")
