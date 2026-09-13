"""Report the annotated windows of the trajectories used as signal examples.

Usage: python scripts/inspect_signal_examples.py --run results/final/tb2_final
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")

ap = argparse.ArgumentParser()
ap.add_argument("--run", default="results/final/tb2_final")
ap.add_argument("--ann", default="data/annotations/tb2")
args = ap.parse_args()

notes = json.load(open(os.path.join(args.run, "figure_notes.json"), encoding="utf-8"))
trajs = notes.get("signal_example_trajectories", [])
print("signal-example trajectories:", trajs)
adj = [a for a in csv.DictReader(open(os.path.join(args.ann, "adjudicated.csv"), encoding="utf-8"))]
rows = [r for r in csv.DictReader(open(os.path.join(args.run, "window_features.parquet"),
                                     newline="", encoding="utf-8"))] if False else None
import pyarrow.parquet as pq
wf = pq.read_table(os.path.join(args.run, "window_features.parquet")).to_pylist()
for t in trajs:
    sub = [a for a in adj if a["traj_id"] == t]
    print(f"\n== {t}  ({sub[0]['agent'] if sub else '?'}, reward {sub[0]['reward'] if sub else '?'}, "
          f"{sub[0]['n_steps'] if sub else '?'} steps)")
    for a in sub:
        print(f"   t={a['t']:>4} {a['gold']:<16} binary={a['binary'] or '-':<2} {a['detail']:<22} "
              f"{a['reason'][:70]}")
    ws = [r for r in wf if r["traj_id"] == t and r["w"] == 10]
    if ws:
        import statistics as st
        key = "ev_new_relevant_rate"
        vals = [r[key] for r in ws if r[key] == r[key]]
        if vals:
            print(f"   evidence rate over the run: mean={st.mean(vals):.3f} max={max(vals):.3f}")
