"""Print the trajectory-level alarm frontier at a given budget, for the paper's summary."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
run = sys.argv[1] if len(sys.argv) > 1 else "results/final/tb2_final"
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
w = sys.argv[3] if len(sys.argv) > 3 else "10"
fr = json.load(open(os.path.join(run, "alarm_frontier.json"), encoding="utf-8"))
print(f"{'monitor':22}{'avail':>6}{'thr':>8}{'det':>7}{'fs':>7}{'saved':>8}{'lat':>7}")
for name in sorted(fr):
    rows = fr[name].get(w) or fr[name].get(w)
    if not rows:
        continue
    r = next((x for x in rows if abs(x["budget"] - budget) < 1e-9), None)
    if not r:
        continue
    print(f"{name:22}{int(r.get('available', 0)):>6}{r.get('threshold', float('nan')):>8.3f}"
          f"{r.get('detection_rate', float('nan')):>7.3f}"
          f"{r.get('false_stop_rate', float('nan')):>7.3f}"
          f"{r.get('mean_saved_steps', float('nan')):>8.2f}"
          f"{r.get('median_latency', float('nan')):>7.1f}")
