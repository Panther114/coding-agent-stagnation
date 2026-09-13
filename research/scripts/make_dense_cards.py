"""Dense annotation sample: several windows per trajectory, spanning the whole run.

Why a second, denser sample exists
----------------------------------
Position sampling with four windows per trajectory gives an unbiased prevalence estimate but
leaves the annotated windows of a trajectory far apart, so contiguous annotated
stagnant/productive *regions* are rare and alarm-level metrics (detection, false stop,
latency, step savings) become unstable.  This script emits a denser sample ---
``--per-traj`` windows spread across the run, at most ``--stride`` steps apart --- so that
consecutive windows of the same label merge into usable regions.

Sampling is stratified by scaffold and by outcome, and enriched (``--enrich``) with
trajectories whose own observable behaviour suggests stagnation, so that both classes are
well represented.  Prevalence must therefore be read from the sparse position sample, while
detector performance is estimated on this dense sample; the paper keeps the two separate.

Usage:
  python scripts/make_dense_cards.py --corpus tb2 --n-traj 60 --per-traj 9 --stride 4
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import paths  # noqa: E402
from export_trace import step_line  # noqa: E402
from loaders import Action, Step, Trajectory, nebius_task_statements, tb2_task_statements  # noqa: E402
from make_annotation_cards import card, quality_flags  # noqa: E402
from normalize import normalize_action  # noqa: E402

PH = re.compile(r"^\$[0-9a-fA-F]{1,4}$")


def load_sample(path: str) -> List[Trajectory]:
    out = []
    for line in open(path, encoding="utf-8"):
        b = json.loads(line)
        steps = [Step(index=i, text=s["text"],
                      actions=[Action(a["name"], a["arg"]) for a in s["actions"]],
                      observation=s["obs"]) for i, s in enumerate(b["steps"])]
        out.append(Trajectory(traj_id=b["traj_id"], task=b["task"], agent=b["agent"], model=b["model"],
                              reward=b["reward"], steps=steps, meta=b["meta"]))
    return out


def stagnation_hint(tr: Trajectory) -> Dict[str, float]:
    """Cheap observable indicators used only to *select* trajectories, never as labels."""
    n = len(tr.steps)
    sigs: List[str] = []
    run, maxrun = 1, 1
    for s in tr.steps:
        for a in s.actions:
            k = normalize_action(a.name, a.arg).signature
            if sigs and k == sigs[-1]:
                run += 1
            else:
                run = 1
            maxrun = max(maxrun, run)
            sigs.append(k)
    from evidence import extract_state
    ver = [extract_state(s.observation) for s in tr.steps]
    n_ver = sum(1 for v in ver if v.exit_code is not None or v.n_failed is not None
                or v.n_passed is not None or v.build_ok is not None or v.error_sig is not None)
    # steps between consecutive verifications with no state change
    stall, last_change = 0, 0
    prev = None
    for i, v in enumerate(ver):
        is_v = (v.exit_code is not None or v.n_failed is not None or v.n_passed is not None
                or v.build_ok is not None or v.error_sig is not None)
        if not is_v:
            continue
        if prev is not None and (v.exit_code, v.n_passed, v.n_failed, v.error_sig) != prev:
            last_change = i
        prev = (v.exit_code, v.n_passed, v.n_failed, v.error_sig)
    stall = n - 1 - last_change if n_ver else 0
    notool = sum(1 for s in tr.steps if not s.actions) / max(1, n)
    ph = sum(1 for s in tr.steps if PH.match((s.observation or "").strip())) / max(1, n)
    return {
        "max_sig_run": float(maxrun),
        "final_stall": float(stall),
        "stall_frac": stall / max(1, n),
        "no_tool_frac": notool,
        "ph_frac": ph,
        "n_ver": float(n_ver),
        "hint": float(max(maxrun - 3, 0) + stall / 6.0 + notool * 3.0),
    }


def dense_windows(n: int, per: int, w: int, stride: int, rng: random.Random) -> List[int]:
    """``per`` window end points spread over [w-1, n-1] with spacing <= ``stride``."""
    lo, hi = w - 1, n - 1
    if hi < lo:
        return []
    span = hi - lo
    step = max(1, min(stride, max(1, span // max(1, per - 1))))
    ends: List[int] = []
    t = lo + rng.randrange(0, max(1, step))
    while len(ends) < per and t <= hi:
        ends.append(int(t))
        t += step + rng.randrange(0, max(1, step // 2 + 1))
    while len(ends) < per:
        nxt = min(hi, ends[-1] + 1)
        if nxt <= ends[-1]:
            break
        ends.append(int(nxt))
    return sorted(set(ends))[:per]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--n-traj", type=int, default=60)
    ap.add_argument("--per-traj", type=int, default=9)
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--min-steps", type=int, default=35)
    ap.add_argument("--enrich-frac", type=float, default=0.5,
                    help="share of trajectories drawn from the highest stagnation-hint ranks")
    ap.add_argument("--seed", type=int, default=101)
    args = ap.parse_args()

    proc = os.path.join(paths.PROCESSED, args.corpus)
    ann = os.path.join(paths.DATA, "annotations", args.corpus)
    cards_dir = os.path.join(ann, "cards_dense")
    os.makedirs(cards_dir, exist_ok=True)
    trajs = load_sample(os.path.join(proc, "sample_trajectories.jsonl"))
    stmts = tb2_task_statements() if args.corpus == "tb2" else nebius_task_statements()

    flags = {t.traj_id: quality_flags(t) for t in trajs}
    usable = [t for t in trajs if not flags[t.traj_id]["exclude"] and len(t.steps) >= args.min_steps]
    rng = random.Random(args.seed)
    hints = {t.traj_id: stagnation_hint(t) for t in usable}

    # per-scaffold quotas so no scaffold dominates
    by_agent: Dict[str, List[Trajectory]] = defaultdict(list)
    for t in usable:
        by_agent[t.agent].append(t)
    agents = sorted(by_agent, key=lambda a: -len(by_agent[a]))
    quota = max(2, args.n_traj // max(1, len(agents)))

    picked: List[Trajectory] = []
    for agent in agents:
        pool = sorted(by_agent[agent], key=lambda t: -hints[t.traj_id]["hint"])
        n_enrich = int(round(quota * args.enrich_frac))
        chosen = pool[:n_enrich]
        rest = pool[n_enrich:]
        rng.shuffle(rest)
        # balance outcomes inside the random part
        by_rew = {0: [t for t in rest if t.reward == 0], 1: [t for t in rest if t.reward == 1]}
        while len(chosen) < quota and any(by_rew.values()):
            for r in (1, 0):
                if by_rew[r] and len(chosen) < quota:
                    chosen.append(by_rew[r].pop())
        picked.extend(chosen[:quota])
    picked = picked[: args.n_traj]
    print(f"candidates {len(usable)} -> picked {len(picked)} across {len(set(t.agent for t in picked))} scaffolds")
    print(f"reward mix: {Counter(t.reward for t in picked)}")

    rows: List[Dict[str, Any]] = []
    for tr in picked:
        f = flags[tr.traj_id]
        h = hints[tr.traj_id]
        ends = dense_windows(len(tr.steps), args.per_traj, args.w, args.stride, rng)
        for t in ends:
            cid = f"d_{args.corpus}_{tr.traj_id}_{t}"
            with open(os.path.join(cards_dir, cid + ".md"), "w", encoding="utf-8") as fh:
                fh.write(card(tr, stmts.get(tr.task, ""), t, args.w, cid,
                              extra_note="dense position sample (stratified by scaffold and outcome)"))
            rows.append({"card_id": cid, "corpus": args.corpus, "traj_id": tr.traj_id, "task": tr.task,
                         "agent": tr.agent, "model": tr.model, "reward": tr.reward,
                         "n_steps": len(tr.steps), "t": t, "w": args.w, "kind": "dense",
                         "placeholder_frac": round(f["placeholder_frac"], 3),
                         "max_msg_repeat_frac": round(f["max_msg_repeat_frac"], 3),
                         "hint": round(h["hint"], 2), "max_sig_run": int(h["max_sig_run"]),
                         "final_stall": int(h["final_stall"])})
    with open(os.path.join(ann, "dense_cards_index.csv"), "w", newline="", encoding="utf-8") as fh:
        wtr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    print(f"wrote {len(rows)} dense cards to {cards_dir}")
    print(f"windows per trajectory: {Counter(Counter(r['traj_id'] for r in rows).values())}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
