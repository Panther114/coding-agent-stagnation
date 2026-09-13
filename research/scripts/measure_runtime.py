"""Measure the monitor's runtime cost, so the paper's efficiency claim is evidence-based.

Usage: python scripts/measure_runtime.py [--n 30]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

from build_dataset import build_views  # noqa: E402
from evidence import task_terms  # noqa: E402
from loaders import Action, Step, Trajectory, tb2_task_statements  # noqa: E402
from monitors import (ExactRepeat, FeatureMonitor, StepBudget, WindowFeatureCache,  # noqa: E402
                      alarmed_steps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--w", type=int, default=10)
    args = ap.parse_args()
    proc = os.path.join(os.path.dirname(HERE), "data", "processed", "tb2")
    sample = [json.loads(l) for l in open(os.path.join(proc, "sample_trajectories.jsonl"),
                                          encoding="utf-8")][: args.n]
    trajs = []
    for b in sample:
        steps = [Step(index=i, text=s["text"],
                      actions=[Action(a["name"], a["arg"]) for a in s["actions"]],
                      observation=s["obs"]) for i, s in enumerate(b["steps"])]
        trajs.append(Trajectory(traj_id=b["traj_id"], task=b["task"], agent=b["agent"],
                                model=b["model"], reward=b["reward"], steps=steps, meta=b["meta"]))
    stmts = tb2_task_statements()
    t0 = time.time()
    views = build_views(trajs, stmts)
    t_build = time.time() - t0
    for v in views:
        v.idf = {}
    n_win = 0
    t0 = time.time()
    caches = {}
    for v in views:
        cfg = {"_terms": task_terms(stmts.get(v.task, "")), "rel_threshold": 0.5}
        c = WindowFeatureCache(v, args.w, cfg)
        caches[v.traj_id] = c
        n_win += c.n
    t_feat = time.time() - t0
    mon = FeatureMonitor("m", ["ev_new_relevant_rate", "ev_persist_rate"], [-1, -1]).fit(
        np_stack([c.X for c in caches.values()]))
    t0 = time.time()
    n_alarm = 0
    for v in views:
        s = mon.score_series(caches[v.traj_id])
        n_alarm += len(alarmed_steps(s, 0.7, k=2, min_step=5))
    t_score = time.time() - t0
    rep = {
        "trajectories": len(views),
        "steps": sum(len(v.steps) for v in views),
        "windows": n_win,
        "seconds_parse_and_normalize": t_build,
        "seconds_features": t_feat,
        "ms_per_window_feature_vector": 1000 * t_feat / max(1, n_win),
        "seconds_score_and_alarm_all_monitors_sample": t_score,
        "ms_per_step_scoring_one_monitor": 1000 * t_score / max(1, n_win),
    }
    print(json.dumps(rep, indent=2))
    out = os.path.join(os.path.dirname(HERE), "results", "final", "runtime.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print(f"wrote {out}")


def np_stack(xs):
    import numpy as np
    return np.vstack(xs)


if __name__ == "__main__":
    main()
