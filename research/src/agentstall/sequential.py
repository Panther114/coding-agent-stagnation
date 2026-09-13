"""Sequential detection with an honest error guarantee, and the cost model.

Why this module matters
-----------------------
Stagnation monitoring is a **sequential** problem: a runtime looks at the trajectory
after every step, so the number of looks is unbounded and a fixed-horizon p-value or a
threshold on a smoothed score has no interpretable false-alarm rate over the life of a
run.  The first version of the study thresholded a smoothed score and reported an
empirical per-window false-alarm rate, which is not the same quantity.

Two procedures are implemented, both computable online from a per-step score:

1. **E-value / test martingale (anytime-valid).** Under the null ``H0: p <= p0`` (the
   agent is still making progress), the process

       M_t = prod_{i<=t} (1 + lambda_i (X_i - p0)),   X_i in [0, 1]

   is a nonnegative supermartingale for ``lambda_i`` predictable, so
   ``P(there exists t with M_t >= 1/alpha) <= alpha`` **for every stopping rule**.
   Rejecting at the first crossing therefore controls the false-alarm probability
   uniformly over time -- no correction for multiple looks, no assumption about run
   length.  ``lambda_i`` is chosen by the predictable plug-in rule of Waudby-Smith &
   Ramdas (2024) with a bound ``m`` on the number of steps.

2. **CUSUM with a calibrated reference.** The classical one-sided CUSUM on
   ``log(f1/f0)`` with tabular ``f0``/``f1`` fitted on training folds (leave-one-task-out
   so the reference cannot memorise).  Reported as detection delay at a fixed
   pre-registered alarm budget rather than as an AUC.

Reported quantities are the ones a runtime cares about: probability of ever raising an
alarm on a healthy run, detection latency in steps, and detection rate at a budget.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# --------------------------------------------------------------------------------------
# e-value (anytime-valid) detector
# --------------------------------------------------------------------------------------


def causal_quiet_series(events_by_run: Dict[str, np.ndarray], w: int) -> Dict[str, np.ndarray]:
    """Carry each window's verdict forward by a full window: no lookahead.

    A window-level label is computed *inside* the window, so it becomes known only once the
    window has elapsed.  A runtime at step ``t`` may therefore act on the verdicts of
    windows that ended at or before ``t``, i.e. on the verdict shifted by ``w``.  Without
    this shift a detector could alarm on the very window it is supposed to be predicting,
    which is how the first attempt produced a negative median latency.
    """
    out: Dict[str, np.ndarray] = {}
    for rid, ev in events_by_run.items():
        ev = np.asarray(ev, dtype=float)
        if len(ev) > w:
            out[rid] = np.concatenate([np.zeros(w, dtype=float), ev[:-w]])
        else:
            out[rid] = np.zeros_like(ev)
    return out


def prefix_max_run(flags: np.ndarray) -> np.ndarray:
    """Running maximum of the current streak of consecutive True flags.

    A prefix maximum, so a threshold crossed once stays crossed: the alarm time is the
    first crossing and the statistic never decreases, which is what makes a fixed threshold
    give a per-run guarantee rather than a per-window one.
    """
    out = np.zeros(len(flags), dtype=float)
    cur = 0
    best = 0
    for i, f in enumerate(np.asarray(flags)):
        cur = cur + 1 if f else 0
        best = max(best, cur)
        out[i] = best
    return out


def quiet_evidence(event: np.ndarray, q_alt: float = 0.02) -> np.ndarray:
    """Anytime-valid evidence that the run has *stopped* producing progress events.

    The generic e-process in ``e_values`` tests "the event rate exceeds p0", which is the
    wrong direction for stalls: a monitor must detect a sustained *absence* of progress,
    and absence cannot be proven by accumulating evidence for the presence of its
    opposite.  (The first attempt did exactly that and detected 1 run in 4,823.)

    So the hypothesis pair is inverted.  Let ``e_t in {0,1}`` mark a step that produced a
    real progress event (a workspace change, a new entity, a verification-state change).
    Under the *null* the agent is still working, so a quiet step is unremarkable::

        H0: P(e_t = 0) = 0.5      (mediocre but alive)
        H1: P(e_t = 0) = q_alt    (stalled: almost every step is quiet)

    The per-step log-likelihood ratio is ``log((1-q_alt)/0.5)`` for a quiet step and
    ``log(q_alt/0.5)`` for an event, and the cumulative sum is a nonnegative (up to a
    constant) supermartingale under ``H0`` for a fixed ``q_alt``.  Crossing
    ``log(1/alpha)`` therefore bounds the probability of ever crying stall, uniformly over
    time and for any stopping rule -- the guarantee the first version could not state.

    The detector is deliberately *not* the monitor's score: it is the exact sequential test
    for the event it is supposed to find, which makes it the correct ceiling reference.
    """
    ev = np.asarray(event, dtype=float)
    ev = np.where(np.isnan(ev), 0.0, ev)
    lr_quiet = math.log(max((1.0 - q_alt) / 0.5, 1e-12))
    lr_event = math.log(max(q_alt / 0.5, 1e-12))
    inc = np.where(ev > 0.5, lr_event, lr_quiet)
    return np.cumsum(inc)


def quiet_detect(event: np.ndarray, alpha: float = 0.05, q_alt: float = 0.02) -> Optional[int]:
    """First index where the quiet-evidence process crosses log(1/alpha), else None."""
    c = quiet_evidence(event, q_alt=q_alt)
    thr = math.log(1.0 / alpha)
    idx = np.nonzero(c >= thr)[0]
    return int(idx[0]) if len(idx) else None


def quiet_evidence_value(event: np.ndarray, q_alt: float = 0.02) -> np.ndarray:
    """The same process as an e-value in (0, inf): exp(cumsum of log-LR)."""
    c = quiet_evidence(event, q_alt=q_alt)
    return np.exp(np.clip(c, -700, 700))


def e_values(x: np.ndarray, p0: float, m_cap: int = 400,
             lambda_grid: int = 50) -> np.ndarray:
    """Predictable-plug-in e-process for H0: p <= p0, with x_t in [0, 1].

    After Waudby-Smith & Ramdas, *Time-uniform central limit theory and asymptotic
    confidence sequences* (and their betting-based e-process).  ``lambda_t`` is chosen
    from the past only:

        mu_hat_t = (0.5 + sum_{i<=t} x_i) / (t + 1)
        sigma_hat_t = 0.25
        lambda_t = clip(sqrt(2 log(1/alpha_prior) / (m_cap sigma_hat_t^2)), 0, 0.75 / p0)

    The clip at ``1/p0`` keeps ``1 + lambda (x - p0) >= 0`` for ``x in [0, 1]``, which is
    what makes the process a nonnegative supermartingale under the null.
    """
    x = np.clip(np.asarray(x, dtype=float), 0.0, 1.0)
    n = len(x)
    out = np.ones(n, dtype=float)
    logM = 0.0
    run_sum = 0.0
    lam_hi = 0.75 / max(p0, 1e-6)
    for t in range(n):
        mu_hat = (0.5 + run_sum) / (t + 1)
        # betting fraction shrinks toward zero over time but never explodes
        lam = min(0.5, math.sqrt(2.0 * math.log(20.0) / (m_cap * 0.25)))
        lam = min(lam, lam_hi)
        # one-sided: back the alternative p > p0
        logM += math.log(max(1e-300, 1.0 + lam * (x[t] - p0)))
        out[t] = math.exp(min(logM, 700.0))
        run_sum += x[t]
    return out


def e_detect(x: np.ndarray, p0: float, alpha: float = 0.05,
             m_cap: int = 400, min_steps: int = 1) -> Optional[int]:
    """First step index (0-based) where the e-value crosses 1/alpha, else None."""
    ev = e_values(x, p0=p0, m_cap=m_cap)
    thr = 1.0 / alpha
    for t in range(min_steps - 1, len(ev)):
        if ev[t] >= thr:
            return t
    return None


# --------------------------------------------------------------------------------------
# CUSUM with a learned reference
# --------------------------------------------------------------------------------------


def fit_bins(x_ref: np.ndarray, n_bins: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    qs = np.quantile(x_ref, np.linspace(0, 1, n_bins + 1))
    qs = np.unique(qs)
    return qs, np.arange(1, len(qs))


def hist_counts(x: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.histogram(x, bins=edges)[0].astype(float)


def cusum_run(x: np.ndarray, f0: np.ndarray, f1: np.ndarray, edges: np.ndarray,
              h: float = 5.0, warmup: int = 3) -> Optional[int]:
    """One-sided CUSUM on the log-likelihood ratio; returns the first alarm index."""
    s = 0.0
    for t in range(len(x)):
        i = int(np.searchsorted(edges, x[t], side="right") - 1)
        i = max(0, min(i, len(f0) - 1))
        p0 = f0[i]
        p1 = f1[i]
        if p0 <= 0:
            p0 = 1e-6
        if p1 <= 0:
            p1 = 1e-6
        s = max(0.0, s + math.log(p1 / p0))
        if t >= warmup and s >= h:
            return t
    return None


# --------------------------------------------------------------------------------------
# score construction from a window series
# --------------------------------------------------------------------------------------


def per_step_series(df, score_col: str, run_col: str = "run_id",
                    step_col: str = "t") -> Dict[str, np.ndarray]:
    """Expand a window score into a per-step series, per run.

    Steps before the first scored window do not exist as observations, so they are filled
    *backwards* from the first score rather than left as NaN: a NaN in a boolean test is
    silently False, which previously made runs with no scored window look like clean
    negatives and drove the false-alarm rate to zero by accident.
    """
    out: Dict[str, np.ndarray] = {}
    for rid, g in df.groupby(run_col, sort=False):
        g = g.sort_values(step_col)
        n = int(g[step_col].max()) + 1
        xs = np.full(n, np.nan)
        for t, v in zip(g[step_col].to_numpy(), g[score_col].to_numpy()):
            xs[int(t)] = v
        first = np.nonzero(~np.isnan(xs))[0]
        if len(first) == 0:
            out[rid] = np.zeros(n, dtype=float)
            continue
        xs[:first[0]] = xs[first[0]]
        last = np.nan
        for i in range(n):
            if np.isnan(xs[i]):
                xs[i] = last
            else:
                last = xs[i]
        out[rid] = xs
    return out


def rank_normalise(x: np.ndarray) -> np.ndarray:
    """Map a raw score to [0, 1] by its within-run empirical rank (online-safe if
    the ranks are computed in a causal manner; here used only for offline reporting)."""
    x = np.asarray(x, dtype=float)
    good = ~np.isnan(x)
    if good.sum() < 2:
        return np.full_like(x, 0.5)
    r = np.full_like(x, 0.5)
    order = np.argsort(x[good], kind="stable")
    ranks = np.empty(good.sum(), dtype=float)
    ranks[order] = np.arange(good.sum(), dtype=float) / max(1, good.sum() - 1)
    r[good] = ranks
    return r


def evaluate_sequential(series: Dict[str, np.ndarray], healthy: Dict[str, bool],
                        p0: float, alpha: float, m_cap: int = 400) -> Dict[str, float]:
    """Run the e-detector run by run and summarise.

    ``healthy[rid]`` True = the run never stalls under the target definition, so any
    alarm on it is a false alarm.  The guarantee is over the *whole life* of the run,
    which is the quantity the first version could not report.
    """
    n_alarm_healthy = 0
    n_healthy = 0
    dets, lats, missed = 0, [], 0
    n_stalled = 0
    for rid, x in series.items():
        x = np.nan_to_num(x, nan=0.0)
        t = e_detect(x, p0=p0, alpha=alpha, m_cap=m_cap)
        if healthy.get(rid, True):
            n_healthy += 1
            if t is not None:
                n_alarm_healthy += 1
        else:
            n_stalled += 1
            if t is not None:
                dets += 1
                lats.append(t)
            else:
                missed += 1
    return {
        "n_runs": len(series),
        "n_healthy": n_healthy,
        "n_stalled": n_stalled,
        "false_alarm_rate": (n_alarm_healthy / n_healthy) if n_healthy else float("nan"),
        "detection_rate": (dets / n_stalled) if n_stalled else float("nan"),
        "n_detected": dets,
        "median_latency_steps": float(np.median(lats)) if lats else float("nan"),
        "alpha": alpha,
        "p0": p0,
    }


# --------------------------------------------------------------------------------------
# cost model
# --------------------------------------------------------------------------------------


def policy_value(run_df, decide_step: np.ndarray, step_cost: float = 1.0,
                 tokens_per_step: Optional[np.ndarray] = None) -> Dict[str, float]:
    """Value of a stop-at-``t`` policy relative to running to completion.

    ``decide_step[run_id]`` is the step at which the policy would stop the run (or None).
    A stopped-run success probability must be supplied by the caller: offline we can only
    report the *ceiling* of what such a policy could earn, plus the steps it saves.  This
    keeps the analysis honest -- no offline replay can measure whether stopping would have
    prevented a later success, and the paper says so.
    """
    total_steps = 0.0
    saved = 0.0
    n_stopped = 0
    stopped_success = 0
    stopped_total = 0
    for row in run_df.itertuples():
        n = int(row.n_steps)
        total_steps += n
        t = decide_step.get(row.run_id)
        if t is not None and t < n:
            n_stopped += 1
            saved += n - t
            stopped_total += 1
            stopped_success += int(row.reward)
    return {
        "total_steps": total_steps,
        "steps_saved": saved,
        "step_saving_frac": saved / total_steps if total_steps else float("nan"),
        "frac_runs_stopped": n_stopped / max(1, len(run_df)),
        "success_among_stopped": stopped_success / stopped_total if stopped_total else float("nan"),
        "success_overall": float(np.mean(run_df["reward"].to_numpy())),
    }
