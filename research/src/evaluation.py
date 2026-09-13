"""Evaluation: window classification metrics and operational alarm metrics.

Two levels of evaluation are implemented, because they answer different questions:

**Window level.**  Given the features of a window, how well does a monitor rank
stagnant windows above productive ones?  Reported as ROC-AUC, PR-AUC (average
precision), F1 at the best threshold, precision and recall at fixed thresholds.

**Alarm level.**  A monitor is run sequentially and allowed to fire once per
trajectory.  We then ask operational questions under an explicit false-stop budget:

* *false stop* - the alarm fires in a region that annotators called productive
  (or before the first stagnant region begins) while the trajectory still had
  productive work left.  A false stop is the expensive error, so all alarm metrics
  are conditioned on a maximum false-stop rate.
* *detected* - the alarm fires inside a gold stagnant region.
* *detection latency* - steps between the start of the gold stagnant region and the alarm.
* *avoidable steps saved* - steps between the alarm and the end of the gold stagnant
  region, i.e. execution the monitor removed that annotators agreed was not progress.

Step accounting is deliberately signed: firing early in a productive stretch *costs*
steps (it discards work the annotator called productive), so a monitor cannot win by
always alarming.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:
    from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
except Exception:  # pragma: no cover
    average_precision_score = roc_auc_score = roc_curve = None


# --------------------------------------------------------------------------------------
# Window-level metrics
# --------------------------------------------------------------------------------------


def bootstrap_ci(values: Sequence[float], n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> Tuple[float, float, float]:
    """Percentile bootstrap CI of the mean."""
    a = np.asarray([v for v in values if v == v], dtype=float)
    if a.size == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    means = a[idx].mean(axis=1)
    return float(a.mean()), float(np.percentile(means, 100 * alpha / 2)), float(np.percentile(means, 100 * (1 - alpha / 2)))


def clustered_bootstrap_ci(cluster_ids: Sequence, values: Sequence[float], n_boot: int = 2000,
                           alpha: float = 0.05, seed: int = 0) -> Tuple[float, float, float]:
    """Bootstrap the mean by resampling clusters (e.g. trajectories or tasks)."""
    df: Dict[Any, List[float]] = {}
    for c, v in zip(cluster_ids, values):
        if v == v:
            df.setdefault(c, []).append(v)
    keys = list(df)
    if not keys:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), size=len(keys))
        vals = [v for k in pick for v in df[keys[k]]]
        means.append(float(np.mean(vals)) if vals else float("nan"))
    point = float(np.mean([v for k in keys for v in df[k]]))
    return point, float(np.nanpercentile(means, 100 * alpha / 2)), float(np.nanpercentile(means, 100 * (1 - alpha / 2)))


def window_metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, float]:
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    ok = ~np.isnan(p)
    y, p = y[ok], p[ok]
    out: Dict[str, float] = {"n": float(len(y)), "prev": float(y.mean()) if len(y) else float("nan")}
    if len(y) == 0 or len(np.unique(y)) < 2:
        out.update({"roc_auc": float("nan"), "pr_auc": float("nan"), "f1_best": float("nan"),
                    "thr_best": float("nan"), "prec_at_best": float("nan"), "rec_at_best": float("nan")})
        return out
    out["roc_auc"] = float(roc_auc_score(y, p)) if roc_auc_score else float("nan")
    out["pr_auc"] = float(average_precision_score(y, p)) if average_precision_score else float("nan")
    # best F1 over candidate thresholds
    best = (-1.0, 0.5, 0.0, 0.0)
    for thr in np.unique(np.round(p, 4)):
        pred = p >= thr
        tp = float(np.sum(pred & (y == 1)))
        fp = float(np.sum(pred & (y == 0)))
        fn = float(np.sum(~pred & (y == 1)))
        if tp == 0:
            continue
        prec = tp / (tp + fp)
        rec = tp / (tp + fn)
        f1 = 2 * prec * rec / (prec + rec)
        if f1 > best[0]:
            best = (f1, float(thr), prec, rec)
    out["f1_best"], out["thr_best"], out["prec_at_best"], out["rec_at_best"] = best
    return out


def within_group_auc(y: np.ndarray, p: np.ndarray, groups: Sequence) -> Tuple[float, int]:
    """Mean AUC computed *inside* each group (e.g. each trajectory).

    This is the honest version of window-level discrimination when windows are sampled densely
    within a run.  A globally computed AUC can be inflated by between-run separation: if one
    trajectory is entirely stagnant and another entirely productive, a monitor that only
    recognises "this run is going badly" scores well without discriminating neighbouring
    windows of the same run.  ``y``, ``p`` and ``groups`` must be aligned.
    """
    from collections import defaultdict as _dd
    buckets: Dict[Any, List[Tuple[int, float]]] = _dd(list)
    for yy, pp, g in zip(y, p, groups):
        if pp == pp:
            buckets[g].append((int(yy), float(pp)))
    aucs: List[float] = []
    for g, items in buckets.items():
        ys = [a for a, _ in items]
        if len(set(ys)) < 2:
            continue
        m = window_metrics(np.array(ys), np.array([b for _, b in items]))
        if m["roc_auc"] == m["roc_auc"]:
            aucs.append(m["roc_auc"])
    if not aucs:
        return float("nan"), 0
    return float(np.mean(aucs)), len(aucs)


def precision_recall_at(y: np.ndarray, p: np.ndarray, thr: float) -> Dict[str, float]:
    pred = np.asarray(p) >= thr
    tp = float(np.sum(pred & (y == 1)))
    fp = float(np.sum(pred & (y == 0)))
    fn = float(np.sum(~pred & (y == 1)))
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if prec == prec and rec == rec and (prec + rec) > 0 else float("nan")
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


# --------------------------------------------------------------------------------------
# Alarm-level evaluation
# --------------------------------------------------------------------------------------


@dataclass
class TrajGold:
    """Independent (annotated) ground truth for one trajectory."""

    traj_id: str
    task: str
    agent: str
    n_steps: int
    reward: Optional[int]
    # (start, end) inclusive step ranges annotated STAGNANT or DONE_REDUNDANT
    stagnant: List[Tuple[int, int]] = field(default_factory=list)
    # (start, end) inclusive ranges annotated PRODUCTIVE / REGRESSION
    productive: List[Tuple[int, int]] = field(default_factory=list)
    windows: List[Dict[str, Any]] = field(default_factory=list)


def _in_any(t: int, ranges: Sequence[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    for a, b in ranges:
        if a <= t <= b:
            return (a, b)
    return None


def alarm_outcome(alarm: Optional[int], gold: TrajGold, min_step: int = 0) -> Dict[str, Any]:
    """Classify one alarm against the annotated gold regions of a trajectory."""
    res: Dict[str, Any] = {"alarm": alarm, "outcome": "no_alarm", "detected": 0, "false_stop": 0,
                           "latency": None, "saved_alarm": 0.0, "saved_oracle": 0.0,
                           "region": None, "n_stagnant_regions": len(gold.stagnant)}
    # oracle upper bound: stops at the start of the first annotated stagnant region
    if gold.stagnant:
        first_start = min(a for a, _ in gold.stagnant)
        res["saved_oracle"] = float(gold.n_steps - first_start)
    if alarm is None or alarm < min_step:
        res["saved_alarm"] = 0.0
        return res
    res["saved_alarm"] = float(gold.n_steps - alarm)
    hit = _in_any(alarm, gold.stagnant)
    if hit is not None:
        res["outcome"] = "detected"
        res["detected"] = 1
        res["latency"] = int(alarm - hit[0])
        res["region"] = hit
        return res
    miss = _in_any(alarm, gold.productive)
    if miss is not None or not gold.stagnant:
        # fired in a region annotators called productive, or in a trajectory with no
        # annotated stagnation at all
        res["outcome"] = "false_stop"
        res["false_stop"] = 1
        res["region"] = miss
        # a false stop destroys the remaining productive work
        res["saved_alarm"] = -float(gold.n_steps - alarm)
        return res
    if gold.stagnant and alarm < min(a for a, _ in gold.stagnant):
        res["outcome"] = "early"
        res["false_stop"] = 1
        res["region"] = None
        res["saved_alarm"] = -float(gold.n_steps - alarm)
    else:
        res["outcome"] = "ambiguous"
    return res


def alarm_metrics(rows: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    n = len(rows)
    if n == 0:
        return {"n_traj": 0.0, "false_stop_rate": float("nan"), "detection_rate": float("nan"),
                "mean_saved_steps": float("nan"), "savings_ratio": float("nan"),
                "median_latency": float("nan"), "n_alarms": 0.0, "alarm_rate": float("nan")}
    fs = np.array([r["false_stop"] for r in rows], dtype=float)
    det = np.array([r["detected"] for r in rows], dtype=float)
    saved = np.array([r["saved_alarm"] for r in rows], dtype=float)
    oracle = np.array([r["saved_oracle"] for r in rows], dtype=float)
    fired = np.array([1.0 if r["alarm"] is not None else 0.0 for r in rows])
    lat = [r["latency"] for r in rows if r["latency"] is not None]
    poss = oracle > 0
    out = {
        "n_traj": float(n),
        "alarm_rate": float(fired.mean()),
        "false_stop_rate": float(fs.mean()),
        "detection_rate": float(det.mean()),
        "detection_rate_where_possible": float(det[poss].mean()) if poss.any() else float("nan"),
        "n_possible": float(poss.sum()),
        "mean_saved_steps": float(saved.mean()),
        "total_saved_steps": float(saved.sum()),
        "median_saved_steps": float(np.median(saved)),
        "mean_saved_where_positive": float(saved[poss].mean()) if poss.any() else float("nan"),
        "oracle_saved_steps": float(oracle.sum()),
        "savings_ratio": float(saved.sum() / oracle.sum()) if oracle.sum() > 0 else float("nan"),
        "median_latency": float(np.median(lat)) if lat else float("nan"),
        "mean_latency": float(np.mean(lat)) if lat else float("nan"),
        "n_alarms": float(fired.sum()),
    }
    return out


def savings_curve(per_threshold: Dict[float, List[Dict[str, Any]]]) -> List[Dict[str, float]]:
    """Mean savings and false-stop rate for each alarm threshold."""
    out = []
    for thr, rows in sorted(per_threshold.items()):
        m = alarm_metrics(rows)
        m["threshold"] = float(thr)
        out.append(m)
    return out


def budget_frontier(curve: Sequence[Dict[str, float]], budgets: Sequence[float]) -> List[Dict[str, float]]:
    """At each false-stop budget, the best achievable net savings among thresholds.

    A threshold is feasible only if it satisfies ``false_stop_rate <= budget``; when no
    threshold does, the entry is reported as unavailable rather than as zero.
    """
    out = []
    for b in budgets:
        feas = [c for c in curve
                if c.get("false_stop_rate") == c.get("false_stop_rate")
                and c["false_stop_rate"] <= b + 1e-12]
        if not feas:
            out.append({"budget": b, "threshold": float("nan"), "false_stop_rate": float("nan"),
                        "detection_rate": float("nan"), "detection_rate_where_possible": float("nan"),
                        "mean_saved_steps": float("nan"), "savings_ratio": float("nan"),
                        "median_latency": float("nan"), "alarm_rate": float("nan"),
                        "n_alarms": float("nan"), "available": 0.0})
            continue
        best = max(feas, key=lambda c: (c["mean_saved_steps"], c["detection_rate"]))
        out.append({"budget": b, "threshold": best["threshold"],
                    "false_stop_rate": best["false_stop_rate"],
                    "detection_rate": best["detection_rate"],
                    "detection_rate_where_possible": best["detection_rate_where_possible"],
                    "mean_saved_steps": best["mean_saved_steps"],
                    "savings_ratio": best["savings_ratio"],
                    "median_latency": best["median_latency"],
                    "alarm_rate": best["alarm_rate"], "n_alarms": best["n_alarms"],
                    "available": 1.0})
    return out


def summarise_curve_at(curve: Sequence[Dict[str, float]], budget: float) -> Dict[str, float]:
    """Nearest-achievable point of a savings curve for a requested budget."""
    usable = [c for c in curve
              if c.get("false_stop_rate") == c.get("false_stop_rate")
              and c["false_stop_rate"] <= budget + 1e-12]
    if not usable:
        # fall back to the lowest false-stop rate that exists at all
        any_ok = [c for c in curve if c.get("false_stop_rate") == c.get("false_stop_rate")]
        if not any_ok:
            return {}
        best = min(any_ok, key=lambda c: c["false_stop_rate"])
        best = dict(best)
        best["budget"] = budget
        best["note"] = "budget not achievable"
        return best
    best = max(usable, key=lambda c: (c["mean_saved_steps"], c["detection_rate"]))
    best = dict(best)
    best["budget"] = budget
    return best
