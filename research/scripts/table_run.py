"""Compact console table for a frozen run: window alarm frontier + window metrics."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
run = sys.argv[1] if len(sys.argv) > 1 else "results/final/tb2_dense"
w = str(sys.argv[2]) if len(sys.argv) > 2 else "10"

wl = json.load(open(os.path.join(run, "window_metrics.json"), encoding="utf-8"))
wf = json.load(open(os.path.join(run, "window_alarm_frontier.json"), encoding="utf-8"))
wc = json.load(open(os.path.join(run, "window_alarm_curves.json"), encoding="utf-8"))

print(f"{'monitor':24}{'ROC':>7}{'PR':>7}{'F1':>7} | {'det@1%':>7}{'det@5%':>7}{'det@10%':>8}{'fs@5%':>7}{'cov@5%':>7}")
for name in sorted(wl):
    m = wl[name].get(w) or wl[name].get(w)
    if not m:
        continue
    fr = wf.get(name, [])
    if isinstance(fr, dict):
        fr = fr.get(w) or []
    by = {round(f["budget"], 2): f for f in fr}

    def g(b, k):
        v = by.get(b, {}).get(k)
        return f"{v:.3f}" if isinstance(v, (int, float)) else "  -- "
    print(f"{name:24}{m['roc_auc']:7.3f}{m['pr_auc']:7.3f}{m['f1_best']:7.3f} | "
          f"{g(0.01,'detection_rate'):>7}{g(0.05,'detection_rate'):>7}{g(0.10,'detection_rate'):>8}"
          f"{g(0.05,'false_stop_rate'):>7}{g(0.05,'coverage'):>7}")

if w in wc.get(next(iter(wc)), {}):
    pass
print("\ncoverage range across monitors at w=%s: %.3f .. %.3f" % (
    w,
    min((c["coverage"] for name in wc for c in wc[name].get(w, []) if c["coverage"] == c["coverage"]), default=float("nan")),
    max((c["coverage"] for name in wc for c in wc[name].get(w, []) if c["coverage"] == c["coverage"]), default=float("nan")),
))
