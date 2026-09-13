"""Data-quality profiling: scrape artefacts and degenerate trajectories.

Produces results/exploratory/data_quality.json and prints a report.  The purpose is
to decide, on evidence, which trajectories are analysable and how much of the corpus
must be excluded -- and to make that decision explicit in the paper.

Usage: python scripts/data_quality.py --corpus tb2 --n 800
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import loaders  # noqa: E402
import paths  # noqa: E402

PLACEHOLDER = re.compile(r"^\$[0-9a-fA-F]{1,4}$")


def profile(trajs) -> Dict:
    n = len(trajs)
    stats = {
        "n": n,
        "placeholder_obs_frac": [],
        "placeholder_step_frac": [],
        "max_msg_repeat_frac": [],
        "n_steps": [],
        "no_tool_frac": [],
        "agents": Counter(),
        "tasks": Counter(),
        "reward": Counter(),
        "n_placeholder_only_trajs": 0,
        "n_degenerate_msg_loop": 0,
        "n_no_tool_dominated": 0,
    }
    for t in trajs:
        npl = sum(1 for s in t.steps if PLACEHOLDER.match((s.observation or "").strip()))
        stats["placeholder_obs_frac"].append(npl / max(1, len(t.steps)))
        if npl / max(1, len(t.steps)) > 0.5:
            stats["n_placeholder_only_trajs"] += 1
        msgs = [re.sub(r"\s+", " ", (s.text or "").strip()) for s in t.steps if (s.text or "").strip()]
        if msgs:
            c = Counter(msgs)
            top = max(c.values()) / len(msgs)
        else:
            top = 0.0
        stats["max_msg_repeat_frac"].append(top)
        if top > 0.5 and len(t.steps) >= 20:
            stats["n_degenerate_msg_loop"] += 1
        notool = sum(1 for s in t.steps if not s.actions)
        stats["no_tool_frac"].append(notool / max(1, len(t.steps)))
        if notool / max(1, len(t.steps)) > 0.6 and len(t.steps) >= 20:
            stats["n_no_tool_dominated"] += 1
        stats["n_steps"].append(len(t.steps))
        stats["agents"][t.agent] += 1
        stats["tasks"][t.task] += 1
        stats["reward"][t.reward] += 1

    keep = {k: v for k, v in stats.items() if not isinstance(v, list)}
    for k in ("placeholder_obs_frac", "max_msg_repeat_frac", "no_tool_frac"):
        a = np.asarray(stats[k])
        keep[k + "_mean"] = float(np.mean(a))
        keep[k + "_p50"] = float(np.median(a))
        keep[k + "_p90"] = float(np.percentile(a, 90))
        keep[k + "_p99"] = float(np.percentile(a, 99))
        keep[k + "_gt50"] = int(np.sum(a > 0.5))
        keep[k + "_gt90"] = int(np.sum(a > 0.9))
    ns = np.asarray(stats["n_steps"])
    keep["n_steps_mean"] = float(np.mean(ns))
    keep["n_steps_p50"] = float(np.median(ns))
    keep["n_steps_p90"] = float(np.percentile(ns, 90))
    keep["agents"] = dict(stats["agents"].most_common(30))
    keep["tasks"] = dict(stats["tasks"].most_common(100))
    keep["reward"] = {str(k): v for k, v in stats["reward"].items()}
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--n", type=int, default=800)
    args = ap.parse_args()
    if args.corpus == "tb2":
        trajs = loaders.load_tb2()
    else:
        trajs = loaders.load_nebius(limit=args.n)
    sub = trajs[:: max(1, len(trajs) // args.n)][: args.n] if args.corpus == "tb2" else trajs
    rep = profile(sub)
    with open(os.path.join(paths.EXPLORATORY, f"data_quality_{args.corpus}.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print(json.dumps(rep, indent=2)[:5000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
