"""Add extra dense windows for the same trajectories (denser marked-point coverage).

The first dense round placed ~10 windows per trajectory at up to 4 steps apart.  For the
tolerant alarm metric, denser marked points reduce the amount of trajectory that is neither
annotated nor credited, so this script adds windows at a stride of 2 for every trajectory
that appears in ``dense_cards_index.csv``, skipping positions that already have a card.

Usage: python scripts/make_extra_dense_cards.py --corpus tb2 --stride 2
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import paths  # noqa: E402
from loaders import Action, Step, Trajectory, nebius_task_statements, tb2_task_statements  # noqa: E402
from make_annotation_cards import card  # noqa: E402


def load_sample(path: str) -> Dict[str, Trajectory]:
    out = {}
    for line in open(path, encoding="utf-8"):
        b = json.loads(line)
        steps = [Step(index=i, text=s["text"],
                      actions=[Action(a["name"], a["arg"]) for a in s["actions"]],
                      observation=s["obs"]) for i, s in enumerate(b["steps"])]
        out[b["traj_id"]] = Trajectory(traj_id=b["traj_id"], task=b["task"], agent=b["agent"],
                                       model=b["model"], reward=b["reward"], steps=steps, meta=b["meta"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--per-traj-cap", type=int, default=30)
    ap.add_argument("--min-step", type=int, default=5)
    ap.add_argument("--w", type=int, default=10)
    args = ap.parse_args()

    proc = os.path.join(paths.PROCESSED, args.corpus)
    ann = os.path.join(paths.DATA, "annotations", args.corpus)
    cards_dir = os.path.join(ann, "cards_dense")
    trajs = load_sample(os.path.join(proc, "sample_trajectories.jsonl"))
    stmts = tb2_task_statements() if args.corpus == "tb2" else nebius_task_statements()

    have: Dict[str, set] = defaultdict(set)
    existing_rows = list(csv.DictReader(open(os.path.join(ann, "dense_cards_index.csv"),
                                             newline="", encoding="utf-8")))
    for r in existing_rows:
        have[r["traj_id"]].add(int(r["t"]))

    rows: List[Dict[str, Any]] = []
    for r in existing_rows:
        tid = r["traj_id"]
    todo = sorted(have)
    for tid in todo:
        tr = trajs.get(tid)
        if tr is None:
            continue
        n = len(tr.steps)
        want = set(range(max(args.min_step, args.w - 1), n, args.stride))
        if len(want) > args.per_traj_cap:
            step = len(want) / args.per_traj_cap
            want = {sorted(want)[int(i * step)] for i in range(args.per_traj_cap)}
        new = sorted(want - have[tid])
        base = next(r for r in existing_rows if r["traj_id"] == tid)
        for t in new:
            cid = f"d_{args.corpus}_{tid}_{t}"
            with open(os.path.join(cards_dir, cid + ".md"), "w", encoding="utf-8") as fh:
                fh.write(card(tr, stmts.get(tr.task, ""), t, args.w, cid,
                              extra_note="dense sample, stride-2 refinement"))
            rows.append({"card_id": cid, "corpus": args.corpus, "traj_id": tid, "task": tr.task,
                         "agent": tr.agent, "model": tr.model, "reward": tr.reward,
                         "n_steps": n, "t": t, "w": args.w, "kind": "dense2",
                         "placeholder_frac": base.get("placeholder_frac", ""),
                         "max_msg_repeat_frac": base.get("max_msg_repeat_frac", ""),
                         "hint": base.get("hint", ""), "max_sig_run": base.get("max_sig_run", ""),
                         "final_stall": base.get("final_stall", "")})
    out_index = os.path.join(ann, "dense2_cards_index.csv")
    if rows:
        with open(out_index, "w", newline="", encoding="utf-8") as fh:
            wtr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            wtr.writeheader()
            wtr.writerows(rows)
    print(f"added {len(rows)} refinement cards over {len(todo)} trajectories")
    counts = Counter()
    for t in todo:
        counts[len(have[t] | {int(r["t"]) for r in rows if r["traj_id"] == t})] += 1
    print(f"windows per trajectory now: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
