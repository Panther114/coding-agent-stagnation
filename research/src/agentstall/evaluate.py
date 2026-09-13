"""Evaluation protocol: task-disjoint folds, task-paired within-instance tests, calibration.

The first version's evaluation had three weaknesses this module fixes:

1. **Pooled AUC dominates because the class balance differs between tasks.**  Its own
   numbers show this: global 0.775, within-run 0.633, with a trivial "step index"
   baseline at 0.644.  Every score here is therefore reported three ways -- pooled,
   task-disjoint (train on other tasks), and *within-run* (does the monitor separate a
   run's own stalled windows from its own productive ones).
2. **Point AUC says nothing about whether a detector can be used.**  The first version's
   calibration attempt failed outright (``B4_semantic`` caught 0 episodes below a 20%
   false-alarm budget), so the metrics that matter operationally are computed explicitly:
   partial AUC at 1% and 5% false-positive rate, and precision at fixed alarms per run.
3. **The claimed ceiling was measured against judged labels only.**  The same features
   are re-scored against the objective targets, so the paper can say whether 0.78 was a
   property of the task or of the label set.

Nothing here fits on the evaluation folds; ``task_disjoint_folds`` is the only source of
splits and it groups by task.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve

# --------------------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------------------


def safe_auc(y: np.ndarray, s: np.ndarray) -> float:
    """ROC-AUC for a binary-or-share target.

    Targets such as ``y_stagnation`` are *shares* (the fraction of a window's steps with
    no change), so a continuous target is binarised at 0.5 before scoring.  Passing a
    continuous vector straight to ``roc_auc_score`` raises, which is how this was found.
    """
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    if len(y) < 2:
        return float("nan")
    yb = (y > 0.5).astype(int) if np.unique(y).size > 2 or not np.all(np.isin(y, (0.0, 1.0))) else y.astype(int)
    if len(np.unique(yb)) < 2:
        return float("nan")
    ok = ~np.isnan(s)
    if ok.sum() < 2 or len(np.unique(s[ok])) < 2:
        return float("nan")
    return float(roc_auc_score(yb[ok], s[ok]))


def safe_ap(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    if len(y) < 2:
        return float("nan")
    yb = (y > 0.5).astype(int) if np.unique(y).size > 2 or not np.all(np.isin(y, (0.0, 1.0))) else y.astype(int)
    if len(np.unique(yb)) < 2:
        return float("nan")
    ok = ~np.isnan(s)
    if ok.sum() < 2:
        return float("nan")
    return float(average_precision_score(yb[ok], s[ok]))


def safe_spearman(y: np.ndarray, s: np.ndarray) -> float:
    """Rank correlation, which uses the full continuous target instead of binarising it."""
    from scipy import stats
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    ok = ~(np.isnan(y) | np.isnan(s))
    if ok.sum() < 10 or len(np.unique(s[ok])) < 2 or len(np.unique(y[ok])) < 2:
        return float("nan")
    return float(stats.spearmanr(y[ok], s[ok]).statistic)


def partial_auc(y: np.ndarray, s: np.ndarray, max_fpr: float) -> float:
    """Partial AUC restricted to FPR <= max_fpr, standardised so 0.5 is chance.

    Delegates to ``sklearn.metrics.roc_auc_score(max_fpr=...)``, which interpolates the ROC
    at the boundary.  A hand-rolled trapezoid over ``roc_curve``'s step function is biased
    when the number of negatives is small: with two negatives it returned 0.487 on a
    perfectly separable case, which the test suite caught.
    """
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    yb = binarise(y)
    if len(yb) < 2 or len(np.unique(yb)) < 2 or not (0.0 < max_fpr < 1.0):
        return float("nan")
    ok = ~np.isnan(s)
    if ok.sum() < 2 or len(np.unique(s[ok])) < 2:
        return float("nan")
    yb, s = yb[ok], s[ok]
    if len(np.unique(yb)) < 2:
        return float("nan")
    try:
        from sklearn.metrics import roc_auc_score as _ras
        return float(_ras(yb, s, max_fpr=max_fpr))
    except Exception:
        return float("nan")


def detection_at_budget(y: np.ndarray, s: np.ndarray, budget: float) -> Dict[str, float]:
    """Detection rate at a false-positive budget, plus the achieved FPR."""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    yb = binarise(y)
    if len(yb) < 2 or len(np.unique(yb)) < 2:
        return {"det": float("nan"), "fpr": float("nan")}
    ok = ~np.isnan(s)
    yb, s = yb[ok], s[ok]
    pos = s[yb == 1]
    neg = s[yb == 0]
    if len(pos) == 0 or len(neg) == 0:
        return {"det": float("nan"), "fpr": float("nan")}
    thr = float(np.quantile(neg, 1.0 - budget))
    return {"det": float((pos > thr).mean()), "fpr": float((neg > thr).mean())}


def within_run_auc(df, score_col: str, y_col: str = "y_stagnation",
                   min_pos: int = 1, min_neg: int = 1) -> Dict[str, float]:
    """Per-run AUC and its pooled/sign-test summary.

    This is the honest measure of a runtime's experience: the summary is an unweighted
    mean over runs, so runs where the monitor is at chance cannot be hidden by runs whose
    label is trivially uniform.
    """
    per_run = []
    for rid, g in df.groupby("run_id", sort=False):
        y = binarise(g[y_col].to_numpy(dtype=float))
        if y.sum() < min_pos or (1 - y).sum() < min_neg:
            continue
        a = safe_auc(y, g[score_col].to_numpy(dtype=float))
        if not np.isnan(a):
            per_run.append({"run_id": rid, "task": g["task"].iloc[0], "auc": a, "n": len(g)})
    if not per_run:
        return {"n_runs": 0, "mean_auc": float("nan"), "median_auc": float("nan"),
                "frac_above_half": float("nan"), "sign_p": float("nan"), "per_run": [],
                "n_above_half": 0}
    aucs = np.array([r["auc"] for r in per_run])
    n_above = int((aucs > 0.5).sum())
    from scipy import stats
    p = float(stats.binomtest(n_above, len(aucs), 0.5, alternative="greater").pvalue)
    return {
        "n_runs": len(per_run),
        "mean_auc": float(aucs.mean()),
        "median_auc": float(np.median(aucs)),
        "frac_above_half": float((aucs > 0.5).mean()),
        "n_above_half": n_above,
        "sign_p": p,
        "per_run": per_run,
    }


def task_paired_test(df, score_col: str, y_col: str = "y_stagnation",
                     min_per_class: int = 1) -> Dict[str, float]:
    """Compare monitor score between positive and negative windows *within the same task*.

    The confound this controls: stagnation prevalence differs enormously across tasks, so
    a monitor can look sharp globally by ranking tasks rather than moments.  Stratifying
    the comparison by task removes that, and the reported p-value treats each task as one
    observation.
    """
    deltas = []
    for task, g in df.groupby("task"):
        y = binarise(g[y_col].to_numpy(dtype=float))
        if y.sum() < min_per_class or (1 - y).sum() < min_per_class:
            continue
        s = g[score_col].to_numpy(dtype=float)
        deltas.append(float(np.nanmean(s[y == 1]) - np.nanmean(s[y == 0])))
    if not deltas:
        return {"n_tasks": 0, "mean_delta": float("nan"), "p": float("nan")}
    d = np.asarray(deltas)
    from scipy import stats
    try:
        p = float(stats.wilcoxon(d).pvalue)
    except Exception:
        p = float("nan")
    return {
        "n_tasks": int(len(d)),
        "mean_delta": float(d.mean()),
        "median_delta": float(np.median(d)),
        "frac_positive": float((d > 0).mean()),
        "p": p,
    }


def paired_bootstrap_auc(y: np.ndarray, s_a: np.ndarray, s_b: np.ndarray,
                         groups: Optional[np.ndarray] = None, n_boot: int = 2000,
                         seed: int = 0) -> Dict[str, float]:
    """Bootstrap the AUC difference, resampling the grouping unit (task or run)."""
    rng = np.random.default_rng(seed)
    y = binarise(np.asarray(y, dtype=float))
    s_a = np.asarray(s_a, dtype=float)
    s_b = np.asarray(s_b, dtype=float)
    if groups is None:
        groups = np.zeros(len(y), dtype=int)
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    idx_by_group = {g: np.where(groups == g)[0] for g in uniq}
    point = safe_auc(y, s_a) - safe_auc(y, s_b)
    diffs = []
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_group[g] for g in pick])
        diffs.append(safe_auc(y[idx], s_a[idx]) - safe_auc(y[idx], s_b[idx]))
    d = np.asarray([x for x in diffs if not np.isnan(x)])
    if len(d) < 10:
        return {"delta": float(point), "lo": float("nan"), "hi": float("nan"), "p": float("nan")}
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = float(2 * min((d <= 0).mean(), (d >= 0).mean()))
    return {"delta": float(point), "lo": float(lo), "hi": float(hi), "p": p,
            "n_boot": int(len(d))}


# --------------------------------------------------------------------------------------
# splits and fitting
# --------------------------------------------------------------------------------------


def task_disjoint_folds(df, n_folds: int = 5, seed: int = 0) -> List[Tuple[np.ndarray, np.ndarray]]:
    """(train_idx, test_idx) folds with whole tasks held out -- no task memorisation."""
    rng = np.random.default_rng(seed)
    tasks = np.array(sorted(df["task"].unique()))
    rng.shuffle(tasks)
    chunks = np.array_split(tasks, n_folds)
    out = []
    tcol = df["task"].to_numpy()
    for k in range(n_folds):
        held = set(chunks[k].tolist())
        test = np.where(np.isin(tcol, list(held)))[0]
        train = np.where(~np.isin(tcol, list(held)))[0]
        if len(train) and len(test):
            out.append((train, test))
    return out


def _clean(X: np.ndarray) -> np.ndarray:
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return X


def _within_task_z(df, X: np.ndarray) -> np.ndarray:
    """Standardise every feature *within its own task* before pooling.

    This is the control the first version never applied.  Per-task stagnation rates run
    from 0.00 to 0.77, so a globally standardised feature partly encodes task identity;
    standardising inside the task forces the monitor to compare moments of the same task.
    Cross-validation then only sees task-disjoint folds, so the normalisation cannot leak
    the held-out task's label.
    """
    out = np.array(X, dtype=float, copy=True)
    tcol = df["task"].to_numpy()
    for task in np.unique(tcol):
        m = tcol == task
        mu = out[m].mean(axis=0)
        sd = out[m].std(axis=0)
        sd[sd < 1e-9] = 1.0
        out[m] = (out[m] - mu) / sd
    return _clean(out)


def binarise(y: np.ndarray) -> np.ndarray:
    """Targets here are shares in [0, 1]; classifiers need a decision boundary.

    0.5 is used throughout and never tuned, so the label is fixed before any score is
    computed.
    """
    y = np.asarray(y, dtype=float)
    if np.unique(y).size <= 2 and np.all(np.isin(y, (0.0, 1.0))):
        return y.astype(int)
    return (y > 0.5).astype(int)


def group_contrast(df, score_col: str, y_col: str, group_col: str) -> Dict[str, float]:
    """Share of a monitor's total discrimination that is *between* groups.

    Two quantities are reported for the same monitor:

    ``between_auc``   rank the groups (tasks or runs) by their mean score and by their
                      mean label.  This part of the signal is free: it comes from knowing
                      which task or run one is in, and needs no online computation.
    ``within_spearman``  rank correlation after removing each group's own mean from both
                      the score and the label -- the part that requires looking at the
                      trajectory.

    A monitor whose between-group signal is strong and whose within-group signal is near
    zero cannot be used by a runtime working on a single task.  The first version of this
    study reported the pooled figure without this split, and its own numbers show why that
    mattered: global AUC 0.775 against a step-index baseline of 0.644.
    """
    g = df.groupby(group_col)
    means = g[[score_col, y_col]].mean()
    between = safe_auc(means[y_col].to_numpy(dtype=float), means[score_col].to_numpy(dtype=float))
    s = df[score_col] - g[score_col].transform("mean")
    within = safe_spearman(df[y_col].to_numpy(dtype=float), s.to_numpy(dtype=float))
    deltas = []
    for _, gg in g:
        y = binarise(gg[y_col].to_numpy(dtype=float))
        if y.sum() < 1 or (1 - y).sum() < 1:
            continue
        sc = gg[score_col].to_numpy(dtype=float)
        deltas.append(float(np.nanmean(sc[y == 1]) - np.nanmean(sc[y == 0])))
    return {"between_auc": between, "within_spearman": within,
            "n_groups": int(len(means)),
            "frac_groups_correct_sign": float(np.mean(np.asarray(deltas) > 0)) if deltas else float("nan"),
            "mean_group_delta": float(np.mean(deltas)) if deltas else float("nan")}


def burst_metrics(df, score_col: str, y_col: str, run_col: str = "run_id",
                  alert_frac: float = 0.10) -> Dict[str, float]:
    """Does the monitor concentrate its alerts on the windows that are actually bad?

    For each run, alert on the top ``alert_frac`` of *its own* windows by score, and
    measure what share of that run's total stagnation the alerts contain.  Perfect
    targeting gives 1.0; no skill gives ``alert_frac``.  This is the quantity a runtime
    can actually consume, because it can only alert on a fraction of the current run.
    """
    lifts = []
    for _, g in df.groupby(run_col, sort=False):
        if len(g) < 10:
            continue
        k = int(round(len(g) * alert_frac))
        if k < 1:
            continue
        y = g[y_col].to_numpy(dtype=float)
        s = g[score_col].to_numpy(dtype=float)
        order = np.argsort(-np.nan_to_num(s, nan=-np.inf))
        tot = float(np.nansum(y))
        if tot <= 1e-9:
            continue
        lifts.append(float(np.nansum(y[order[:k]]) / tot))
    if not lifts:
        return {"n_runs": 0, "mean_share_captured": float("nan"), "lift": float("nan")}
    return {"n_runs": len(lifts), "mean_share_captured": float(np.mean(lifts)),
            "median_share_captured": float(np.median(lifts)),
            "lift": float(np.mean(lifts) / alert_frac), "alert_frac": alert_frac}


def fit_logistic_cv(df, cols: Sequence[str], y_col: str = "y_stagnation",
                    n_folds: int = 5, seed: int = 0, C: float = 1.0,
                    within_task: bool = False) -> Dict[str, object]:
    """Out-of-fold logistic scores over task-disjoint folds.

    ``within_task=True`` standardises the features inside each task before pooling, which
    removes the task-identity component of the feature scale.  Both variants are reported,
    because the difference between them is exactly how much of a monitor's apparent skill
    came from knowing which task it was looking at.
    """
    Xr = df[list(cols)].to_numpy(dtype=float)
    X = _within_task_z(df, Xr) if within_task else _clean(Xr)
    y_raw = df[y_col].to_numpy(dtype=float)
    y = binarise(y_raw)
    oof = np.full(len(df), np.nan)
    aucs = []
    for tr, te in task_disjoint_folds(df, n_folds=n_folds, seed=seed):
        if y[tr].sum() == 0 or y[tr].sum() == len(tr):
            continue
        mu = X[tr].mean(axis=0)
        sd = X[tr].std(axis=0)
        sd[sd < 1e-9] = 1.0
        model = LogisticRegression(max_iter=2000, C=C, solver="lbfgs")
        model.fit((X[tr] - mu) / sd, y[tr])
        oof[te] = model.predict_proba((X[te] - mu) / sd)[:, 1]
        a = safe_auc(y[te], oof[te])
        if not np.isnan(a):
            aucs.append(a)
    return {"oof": oof, "fold_aucs": aucs, "auc_mean": float(np.mean(aucs)) if aucs else float("nan"),
            "coef": None}


def direct_score(df, cols: Sequence[str], signs: Optional[Sequence[int]] = None,
                 standardise: bool = True) -> np.ndarray:
    """A signed, standardised sum of standardised features (the 'hand-designed' monitor).

    Kept because the first version's headline monitor was of exactly this form, so any
    comparison against it must use the same construction.
    """
    X = _clean(df[list(cols)].to_numpy(dtype=float))
    if standardise:
        mu = X.mean(axis=0)
        sd = X.std(axis=0)
        sd[sd < 1e-9] = 1.0
        X = (X - mu) / sd
    if signs is None:
        signs = np.ones(X.shape[1])
    s = X @ np.asarray(signs, dtype=float)
    return np.asarray(s, dtype=float)
