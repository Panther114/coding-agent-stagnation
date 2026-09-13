"""Monitor models: threshold baselines, logistic model, sustained-alarm wrapper.

Design constraints (from the research design):

* online      - the score at step ``t`` uses only the window ending at ``t``;
* reference-free - no gold patch, no hidden tests, no final reward, no future steps;
* low cost    - pure feature arithmetic at run time.

Every monitor exposes ``score_series(view, w) -> np.ndarray`` giving a per-step
stagnation score in [0, 1], plus an ``alarm`` policy that converts a score series
into a first-alarm step (or ``None``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from features import ALL_FEATURES, CHANNELS, FEATURE_CHANNEL, TrajView, compute_window_features, first_seen_index

EPS = 1e-9


# --------------------------------------------------------------------------------------
# Feature-matrix helpers
# --------------------------------------------------------------------------------------


def window_matrix(view: TrajView, w: int, cfg: Dict[str, Any],
                  stride: int = 1) -> Tuple[np.ndarray, List[int]]:
    """Feature matrix for every step (or every ``stride`` steps) of a trajectory."""
    fseen = first_seen_index(view)
    rows, idxs = [], []
    for t in range(0, view.n_steps, stride):
        feats = compute_window_features(view, t, w, fseen, cfg)
        rows.append([feats.get(k, np.nan) for k in ALL_FEATURES])
        idxs.append(t)
    if not rows:
        return np.zeros((0, len(ALL_FEATURES))), []
    return np.asarray(rows, dtype=np.float64), idxs


def channel_columns(channel: str) -> List[str]:
    return [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == channel]


# --------------------------------------------------------------------------------------
# Hand-designed channel scores
# --------------------------------------------------------------------------------------


def _z(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    mu, sd = float(np.mean(x)), float(np.std(x))
    return (x - mu) / (sd + EPS)


@dataclass
class ChannelScorer:
    """Maps a feature matrix to a scalar 'evidence of progress' score per row.

    Positive = looks productive, negative = looks stagnant.  Each channel is
    standardized with training-set statistics so that channels are commensurate.
    """

    weights: Dict[str, float] = field(default_factory=dict)
    stats: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    def fit(self, X: np.ndarray, cols: Sequence[str]) -> "ChannelScorer":
        names = list(ALL_FEATURES)
        for c in cols:
            j = names.index(c)
            v = np.nan_to_num(X[:, j], nan=0.0, posinf=0.0, neginf=0.0)
            self.stats[c] = (float(np.mean(v)), float(np.std(v) + EPS))
        return self

    def score(self, X: np.ndarray, cols: Sequence[str], weights: Optional[Dict[str, float]] = None) -> np.ndarray:
        names = list(ALL_FEATURES)
        w = weights or self.weights
        out = np.zeros(X.shape[0], dtype=np.float64)
        for c in cols:
            j = names.index(c)
            mu, sd = self.stats.get(c, (0.0, 1.0))
            v = np.nan_to_num(X[:, j], nan=0.0, posinf=0.0, neginf=0.0)
            out += w.get(c, 1.0) * ((v - mu) / sd)
        return out / max(1, len(cols))


# Progress-positive feature groups (higher value => more productive)
PROGRESS_POS = {
    "NOV": ["nov_new_entity_rate", "nov_new_path_rate", "nov_new_symbol_rate", "nov_new_exc_rate",
            "nov_new_testid_rate", "nov_distinct_sig_frac"],
    "EVID": ["ev_new_relevant_rate", "ev_new_highrel_rate", "ev_rel_weighted_novelty",
             "ev_persist_rate", "ev_relevance_max"],
    "VER": ["ver_progress", "ver_has_improvement", "ver_passed_delta", "ver_novel_errorsig_rate",
            "ver_n_improve"],
    "WORK": ["wk_net_new_edited_targets", "wk_new_edit_target_frac"],
}
# Progress-negative (higher value => more stagnant)
PROGRESS_NEG = {
    "REP": ["rep_exact_frac", "rep_target_frac", "rep_cmdfam_frac", "rep_searchterm_frac",
            "rep_cycle", "rep_global_recurrence"],
    "VER": ["ver_stall_len", "ver_same_errorsig_frac", "ver_n_regress"],
    "WORK": ["wk_churn_rate", "wk_reedit_rate", "wk_edit_after_complete"],
    "SEM": [],
}


def channel_progress_score(X: np.ndarray, channel: str, scorer: ChannelScorer) -> np.ndarray:
    pos = PROGRESS_POS.get(channel, [])
    neg = PROGRESS_NEG.get(channel, [])
    out = np.zeros(X.shape[0], dtype=np.float64)
    n = 0
    if pos:
        out += scorer.score(X, pos)
        n += 1
    if neg:
        out -= scorer.score(X, neg)
        n += 1
    return out if n else out


# --------------------------------------------------------------------------------------
# Feature cache
# --------------------------------------------------------------------------------------


class WindowFeatureCache:
    """Dense per-step feature matrix for one trajectory and one window size.

    Computing features is by far the dominant cost, so the cache is built once and
    every monitor scores from it.  ``X[i, :]`` contains the window ending at step ``i``
    (windows shorter than ``w`` at the start of a trajectory are included but can be
    masked through ``min_step``).
    """

    def __init__(self, view: TrajView, w: int, cfg: Dict[str, Any]):
        self.view = view
        self.w = w
        self.cfg = cfg
        fseen = first_seen_index(view)
        rows = []
        for t in range(view.n_steps):
            feats = compute_window_features(view, t, w, fseen, cfg)
            rows.append([feats.get(k, np.nan) for k in ALL_FEATURES])
        self.X = np.asarray(rows, dtype=np.float64) if rows else np.zeros((0, len(ALL_FEATURES)))

    @property
    def n(self) -> int:
        return self.X.shape[0]


def col(name: str) -> int:
    return ALL_FEATURES.index(name)


# --------------------------------------------------------------------------------------
# Monitors
# --------------------------------------------------------------------------------------


class Monitor:
    name = "monitor"

    def score_series(self, cache: WindowFeatureCache) -> np.ndarray:
        """Per-step stagnation score in [0, 1]; ``score[t]`` uses the window ending at t."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.name}>"


class StepBudget(Monitor):
    """B1: alarm purely on step count."""

    name = "B1_step_budget"

    def __init__(self, budget: int = 60):
        self.budget = budget

    def score_series(self, cache: WindowFeatureCache) -> np.ndarray:
        return np.array([1.0 if t >= self.budget else 0.0 for t in range(cache.n)])


class ExactRepeat(Monitor):
    """B2: alarm when the trailing actions contain ``k`` identical normalized actions."""

    name = "B2_exact_repeat"

    def __init__(self, k: int = 3):
        self.k = k

    def score_series(self, cache: WindowFeatureCache) -> np.ndarray:
        view = cache.view
        scores = np.zeros(cache.n, dtype=np.float64)
        seq: List[str] = []
        run = 1
        for s in view.steps:
            for key in s.sig_keys:
                if seq and key == seq[-1]:
                    run += 1
                else:
                    run = 1
                seq.append(key)
                if s.index < cache.n:
                    scores[s.index] = min(1.0, run / float(self.k))
        return scores


class FeatureMonitor(Monitor):
    """Threshold / linear monitor over an explicit feature subset.

    ``direction`` is +1 when a larger feature value means 'more stagnant'.
    """

    def __init__(self, name: str, features: Sequence[str], direction: Sequence[int],
                 stats: Optional[Dict[str, Tuple[float, float]]] = None,
                 weights: Optional[Sequence[float]] = None, scale: float = 1.0):
        self.name = name
        self.features = list(features)
        self.direction = list(direction)
        self.stats = stats or {}
        self.weights = list(weights) if weights is not None else [1.0] * len(features)
        # ``scale`` is fitted from the training split so the bounded map below spans the range
        # the features actually take, instead of saturating.
        self.scale = float(scale)
        self.raw_mu = 0.0

    def fit(self, X: np.ndarray) -> "FeatureMonitor":
        names = list(ALL_FEATURES)
        self.stats = {}
        for f in self.features:
            v = np.nan_to_num(X[:, names.index(f)], nan=0.0, posinf=0.0, neginf=0.0)
            self.stats[f] = (float(np.mean(v)), float(np.std(v) + EPS))
        raw = self._raw(X)
        self.raw_mu = float(np.median(raw))
        self.scale = float(np.std(raw) + 1e-6)
        return self

    def _raw(self, X: np.ndarray) -> np.ndarray:
        out = np.zeros(X.shape[0], dtype=np.float64)
        tot = 0.0
        for f, d, wt in zip(self.features, self.direction, self.weights):
            v = np.nan_to_num(X[:, col(f)], nan=0.0, posinf=0.0, neginf=0.0)
            if f in self.stats:
                mu, sd = self.stats[f]
                v = (v - mu) / sd
            out += d * wt * v
            tot += abs(wt)
        return out / max(tot, EPS)

    def score_series(self, cache: WindowFeatureCache) -> np.ndarray:
        X = cache.X
        if X.shape[0] == 0:
            return np.zeros(0)
        out = self._raw(X)
        # Squash to (0,1) so one threshold scale works across monitors.  We deliberately use a
        # bounded linear map rather than a logistic: features such as ``ver_has_improvement``
        # are zero in almost every training window, so their training-split standard deviation
        # is tiny, a single occurrence produces a z-score in the hundreds, and a logistic
        # saturates to exactly 0 or 1 --- which made the hand-designed monitors either never
        # fire or fire constantly.  Clipping preserves ordering and keeps the scale usable.
        return 0.5 + 0.5 * np.clip((out - self.raw_mu) / max(self.scale, EPS), -1.0, 1.0)


class LogisticMonitor(Monitor):
    """Logistic regression over a channel subset, trained on a task-disjoint split."""

    def __init__(self, name: str, model, features: Sequence[str],
                 mu: np.ndarray, sd: np.ndarray):
        self.name = name
        self.model = model
        self.features = list(features)
        self.mu = np.asarray(mu)
        self.sd = np.asarray(sd)

    def score_series(self, cache: WindowFeatureCache) -> np.ndarray:
        X = cache.X
        if X.shape[0] == 0:
            return np.zeros(0)
        cols = [col(f) for f in self.features]
        Xs = np.nan_to_num(X[:, cols], nan=0.0, posinf=0.0, neginf=0.0)
        Xs = (Xs - self.mu) / self.sd
        return self.model.predict_proba(Xs)[:, 1]


# --------------------------------------------------------------------------------------
# Alarm policy
# --------------------------------------------------------------------------------------


def alarmed_steps(scores: np.ndarray, thr: float, k: int = 2, min_step: int = 0) -> List[int]:
    """Every step at which the sustained rule fires (it may fire repeatedly).

    Returning all firing steps matters for the window-level alarm metrics: an alarm is
    credited to a window when any firing step falls inside it (plus tolerance), so a monitor
    that keeps alarming through a stagnant stretch is rewarded for that persistence.
    """
    out: List[int] = []
    run = 0
    for t, s in enumerate(scores):
        if t < min_step or not (s == s):
            run = 0
            continue
        if s >= thr:
            run += 1
            if run >= k:
                out.append(int(t))
        else:
            run = 0
    return out


def sustained_alarm(scores: np.ndarray, thr: float, k: int = 2, min_step: int = 0) -> Optional[int]:
    """First step at which ``k`` consecutive scores are >= ``thr`` (``None`` if never)."""
    steps = alarmed_steps(scores, thr, k, min_step)
    return steps[0] if steps else None


def first_alarm_over_thresholds(scores: np.ndarray, thresholds: Sequence[float],
                                k: int = 2, min_step: int = 0) -> Dict[float, Optional[int]]:
    return {float(th): sustained_alarm(scores, float(th), k, min_step) for th in thresholds}


def budget_thresholds(train_scores: Sequence[np.ndarray], k: int = 2,
                      budgets: Sequence[float] = (0.01, 0.02, 0.05, 0.10, 0.20),
                      min_step: int = 5) -> Dict[float, float]:
    """Alarm thresholds calibrated on training trajectories to hit target *firing* budgets.

    Choosing a fixed score threshold treats monitors unfairly: a monitor whose scores sit in a
    narrow band never fires at 0.7 while one with a wide band always does.  Calibrating on the
    training split fixes the operating point instead of the scale: for a budget ``b`` we pick
    the threshold at the ``1-b`` quantile of the training *step* scores, so roughly a fraction
    ``b`` of steps fire before the persistence rule is applied.  The evaluation then measures
    what that operating point does on held-out tasks.
    """
    pool = np.concatenate([np.asarray(s, dtype=float).ravel() for s in train_scores if len(s)])
    pool = pool[~np.isnan(pool)]
    if pool.size == 0:
        return {float(b): float("nan") for b in budgets}
    return {float(b): float(np.quantile(pool, 1.0 - b)) for b in budgets}

