"""Print a human-readable dump of one trajectory.

Usage: python inspect_trajectory.py --task <substr> [--agent a] [--model m] [--reward 0|1]
       python inspect_trajectory.py --trial <trial_name>
       [--max-steps N] [--obs-chars N] [--list]
"""
import argparse
import json
import os
import sys
from collections import Counter

import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TB2 = os.path.join(ROOT, "data", "raw", "tb2", "train-00000-of-00002.parquet")


def load(columns):
    pf = pq.ParquetFile(TB2)
    rows = []
    for i in range(pf.metadata.num_row_groups):
        rows.extend(pf.read_row_group(i, columns=columns).to_pylist())
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task")
    ap.add_argument("--agent")
    ap.add_argument("--model")
    ap.add_argument("--reward", type=int)
    ap.add_argument("--trial")
    ap.add_argument("--min-steps", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=10**9)
    ap.add_argument("--obs-chars", type=int, default=400)
    ap.add_argument("--msg-chars", type=int, default=500)
    ap.add_argument("--head", type=int, default=6)
    ap.add_argument("--tail", type=int, default=6)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    rows = load(["task_name", "agent", "model", "reward", "trial_name", "duration_seconds", "steps"])
    rows = [r for r in rows if r["steps"] and r["steps"] != "null"]
    if args.task:
        rows = [r for r in rows if args.task in r["task_name"]]
    if args.agent:
        rows = [r for r in rows if args.agent in r["agent"]]
    if args.model:
        rows = [r for r in rows if args.model in r["model"]]
    if args.reward is not None:
        rows = [r for r in rows if r["reward"] == args.reward]
    if args.trial:
        rows = [r for r in rows if r["trial_name"] == args.trial]

    def nsteps(r):
        try:
            return len(json.loads(r["steps"]))
        except Exception:
            return 0

    rows = [r for r in rows if nsteps(r) >= args.min_steps]
    print(f"# candidate trajectories: {len(rows)}")
    if args.list or not rows:
        for r in rows[:60]:
            print(f"  {r['trial_name']:<48} {r['agent']:<20} {r['model']:<45} reward={r['reward']} steps={nsteps(r)}")
        return

    r = max(rows, key=nsteps)
    steps = json.loads(r["steps"])
    print("=" * 110)
    print(f"trial={r['trial_name']} task={r['task_name']} agent={r['agent']} model={r['model']} "
          f"reward={r['reward']} steps={len(steps)} dur={r['duration_seconds']}")
    print("=" * 110)
    idx = list(range(len(steps)))
    show = idx[: args.head] + idx[-args.tail :] if len(steps) > args.head + args.tail else idx
    for i in show:
        s = steps[i]
        if len(steps) > len(show) and i == idx[args.head]:
            print(f"\n... [{len(steps) - args.head - args.tail} steps omitted] ...\n")
        print(f"--- step {i} src={s.get('src')} ---")
        msg = s.get("msg")
        if msg:
            print(f"MSG: {msg[:args.msg_chars]}")
        for t in (s.get("tools") or []):
            print(f"TOOL[{t.get('fn')}]: {str(t.get('cmd'))[:600]}")
        obs = s.get("obs")
        if obs:
            print(f"OBS({len(obs)}c): {obs[:args.obs_chars]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
