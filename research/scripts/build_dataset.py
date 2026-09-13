"""Build preprocessed trajectory views and the window feature matrix.

Usage:
  python scripts/build_dataset.py --corpus tb2 --n 1500 --out data/processed/tb2
  python scripts/build_dataset.py --corpus nebius --n 1200 --out data/processed/nebius
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

import loaders  # noqa: E402
import paths  # noqa: E402
from evidence import task_terms  # noqa: E402
from features import (ALL_FEATURES, META_FEATURES, TrajView, build_step_view,  # noqa: E402
                      compute_window_features, first_seen_index)
from normalize import normalize_action  # noqa: E402

TERM_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")


def stratified_sample(trajs, n, seed=0):
    """Sample across (agent, reward, length bucket) strata, round-robin."""
    rng = random.Random(seed)
    buckets: Dict[Any, List[Any]] = {}
    for t in trajs:
        nb = len(t.steps)
        lb = "s" if nb < 25 else ("m" if nb < 60 else ("l" if nb < 150 else "xl"))
        buckets.setdefault((t.agent, t.reward, lb), []).append(t)
    for v in buckets.values():
        rng.shuffle(v)
    keys = sorted(buckets, key=lambda k: -len(buckets[k]))
    out, i = [], 0
    while len(out) < n and any(buckets[k] for k in keys):
        k = keys[i % len(keys)]
        if buckets[k]:
            out.append(buckets[k].pop())
        i += 1
    return out


def build_views(trajs, statements: Dict[str, str], semantic: bool = False) -> List[TrajView]:
    views: List[TrajView] = []
    for tr in trajs:
        terms = task_terms(statements.get(tr.task, ""))
        steps = []
        for s in tr.steps:
            acts = [normalize_action(a.name, a.arg) for a in s.actions]
            steps.append(build_step_view(s.index, s.text, acts, s.observation, terms, {}))
        finish = None
        for s in tr.steps:
            for a in s.actions:
                if normalize_action(a.name, a.arg).kind == "control" and re.search(
                        r"mark_task_complete|finish|end_execution|COMPLETE_TASK", a.name + a.arg):
                    finish = s.index
                    break
            if finish is not None:
                break
        views.append(TrajView(
            traj_id=tr.traj_id, task=tr.task, agent=tr.agent, model=tr.model,
            reward=tr.reward, steps=steps, finish_step=finish, meta=dict(tr.meta),
        ))
    return views


def compute_idf(views: List[TrajView], corpus: str) -> Dict[str, float]:
    df: Counter = Counter()
    n = 0
    for v in views:
        n += 1
        seen = set()
        for s in v.steps:
            for k, val in s.entities:
                for t in TERM_RE.findall(val.lower()):
                    seen.add(("e", t))
            for a in s.actions:
                for t in TERM_RE.findall(a.signature.lower()):
                    seen.add(("a", t))
        for kind, t in seen:
            df[t] += 1
    idf = {t: math.log(n / (1.0 + c)) for t, c in df.items() if c < 0.25 * n}
    return idf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=["tb2", "nebius"], default="tb2")
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--out", required=True)
    ap.add_argument("--windows", default="10")
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--rel-threshold", type=float, default=0.5)
    args = ap.parse_args()
    t0 = time.time()

    if args.corpus == "tb2":
        all_tr = loaders.load_tb2()
        statements = loaders.tb2_task_statements()
    else:
        all_tr = loaders.load_nebius()
        statements = loaders.nebius_task_statements()
    print(f"loaded {len(all_tr)} trajectories in {time.time()-t0:.1f}s")

    sample = stratified_sample(all_tr, args.n, seed=args.seed)
    print(f"samples: {len(sample)}  tasks={len(set(t.task for t in sample))} "
          f"agents={len(set(t.agent for t in sample))} models={len(set(t.model for t in sample))}")

    views = build_views(sample, statements)
    idf = compute_idf(views, args.corpus)
    for v in views:
        v.idf = idf
    print(f"views built in {time.time()-t0:.1f}s; idf terms={len(idf)}")

    windows = [int(x) for x in args.windows.split(",")]
    rows: List[Dict[str, Any]] = []
    traj_rows: List[Dict[str, Any]] = []
    for vi, v in enumerate(views):
        terms = task_terms(statements.get(v.task, ""))
        fseen = first_seen_index(v)
        cfg = {"rel_threshold": args.rel_threshold, "_terms": terms}
        traj_rows.append({
            "traj_id": v.traj_id, "corpus": args.corpus, "task": v.task, "agent": v.agent,
            "model": v.model, "reward": v.reward, "n_steps": v.n_steps,
            "finish_step": v.finish_step, "duration_seconds": v.meta.get("duration_seconds"),
            "exit_status": v.meta.get("exit_status"),
            "task_statement_chars": len(statements.get(v.task, "")),
            "has_task_statement": bool(statements.get(v.task)),
        })
        for w in windows:
            for t in range(0, v.n_steps, args.stride):
                if t + 1 < min(w, 3):
                    continue
                feats = compute_window_features(v, t, w, fseen, cfg)
                rec = {"traj_id": v.traj_id, "corpus": args.corpus, "task": v.task,
                       "agent": v.agent, "model": v.model, "reward": v.reward,
                       "n_steps": v.n_steps, "t": t, "w": w}
                rec.update({k: feats.get(k, float("nan")) for k in ALL_FEATURES + META_FEATURES})
                rows.append(rec)
        if vi % 200 == 0:
            print(f"  featurised {vi}/{len(views)} ({len(rows)} window rows) {time.time()-t0:.0f}s")

    os.makedirs(args.out, exist_ok=True)
    fcols = ALL_FEATURES + META_FEATURES
    table = pa.table({
        **{k: pa.array([r[k] for r in rows], type=pa.float64()) for k in fcols},
        "traj_id": pa.array([r["traj_id"] for r in rows], type=pa.string()),
        "corpus": pa.array([r["corpus"] for r in rows], type=pa.string()),
        "task": pa.array([r["task"] for r in rows], type=pa.string()),
        "agent": pa.array([r["agent"] for r in rows], type=pa.string()),
        "model": pa.array([r["model"] for r in rows], type=pa.string()),
        "reward": pa.array([r["reward"] for r in rows], type=pa.int64()),
        "n_steps": pa.array([r["n_steps"] for r in rows], type=pa.int64()),
        "t": pa.array([r["t"] for r in rows], type=pa.int64()),
        "w": pa.array([r["w"] for r in rows], type=pa.int64()),
    })
    pq.write_table(table, os.path.join(args.out, "windows.parquet"))
    pq.write_table(pa.Table.from_pylist(traj_rows), os.path.join(args.out, "trajectories.parquet"))
    with open(os.path.join(args.out, "build_config.json"), "w", encoding="utf-8") as fh:
        json.dump({"args": vars(args), "n_views": len(views), "n_window_rows": len(rows),
                   "n_idf_terms": len(idf), "seconds": time.time() - t0,
                   "built_at": time.strftime("%Y-%m-%d %H:%M:%S")}, fh, indent=2)

    # cache the sampled raw trajectories for annotation / trace export
    blob = []
    for tr in sample:
        blob.append({
            "traj_id": tr.traj_id, "task": tr.task, "agent": tr.agent, "model": tr.model,
            "reward": tr.reward, "meta": tr.meta,
            "steps": [{"text": s.text, "actions": [{"name": a.name, "arg": a.arg} for a in s.actions],
                       "obs": s.observation} for s in tr.steps],
        })
    with open(os.path.join(args.out, "sample_trajectories.jsonl"), "w", encoding="utf-8") as fh:
        for b in blob:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")
    print(f"rows={len(rows)} written to {args.out} in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
