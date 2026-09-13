"""Collect every number the paper quotes into one JSON, from the frozen artifacts.

Usage: python scripts/collect_paper_numbers.py --run results/final/tb2 --corpus tb2
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

import paths  # noqa: E402
from evaluation import window_metrics  # noqa: E402
from features import FEATURE_CHANNEL  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--ann", default=None)
    ap.add_argument("--w", type=int, default=10)
    args = ap.parse_args()
    ann = args.ann or os.path.join(paths.DATA, "annotations", args.corpus)
    out: Dict[str, Any] = {}

    cfg = json.load(open(os.path.join(args.run, "run_config.json"), encoding="utf-8"))
    out["setup"] = {k: cfg[k] for k in ("n_traj", "n_window_rows", "n_annotated_windows",
                                        "n_alarm_eval_traj", "n_alarm_eval_traj_with_region",
                                        "folds", "tasks_per_fold", "has_semantic",
                                        "min_step_margin", "tolerance") if k in cfg}
    agree = json.load(open(os.path.join(ann, "agreement.json"), encoding="utf-8"))
    out["annotation"] = agree

    summary_path = os.path.join(paths.FINAL, f"summary_{args.corpus}.json")
    if os.path.exists(summary_path):
        out["corpus"] = json.load(open(summary_path, encoding="utf-8"))

    # per-window feature tables
    rows = pq.read_table(os.path.join(args.run, "window_features.parquet")).to_pylist()
    labelled = [r for r in rows if r["binary"] is not None]
    y = np.array([r["binary"] for r in labelled])
    out["labelled_windows"] = {"n": len(labelled), "positive": int(y.sum()),
                               "prevalence": float(y.mean()) if len(y) else None}

    feat_tbl: Dict[str, Any] = {}
    for f, ch in FEATURE_CHANNEL.items():
        x = np.array([r.get(f, np.nan) for r in labelled], dtype=float)
        if np.all(np.isnan(x)) or np.nanstd(x) == 0:
            continue
        x2 = np.nan_to_num(x, nan=float(np.nanmean(x)))
        m = window_metrics(y, x2)
        if m["roc_auc"] != m["roc_auc"]:
            continue
        feat_tbl[f] = {"channel": ch, "roc_auc": m["roc_auc"], "pr_auc": m["pr_auc"],
                       "mean_pos": float(np.nanmean(x[y == 1])) if (y == 1).any() else None,
                       "mean_neg": float(np.nanmean(x[y == 0])) if (y == 0).any() else None}
    out["features"] = feat_tbl
    best_by_channel = {}
    for ch in ("REP", "NOV", "EVID", "VER", "WORK", "SEM"):
        items = [(f, v) for f, v in feat_tbl.items() if v["channel"] == ch]
        if items:
            f, v = max(items, key=lambda kv: abs(kv[1]["roc_auc"] - 0.5))
            best_by_channel[ch] = {"feature": f, "roc_auc": v["roc_auc"],
                                   "mean_pos": v["mean_pos"], "mean_neg": v["mean_neg"]}
    out["best_feature_per_channel"] = best_by_channel

    # label statistics
    adj = list(csv.DictReader(open(os.path.join(ann, "adjudicated.csv"), encoding="utf-8")))
    per_agent = defaultdict(lambda: Counter())
    for a in adj:
        if a["binary"] in {"0", "1"}:
            per_agent[a["agent"]]["POS" if a["binary"] == "1" else "NEG"] += 1
    out["label_by_scaffold"] = {k: dict(v) for k, v in per_agent.items()}
    rew = defaultdict(Counter)
    for a in adj:
        if a["binary"] in {"0", "1"}:
            rew[a["reward"]]["POS" if a["binary"] == "1" else "NEG"] += 1
    out["label_by_reward"] = {k: dict(v) for k, v in rew.items()}
    out["subtypes"] = dict(Counter(a["detail"] for a in adj if a["detail"]).most_common())
    out["channels_advanced"] = dict(Counter(a["channels"] for a in adj if a["channels"]).most_common())

    # monitor tables
    for name in ("window_metrics.json", "window_alarm_frontier.json", "alarm_frontier.json",
                 "descriptive.json", "outcome_association.json", "logistic_report.json"):
        p = os.path.join(args.run, name)
        if os.path.exists(p):
            out[name.replace(".json", "")] = json.load(open(p, encoding="utf-8"))

    # compact headline for each monitor at w
    wl = out.get("window_metrics", {})
    front = out.get("window_alarm_frontier", {})
    headline = {}
    for name in sorted(wl):
        m = wl[name].get(str(args.w)) or wl[name].get(args.w)
        fr = front.get(name, [])
        if isinstance(fr, dict):
            fr = fr.get(str(args.w)) or fr.get(args.w) or []
        by = {round(f["budget"], 2): f for f in fr}
        headline[name] = {
            "roc_auc": m["roc_auc"] if m else None,
            "pr_auc": m["pr_auc"] if m else None,
            "f1_best": m["f1_best"] if m else None,
            "det_at_5pct": by.get(0.05, {}).get("detection_rate"),
            "fs_at_5pct": by.get(0.05, {}).get("false_stop_rate"),
            "cov_at_5pct": by.get(0.05, {}).get("coverage"),
            "det_at_10pct": by.get(0.10, {}).get("detection_rate"),
        }
    out["headline"] = headline

    dest = os.path.join(args.run, "paper_numbers.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {dest}")
    print(json.dumps(headline, indent=2)[:3000])
    print("\nbest feature per channel:")
    for ch, v in best_by_channel.items():
        print(f"  {ch:5} {v['feature']:28} auc={v['roc_auc']:.3f} "
              f"mean_pos={v['mean_pos']:.3f} mean_neg={v['mean_neg']:.3f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
