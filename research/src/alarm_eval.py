"""Window-level alarm evaluation with tolerance.

Motivation
----------
Comparing a monitor's *first* alarm with per-trajectory gold regions is statistically weak:
the evaluation collapses to a few dozen runs, and an alarm a few steps outside a labelled
window is scored as an error even though no annotator looked there.  This module defines the
finest-grained honest operational metric that our annotations support:

For each annotated window $R$ with label $y$ (stagnant / productive) and each alarm threshold,
the alarm is *triggered on R* when at least one sustained alarm falls inside
$R \\pm \\tau$ steps.  Then

* detection rate  = fraction of stagnant windows with a triggered alarm,
* false-stop rate = fraction of productive windows with a triggered alarm,
* coverage        = the same computation on the *unannotated* windows, which measures how
  often the monitor fires at all (a monitor that never fires has coverage zero).

Reporting coverage alongside detection is what makes this metric trustworthy: a monitor
cannot buy a low false-stop rate by staying silent, because silence shows up as zero coverage.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


def window_alarm_matrix(alarms: Dict[str, Optional[int]], windows: Sequence[Tuple[int, int]],
                        tau: int) -> np.ndarray:
    """Boolean vector: was an alarm triggered inside each window (expanded by ``tau``)?"""
    fired = sorted(a for a in alarms.values() if a is not None)
    out = np.zeros(len(windows), dtype=bool)
    if not fired:
        return out
    arr = np.asarray(fired)
    for i, (a, b) in enumerate(windows):
        lo, hi = a - tau, b + tau
        j = np.searchsorted(arr, lo, side="left")
        out[i] = j < len(arr) and arr[j] <= hi
    return out


def evaluate_window_alarms(
    per_threshold: Dict[float, Dict[str, Dict[str, Optional[int]]]],
    gold_windows: Dict[str, List[Dict[str, Any]]],
    all_windows: Dict[str, List[Tuple[int, int]]],
    tau: int = 2,
) -> List[Dict[str, Any]]:
    """Detection / false-stop / coverage curves over alarm thresholds.

    ``per_threshold[th][traj_id][unused_key]`` is not used; instead the caller passes, for
    each threshold and trajectory, the *set* of alarmed steps.  To keep the interface small we
    accept ``per_threshold[th][traj_id] = {threshold: first_alarm}`` as produced by the
    runner and expand it to all alarmed steps by re-running the sustained rule downstream.
    """
    raise NotImplementedError("use evaluate_from_step_alarms")


def evaluate_from_step_alarms(
    step_alarms: Dict[float, Dict[str, Sequence[int]]],
    gold_windows: Dict[str, List[Dict[str, Any]]],
    unlabelled_windows: Dict[str, List[Tuple[int, int]]],
    tau: int = 2,
) -> List[Dict[str, Any]]:
    """``step_alarms[th][traj_id]`` = list of steps at which the monitor alarms."""
    rows: List[Dict[str, Any]] = []
    for th in sorted(step_alarms):
        det_n = det_tot = fs_n = fs_tot = cov_n = cov_tot = 0
        n_traj_alarm = n_traj = 0
        for tid, wins in gold_windows.items():
            alarms = step_alarms[th].get(tid, [])
            arr = np.asarray(sorted(alarms), dtype=int) if len(alarms) else np.zeros(0, dtype=int)
            n_traj += 1
            if arr.size:
                n_traj_alarm += 1
            for w in wins:
                a, b = int(w["lo"]), int(w["hi"])
                hit = bool(arr.size) and bool(((arr >= a - tau) & (arr <= b + tau)).any())
                if w["binary"] == 1:
                    det_tot += 1
                    det_n += int(hit)
                elif w["binary"] == 0:
                    fs_tot += 1
                    fs_n += int(hit)
            for (a, b) in unlabelled_windows.get(tid, []):
                hit = bool(arr.size) and bool(((arr >= a - tau) & (arr <= b + tau)).any())
                cov_tot += 1
                cov_n += int(hit)
        rows.append({
            "threshold": float(th),
            "detection_rate": det_n / det_tot if det_tot else float("nan"),
            "n_positive_windows": det_tot,
            "false_stop_rate": fs_n / fs_tot if fs_tot else float("nan"),
            "n_negative_windows": fs_tot,
            "coverage": cov_n / cov_tot if cov_tot else float("nan"),
            "n_unlabelled_windows": cov_tot,
            "alarm_rate_per_traj": n_traj_alarm / n_traj if n_traj else float("nan"),
            "n_traj": n_traj,
            "balanced_accuracy": ((det_n / det_tot if det_tot else 0.0)
                                  + (1 - fs_n / fs_tot if fs_tot else 0.0)) / 2,
        })
    return rows


def summarise_window_frontier(curve: Sequence[Dict[str, Any]], budgets: Sequence[float]) -> List[Dict[str, Any]]:
    out = []
    for b in budgets:
        feas = [c for c in curve if c["false_stop_rate"] == c["false_stop_rate"]
                and c["false_stop_rate"] <= b + 1e-12]
        if not feas:
            out.append({"budget": b, "available": 0.0, "threshold": float("nan"),
                        "detection_rate": float("nan"), "false_stop_rate": float("nan"),
                        "coverage": float("nan"), "balanced_accuracy": float("nan")})
            continue
        best = max(feas, key=lambda c: (c["detection_rate"], c["coverage"]))
        out.append({"budget": b, "available": 1.0, "threshold": best["threshold"],
                    "detection_rate": best["detection_rate"],
                    "false_stop_rate": best["false_stop_rate"],
                    "coverage": best["coverage"],
                    "balanced_accuracy": best["balanced_accuracy"],
                    "n_positive_windows": best["n_positive_windows"],
                    "n_negative_windows": best["n_negative_windows"]})
    return out


def bootstrap_ci(values: Sequence[float], n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> Tuple[float, float, float]:
    a = np.asarray([v for v in values if v == v], dtype=float)
    if a.size == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    m = a[idx].mean(axis=1)
    return float(a.mean()), float(np.percentile(m, 100 * alpha / 2)), float(np.percentile(m, 100 * (1 - alpha / 2)))
