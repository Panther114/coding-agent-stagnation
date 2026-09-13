"""Show budget-calibrated operating points."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
run = sys.argv[1] if len(sys.argv) > 1 else "results/final/tb2_cal"
bc = json.load(open(f"{run}/budget_calibrated.json", encoding="utf-8"))
print(f"{'monitor':24}" + "".join(f"{'det@'+str(b)+'%':>10}{'fs':>7}{'cov':>7}" for b in (1, 2, 5, 10, 20)))
for name in sorted(bc):
    row = {int(round(r["budget"] * 100)): r for r in bc[name]}
    cells = ""
    for b in (1, 2, 5, 10, 20):
        r = row.get(b)
        if not r:
            cells += f"{'--':>10}{'--':>7}{'--':>7}"
        else:
            cells += (f"{r['detection_rate']:>10.3f}{r['false_stop_rate']:>7.3f}"
                      f"{r['coverage']:>7.3f}")
    print(f"{name:24}{cells}")
print("\ntrajectory-level view (calibrated at the 5% budget):")
print(f"{'monitor':24}{'thr':>8}{'det':>7}{'fs':>7}{'saved':>8}{'lat':>7}")
for name in sorted(bc):
    r = next((x for x in bc[name] if abs(x["budget"] - 0.05) < 1e-9), None)
    if not r:
        continue
    print(f"{name:24}{r['threshold']:>8.4f}{r.get('traj_detection_rate', float('nan')):>7.3f}"
          f"{r.get('traj_false_stop_rate', float('nan')):>7.3f}"
          f"{r.get('traj_mean_saved', float('nan')):>8.1f}"
          f"{r.get('traj_median_latency', float('nan')):>7.1f}")
