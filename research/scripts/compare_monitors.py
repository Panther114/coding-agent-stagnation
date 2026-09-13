"""Paired comparisons between monitors with trajectory-clustered bootstrap intervals.

The question "does monitor A beat monitor B?" is answered on the *same* windows, so the
right statistic is the paired difference with an interval that resamples trajectories (which
are the independent units) rather than windows.

Usage:
  python scripts/compare_monitors.py --run results/final/tb2_v3 --corpus tb2 \
      --pairs C1_evidence:B4_semantic,C3_evid_sem:B4_semantic,L_evid_sem:L_sem
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

import paths  # noqa: E402
from evaluation import window_metrics  # noqa: E402


def load_scores(run: str, w: int) -> Dict[str, Dict[Tuple[str, int], float]]:
    rows = pq.read_table(os.path.join(run, "monitor_scores.parquet")).to_pylist()
    out: Dict[str, Dict[Tuple[str, int], float]] = defaultdict(dict)
    for r in rows:
        if r["w"] != w or r["score"] is None:
            continue
        out[r["monitor"]][(r["traj_id"], r["t"])] = r["score"]
    return out


def load_labels(run: str, w: int) -> Dict[Tuple[str, int], int]:
    rows = pq.read_table(os.path.join(run, "window_features.parquet")).to_pylist()
    return {(r["traj_id"], r["t"]): r["binary"] for r in rows
            if r["w"] == w and r["binary"] is not None}


def fast_auc(y: np.ndarray, p: np.ndarray) -> float:
    """Mann-Whitney AUC via average ranks (much faster than sklearn inside a bootstrap)."""
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    sp = p[order]
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    n_pos = float((y == 1).sum())
    n_neg = float((y == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return (ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def paired_auc_diff(y: np.ndarray, a: np.ndarray, b: np.ndarray, clusters: Sequence[str],
                    n_boot: int = 2000, seed: int = 0) -> Dict[str, float]:
    """AUC(A) - AUC(B) with a trajectory-clustered bootstrap interval."""
    rng = np.random.default_rng(seed)
    by_cluster: Dict[str, List[int]] = defaultdict(list)
    for i, c in enumerate(clusters):
        by_cluster[c].append(i)
    keys = list(by_cluster)
    point_a = fast_auc(y, a)
    point_b = fast_auc(y, b)
    diffs = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), size=len(keys))
        idx = np.concatenate([by_cluster[keys[k]] for k in pick]) if keys else np.arange(len(y))
        yy = y[idx]
        aa = fast_auc(yy, a[idx])
        bb = fast_auc(yy, b[idx])
        if aa == aa and bb == bb:
            diffs.append(aa - bb)
    arr = np.asarray(diffs)
    lo = float(np.percentile(arr, 2.5)) if arr.size else float("nan")
    hi = float(np.percentile(arr, 97.5)) if arr.size else float("nan")
    return {"auc_a": point_a, "auc_b": point_b, "delta": point_a - point_b,
            "lo": lo, "hi": hi,
            "p_two_sided": (2 * min(float(np.mean(arr <= 0)), float(np.mean(arr >= 0)))
                            if arr.size else float("nan")),
            "n_boot": int(arr.size)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--pairs", default=None,
                    help="comma separated A:B pairs; default compares every monitor with the best")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    scores = load_scores(args.run, args.w)
    labels = load_labels(args.run, args.w)
    keys = sorted(labels)
    y = np.array([labels[k] for k in keys])
    clusters = [k[0] for k in keys]
    aucs = {}
    for m, sv in scores.items():
        p = np.array([sv.get(k, np.nan) for k in keys])
        ok = ~np.isnan(p)
        if ok.sum() < 10 or len(set(y[ok].tolist())) < 2:
            continue
        aucs[m] = window_metrics(y[ok], p[ok])["roc_auc"]
    best = max(aucs, key=lambda m: aucs[m]) if aucs else None
    print(f"windows={len(keys)} monitors={len(aucs)} best={best} ({aucs.get(best, float('nan')):.3f})")

    pairs: List[Tuple[str, str]] = []
    if args.pairs:
        for p in args.pairs.split(","):
            a, b = p.split(":")
            pairs.append((a.strip(), b.strip()))
    else:
        for m in sorted(aucs):
            if m != best:
                pairs.append((m, best))

    results = {}
    for a, b in pairs:
        if a not in scores or b not in scores:
            print(f"  {a} vs {b}: missing monitor")
            continue
        pa = np.nan_to_num(np.array([scores[a].get(k, np.nan) for k in keys]), nan=0.0)
        pb = np.nan_to_num(np.array([scores[b].get(k, np.nan) for k in keys]), nan=0.0)
        r = paired_auc_diff(y, pa, pb, clusters)
        results[f"{a}_vs_{b}"] = r
        star = "*" if (r["lo"] > 0 or r["hi"] < 0) else " "
        print(f"  {a:22} {r['auc_a']:.3f}  vs {b:22} {r['auc_b']:.3f}  "
              f"delta={r['delta']:+.3f} [{r['lo']:+.3f},{r['hi']:+.3f}]{star} p={r['p_two_sided']:.3f}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"w": args.w, "best": best, "aucs": aucs, "pairs": results}, fh, indent=2)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
