"""Compare global window AUC with within-trajectory AUC."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
run = sys.argv[1] if len(sys.argv) > 1 else "results/final/tb2_v2"
w = sys.argv[2] if len(sys.argv) > 2 else "10"
wl = json.load(open(f"{run}/window_metrics.json", encoding="utf-8"))
rows = []
for n in sorted(wl):
    m = wl[n].get(w)
    if not m:
        continue
    rows.append((n, m["roc_auc"], m.get("within_traj_auc"), m.get("n_traj_with_both_classes", 0),
                 m["pr_auc"], m["f1_best"]))
rows.sort(key=lambda r: -(r[2] if r[2] == r[2] else 0))
print(f"{'monitor':24}{'global':>8}{'within':>8}{'runs':>6}{'PR':>8}{'F1':>8}")
for n, a, b, c, d, e in rows:
    bs = f"{b:.3f}" if b == b else "  -- "
    print(f"{n:24}{a:8.3f}{bs:>8}{int(c):6d}{d:8.3f}{e:8.3f}")
