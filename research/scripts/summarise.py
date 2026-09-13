"""Consolidated descriptive statistics for the paper (corpus, labels, signal coverage).

Usage: python scripts/summarise.py --corpus tb2
Writes results/final/summary_<corpus>.json and prints a compact report.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

import paths  # noqa: E402

PH = re.compile(r"^\$[0-9a-fA-F]{1,4}$")


def pct(vals: List[float], q: float) -> float:
    return float(np.percentile(np.asarray(vals, dtype=float), q)) if vals else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--proc", default=None)
    ap.add_argument("--ann", default=None)
    args = ap.parse_args()
    proc = args.proc or os.path.join(paths.PROCESSED, args.corpus)
    ann = args.ann or os.path.join(paths.DATA, "annotations", args.corpus)

    trajs = [json.loads(l) for l in open(os.path.join(proc, "sample_trajectories.jsonl"), encoding="utf-8")]
    meta = pq.read_table(os.path.join(proc, "trajectories.parquet")).to_pylist()
    n_steps = [len(t["steps"]) for t in trajs]
    ph_frac = []
    notool_frac = []
    sig_frac = []
    obs_chars = []
    kinds = Counter()
    tools = Counter()
    for t in trajs:
        ph = sum(1 for s in t["steps"] if PH.match((s["obs"] or "").strip()))
        ph_frac.append(ph / max(1, len(t["steps"])))
        notool = sum(1 for s in t["steps"] if not s["actions"])
        notool_frac.append(notool / max(1, len(t["steps"])))
        sig_frac.append(1 - notool / max(1, len(t["steps"])))
        for s in t["steps"]:
            obs_chars.append(len(s["obs"] or ""))
            for a in s["actions"]:
                tools[a["name"]] += 1
        msgs = [re.sub(r"\s+", " ", (s["text"] or "").strip()) for s in t["steps"] if (s["text"] or "").strip()]
        if msgs:
            kinds["repeat"] += 0
    print(f"trajectories: {len(trajs)}")
    print(f"tasks: {len({t['task'] for t in trajs})}  scaffolds: {len({t['agent'] for t in trajs})}  "
          f"models: {len({t['model'] for t in trajs})}")
    print(f"steps per trajectory: mean {np.mean(n_steps):.1f} median {np.median(n_steps):.0f} "
          f"p90 {pct(n_steps,90):.0f} max {max(n_steps)}  total {sum(n_steps)}")
    print(f"reward: {dict(Counter(t['reward'] for t in trajs))}")
    print(f"redacted-observation fraction: mean {np.mean(ph_frac):.3f} p90 {pct(ph_frac,90):.3f}")
    print(f"steps with a tool call: mean {np.mean(sig_frac):.3f}")
    print(f"observation length: mean {np.mean(obs_chars):.0f} p50 {pct(obs_chars,50):.0f} p90 {pct(obs_chars,90):.0f}")
    print(f"top scaffolds: {Counter(t['agent'] for t in trajs).most_common()}")
    print(f"top tool names: {tools.most_common(12)}")
    print(f"reward pass rate: {np.mean([t['reward'] or 0 for t in trajs]):.3f}")

    out = {
        "corpus": args.corpus, "n_traj": len(trajs),
        "n_tasks": len({t["task"] for t in trajs}), "n_scaffolds": len({t["agent"] for t in trajs}),
        "n_models": len({t["model"] for t in trajs}),
        "steps_mean": float(np.mean(n_steps)), "steps_median": float(np.median(n_steps)),
        "steps_p90": pct(n_steps, 90), "steps_max": int(max(n_steps)), "steps_total": int(sum(n_steps)),
        "reward": {str(k): v for k, v in Counter(t["reward"] for t in trajs).items()},
        "pass_rate": float(np.mean([t["reward"] or 0 for t in trajs])),
        "ph_frac_mean": float(np.mean(ph_frac)), "ph_frac_p90": pct(ph_frac, 90),
        "tool_step_frac_mean": float(np.mean(sig_frac)),
        "obs_chars_mean": float(np.mean(obs_chars)), "obs_chars_p50": pct(obs_chars, 50),
        "obs_chars_p90": pct(obs_chars, 90),
        "scaffolds": dict(Counter(t["agent"] for t in trajs).most_common()),
        "top_tools": dict(tools.most_common(15)),
    }

    if os.path.exists(os.path.join(ann, "agreement.json")):
        agree = json.load(open(os.path.join(ann, "agreement.json"), encoding="utf-8"))
        adj = list(csv.DictReader(open(os.path.join(ann, "adjudicated.csv"), encoding="utf-8")))
        out["annotation"] = agree
        out["annotation"]["n_cards_index"] = sum(1 for _ in open(os.path.join(ann, "cards_index.csv"), encoding="utf-8")) - 1
        # how many trajectories have at least one positive window, and how many are all-negative
        by_traj = defaultdict(list)
        for a in adj:
            by_traj[a["traj_id"]].append(a)
        pos_traj = sum(1 for v in by_traj.values() if any(a["binary"] == "1" for a in v))
        neg_traj = sum(1 for v in by_traj.values() if all(a["binary"] != "1" for a in v))
        out["annotation"]["traj_with_positive"] = pos_traj
        out["annotation"]["traj_all_negative"] = neg_traj
        out["annotation"]["traj_annotated"] = len(by_traj)
        out["annotation"]["mean_windows_per_traj"] = float(np.mean([len(v) for v in by_traj.values()]))
        # reward association of the labels (independent check that stagnation is not just failure)
        rew = defaultdict(Counter)
        for a in adj:
            if a["binary"] in {"0", "1"}:
                rew[a["reward"]]["POS" if a["binary"] == "1" else "NEG"] += 1
        out["annotation"]["label_by_reward"] = {k: dict(v) for k, v in rew.items()}
        # label by reward bucket: conditional positive rate
        for r, c in rew.items():
            tot = sum(c.values())
            print(f"reward={r}: positive rate {c['POS']/tot:.3f} (n={tot})")

    os.makedirs(paths.FINAL, exist_ok=True)
    with open(os.path.join(paths.FINAL, f"summary_{args.corpus}.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote results/final/summary_{args.corpus}.json")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
