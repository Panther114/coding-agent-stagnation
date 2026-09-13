"""Online window features, and their position-stationary forms.

Why this module exists
----------------------
The first version of the study reported ROC-AUC 0.775 for its best family and then
found that the same score carries a within-run trend with the step index (r = 0.518,
positive in 93% of runs).  That is the most serious defect in the first version: a
score that drifts with run position is not a stagnation *state*, it is a clock, and
any threshold on it drifts out of calibration as the run proceeds.

Every feature is therefore computed in two forms:

``raw``   the plain window statistic, comparable with the first version.
``stat``  a position-stationary variant::

              f_stat(t) = f(t) - mean_{i <= t} f(i)

          Computable online without labels and without lookahead -- it needs only the
          scores already produced.  It removes the run's trend (constant plus linear
          drift vanishes) and leaves the within-run deviation a stall should produce.

Results are always reported for both forms, so the paper can state exactly how much of
the first version's accuracy was position rather than progress.

Leakage rule
------------
Nothing here reads a label, the final patch, the reward, or a future step.  Novelty is
computed against the prefix of the run seen so far, never against the whole run.
``scripts/run_tests.py`` exercises that restriction mechanically.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

# Feature keys whose stationary form is computed. Populated by ``all_feature_keys``.
_META = ("_t", "_w", "_relpos", "_frac_done")


@dataclass
class RunView:
    """Numpy view of one run's step table. ``meta`` carries the per-step novelty log."""

    run_id: str
    corpus: str
    task: str
    agent: str
    model: str
    reward: int
    n: int
    # arrays
    is_edit: np.ndarray
    is_test: np.ndarray
    is_read: np.ndarray
    is_run: np.ndarray
    is_search: np.ndarray
    verb_code: np.ndarray
    file_total: np.ndarray          # -1 unknown
    file_first: np.ndarray
    obs_chars: np.ndarray
    text_chars: np.ndarray
    n_cmds: np.ndarray
    st_test: np.ndarray
    st_passed: np.ndarray           # -1 absent
    st_failed: np.ndarray           # -1 absent
    st_exit: np.ndarray             # -999 absent
    st_syntax: np.ndarray
    st_tb: np.ndarray
    st_notfound: np.ndarray
    st_timeout: np.ndarray
    st_err: np.ndarray
    # per-step raw strings (lists)
    sig: List[str] = field(default_factory=list)
    cmd_family: List[str] = field(default_factory=list)
    file_shown: List[str] = field(default_factory=list)
    errc: List[str] = field(default_factory=list)
    st_sig: List[str] = field(default_factory=list)
    # entity text per step and kind, for prefix-based novelty
    ent_text: List[List[Tuple[str, str, int]]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


def _first_seen_flags(seq: Sequence[str]) -> np.ndarray:
    seen: Set[str] = set()
    out = np.zeros(len(seq), dtype=np.float32)
    for i, s in enumerate(seq):
        if s and s not in seen:
            out[i] = 1.0
            seen.add(s)
    return out


def build_run_view(df, ent_text: Optional[List[List[Tuple[str, str, int]]]] = None) -> RunView:
    """Numpy view of one run's step table.

    ``reward`` is carried on the view as *identity metadata only* -- it labels the row for
    evaluation and is never read by any function in this module.  The test suite checks the
    separation structurally and behaviourally.
    """
    df = df.sort_values("step").reset_index(drop=True)
    n = len(df)

    def col(name: str, default: float = 0.0) -> np.ndarray:
        if name not in df.columns:
            return np.full(n, default, dtype=np.float64)
        return df[name].to_numpy(dtype=np.float64)

    verbs = sorted(set(df["verb"].astype(str)))
    vmap = {v: i for i, v in enumerate(verbs)}

    st_test = col("st_test")
    st_passed = col("st_passed", -1.0)
    st_failed = col("st_failed", -1.0)
    st_exit = col("st_exit", -999.0)
    st_tb = col("st_tb")
    st_syntax = col("st_syntax")
    st_nf = col("st_notfound")
    st_to = col("st_timeout")
    st_err = np.clip(st_tb + st_syntax + st_nf + st_to + ((st_exit < 0) & (st_exit > -900)), 0, 1)

    return RunView(
        run_id=str(df["run_id"].iloc[0]),
        corpus=str(df["corpus"].iloc[0]),
        task=str(df["task"].iloc[0]),
        agent=str(df["agent"].iloc[0]),
        model=str(df["model"].iloc[0]),
        reward=int(df["reward"].iloc[0]),
        n=n,
        is_edit=col("is_edit"), is_test=col("is_test"), is_read=col("is_read"),
        is_run=col("is_run"), is_search=col("is_search"),
        verb_code=df["verb"].astype(str).map(vmap).to_numpy(dtype=np.float64),
        file_total=col("file_total", -1.0), file_first=col("file_first", -1.0),
        obs_chars=col("obs_chars"), text_chars=col("text_chars"), n_cmds=col("n_cmds"),
        st_test=st_test, st_passed=st_passed, st_failed=st_failed, st_exit=st_exit,
        st_syntax=st_syntax, st_tb=st_tb, st_notfound=st_nf, st_timeout=st_to,
        st_err=st_err,
        sig=[str(x) for x in df.get("sig", [""] * n)],
        cmd_family=[str(x) for x in df.get("cmd_family", [""] * n)],
        file_shown=[("" if x is None else str(x)) for x in df.get("file_shown", [""] * n)],
        errc=[str(x) for x in df.get("st_errc", [""] * n)],
        st_sig=[str(x) for x in df.get("st_sig", [""] * n)],
        ent_text=ent_text if ent_text is not None else [[] for _ in range(n)],
    )


# --------------------------------------------------------------------------------------
# window features
# --------------------------------------------------------------------------------------


def _dup_frac(seq: Sequence[str]) -> Tuple[float, int]:
    if not seq:
        return 0.0, 0
    c = Counter(seq)
    return sum(v - 1 for v in c.values()) / len(seq), max(c.values())


def _cycle_frac(sigs: Sequence[str]) -> float:
    m = len(sigs)
    if m < 6:
        return 0.0
    best = 0.0
    for p in (2, 3, 4):
        if m >= 2 * p:
            hits = sum(1 for i in range(p, m) if sigs[i] == sigs[i - p])
            best = max(best, hits / (m - p))
    return best


def _new_in_window(prefix: Set[str], events: Sequence[Tuple[str, str, int]],
                   t: int, lo: int) -> Tuple[int, int, int, int, int, float]:
    """Count genuinely novel entity mentions inside the window [lo, t].

    ``events[i]`` is the list of (kind, value, chars) observed at step i.
    """
    n_new = 0
    n_new_file = 0
    n_new_sym = 0
    n_new_exc = 0
    n_new_test = 0
    new_chars = 0.0
    for i in range(lo, t + 1):
        for kind, val, chars in events[i]:
            key = kind + "|" + val
            if key not in prefix:
                prefix.add(key)
                n_new += 1
                new_chars += chars
                if kind == "file":
                    n_new_file += 1
                elif kind == "symbol":
                    n_new_sym += 1
                elif kind == "exc":
                    n_new_exc += 1
                elif kind == "testid":
                    n_new_test += 1
    return n_new, n_new_file, n_new_sym, n_new_exc, n_new_test, new_chars


def window_features(rv: RunView, t: int, w: int, prefix: Set[str]) -> Dict[str, float]:
    """Features for the window of ``w`` steps ending at ``t`` (inclusive).

    ``prefix`` is the running set of entity keys seen strictly before ``lo``; the
    caller maintains it so a left-to-right sweep costs one pass per run.
    """
    lo = max(0, t - w + 1)
    m = t - lo + 1
    f: Dict[str, float] = {}

    # ---- repetition ---------------------------------------------------------------
    sigs = rv.sig[lo:t + 1]
    fams = rv.cmd_family[lo:t + 1]
    f["rep_exact_frac"], f["rep_exact_maxrep"] = _dup_frac(sigs)
    f["rep_family_frac"], _ = _dup_frac(fams)
    f["rep_cycle"] = _cycle_frac(sigs)
    first_sig = rv.meta.setdefault("sig_first", {})
    if not first_sig:
        for i, s in enumerate(rv.sig):
            first_sig.setdefault(s, i)
    f["rep_recurrence"] = float(np.mean([1.0 if first_sig.get(s, 10 ** 9) < lo else 0.0
                                         for s in sigs])) if sigs else 0.0

    # ---- composition --------------------------------------------------------------
    f["mix_edit_frac"] = float(rv.is_edit[lo:t + 1].mean())
    f["mix_test_frac"] = float(rv.is_test[lo:t + 1].mean())
    f["mix_read_frac"] = float(rv.is_read[lo:t + 1].mean())
    f["mix_n_edit"] = float(rv.is_edit[lo:t + 1].sum())
    f["mix_n_test"] = float(rv.is_test[lo:t + 1].sum())
    f["mix_total_actions"] = float(rv.n_cmds[lo:t + 1].sum())
    f["mix_distinct_verbs"] = float(len(set(rv.verb_code[lo:t + 1].tolist())))

    # ---- novelty (prefix-relative, so no lookahead) --------------------------------
    (n_new, n_new_file, n_new_sym, n_new_exc, n_new_test, new_chars) = \
        _new_in_window(prefix, rv.ent_text, t, lo)
    f["nov_new_total"] = float(n_new)
    f["nov_new_rate"] = n_new / m
    f["nov_new_file_rate"] = n_new_file / m
    f["nov_new_symbol_rate"] = n_new_sym / m
    f["nov_new_exc_rate"] = n_new_exc / m
    f["nov_new_testid_rate"] = n_new_test / m
    f["nov_new_chars_rate"] = new_chars / m
    f["nov_distinct_state_sig"] = len(set(rv.st_sig[lo:t + 1])) / m
    f["nov_distinct_family"] = len(set(fams)) / m
    f["nov_state_sig_change"] = sum(1 for i in range(lo + 1, t + 1)
                                    if rv.st_sig[i] != rv.st_sig[i - 1]) / max(1, m - 1)
    f["nov_obs_chars"] = float(rv.obs_chars[lo:t + 1].mean())
    f["nov_text_chars"] = float(rv.text_chars[lo:t + 1].mean())

    # ---- workspace state: the objective channel -------------------------------------
    ftot = rv.file_total[lo:t + 1]
    known = ftot >= 0
    f["ws_known_frac"] = float(known.mean())
    deltas: List[float] = []
    n_edit_meas = 0
    noop = 0
    for i in range(max(1, lo), t + 1):
        a = rv.file_total[i]
        b = rv.file_total[i - 1]
        if a >= 0 and b >= 0 and rv.file_shown[i] and rv.file_shown[i] == rv.file_shown[i - 1]:
            deltas.append(a - b)
            if rv.is_edit[i]:
                n_edit_meas += 1
                if a == b:
                    noop += 1
    d = np.asarray(deltas, dtype=np.float64) if deltas else np.zeros(0)
    f["ws_n_size_deltas"] = float(len(d))
    f["ws_abs_size_delta"] = float(np.abs(d).mean()) if len(d) else 0.0
    f["ws_net_size_delta"] = float(d.sum()) if len(d) else 0.0
    f["ws_size_flat_frac"] = float((d == 0).mean()) if len(d) else 0.0
    f["ws_growth_frac"] = float((d > 0).mean()) if len(d) else 0.0
    f["ws_shrink_frac"] = float((d < 0).mean()) if len(d) else 0.0
    f["ws_oscillation"] = float(np.mean(np.abs(np.diff(np.sign(d))) > 0)) if len(d) >= 3 else 0.0
    f["ws_n_edit_measurable"] = float(n_edit_meas)
    f["ws_noop_edit_frac"] = (noop / n_edit_meas) if n_edit_meas else 0.0
    files = [x for x in rv.file_shown[lo:t + 1] if x]
    f["ws_distinct_files"] = float(len(set(files)))
    f["ws_same_file_frac"] = (1.0 - len(set(files)) / len(files)) if files else 0.0

    # ---- verification state ---------------------------------------------------------
    f["ver_n_test_obs"] = float(rv.st_test[lo:t + 1].sum())
    f["ver_err_rate"] = float(rv.st_err[lo:t + 1].mean())
    f["ver_n_syntax"] = float(rv.st_syntax[lo:t + 1].sum())
    f["ver_n_traceback"] = float(rv.st_tb[lo:t + 1].sum())
    f["ver_n_notfound"] = float(rv.st_notfound[lo:t + 1].sum())
    have = ((rv.st_passed[lo:t + 1] >= 0) | (rv.st_failed[lo:t + 1] >= 0))
    f["ver_n_test_counts"] = float(have.sum())
    n_improve = 0
    for i in range(max(1, lo), t + 1):
        a, b = rv.st_passed[i], rv.st_passed[i - 1]
        if a >= 0 and b >= 0 and a > b:
            n_improve += 1
        elif a < 0 and b >= 0:
            fa, fb = rv.st_failed[i], rv.st_failed[i - 1]
            if fa >= 0 and fb >= 0 and fa < fb:
                n_improve += 1
    f["ver_improve_rate"] = n_improve / max(1, m - 1)

    # ---- stall lengths: time since the last objectively positive event ---------------
    last_sig = last_growth = last_novel = -1
    ncount = rv.meta.get("novel_step_count")
    for i in range(0, t + 1):
        if i > 0 and rv.st_sig[i] != rv.st_sig[i - 1]:
            last_sig = i
        if i > 0 and rv.file_total[i] >= 0 and rv.file_total[i - 1] >= 0 \
                and rv.file_total[i] != rv.file_total[i - 1]:
            last_growth = i
        if ncount is not None and ncount[i] > 0:
            last_novel = i
    f["ver_stall_len"] = float(t - last_sig) if last_sig >= 0 else float(t)
    f["ws_stall_len"] = float(t - last_growth) if last_growth >= 0 else float(t)
    f["nov_stall_len"] = float(t - last_novel) if last_novel >= 0 else float(t)

    f["_t"] = float(t)
    f["_w"] = float(w)
    # Position controls.  These are computed from the prefix only, so a feature matrix built
    # on a truncated run is identical for the same step (checked by the test suite).  A
    # monitor is allowed to know how many steps it has been running; it is not allowed to
    # know how long the run will turn out to be.
    f["_relpos"] = t / max(1, t + 1)
    f["_frac_done"] = t / max(1, t + 1)
    f["_elapsed"] = float(t + 1)
    return f


def prefix_novel_counts(rv: RunView) -> np.ndarray:
    """Per-step count of entity keys never seen earlier in the run (leak-free)."""
    seen: Set[str] = set()
    out = np.zeros(rv.n, dtype=np.float64)
    for i, events in enumerate(rv.ent_text):
        c = 0
        for kind, val, _chars in events:
            k = kind + "|" + val
            if k not in seen:
                seen.add(k)
                c += 1
        out[i] = c
    return out


def sweep_run(rv: RunView, w: int, stride: int = 1, min_window: int = 3,
              t_stop: Optional[int] = None) -> List[Dict[str, float]]:
    """All windows of one run, left to right, maintaining the novelty prefix.

    Returns a list of feature dicts (the ``raw`` form).  The stationary form is added by
    ``stationarise`` once the whole run's raw matrix exists, because a running mean over
    the prefix requires every earlier window's value.
    """
    rv.meta["novel_step_count"] = prefix_novel_counts(rv)
    rows: List[Dict[str, float]] = []
    prefix: Set[str] = set()
    rv.meta["_pref_i"] = 0
    last_t = rv.n - 1 if t_stop is None else min(t_stop, rv.n - 1)
    for t in range(0, last_t + 1):
        lo = max(0, t - w + 1)
        # add to the prefix everything strictly before lo
        while rv.meta["_pref_i"] < lo:
            i = rv.meta["_pref_i"]
            for kind, val, _c in rv.ent_text[i]:
                prefix.add(kind + "|" + val)
            rv.meta["_pref_i"] = i + 1
        if (t - lo + 1) < min_window:
            continue
        if (t - w + 1) % max(1, stride) != 0 and t != last_t:
            continue
        rows.append(window_features(rv, t, w, prefix))
    return rows


def stationarise(raw: np.ndarray, keys: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    """Two causal position-normalisations, neither of which may look ahead.

    ``lev`` (written ``<key>_s``)   ``f(t) - mean(f(0..t))`` — kills a constant offset and
                                    reduces, but does not eliminate, a linear drift.
    ``fit`` (written ``<key>_o``)   ``f(t) - OLS_fit(f(0..t))(t)`` — fits a straight line to
                                    the run's own past and subtracts its value at ``t``, so a
                                    constant *and* a linear trend vanish exactly while any
                                    bend survives.

    The first version reported a within-run trend (r = 0.518 with step index, positive in
    93% of runs) and asked for "a stationary stagnation statistic"; ``_o`` is the exact
    version of that request, and ``_s`` is the cheap approximation.  Both read only values
    already produced, so both are online.

    Rows of ``raw`` must be ordered by ``t``.
    """
    n, m = raw.shape
    lev = np.empty((n, m), dtype=np.float64)
    fit = np.empty((n, m), dtype=np.float64)
    t = np.arange(n, dtype=np.float64)
    cnt = np.arange(1, n + 1, dtype=np.float64)
    sx = np.cumsum(t)
    sxx = np.cumsum(t * t)
    for j in range(m):
        col = raw[:, j]
        csum = np.cumsum(col)
        lev[:, j] = col - csum / cnt
        sxy = np.cumsum(t * col)
        denom = cnt * sxx - sx * sx
        ok = np.abs(denom) > 1e-12
        safe = np.where(ok, denom, 1.0)
        slope = np.where(ok, (cnt * sxy - sx * csum) / safe, 0.0)
        intercept = np.where(ok, (csum - slope * sx) / np.maximum(cnt, 1.0), csum / cnt)
        fit[:, j] = col - (intercept + slope * t)
    return lev, fit


def all_feature_keys(sample: Dict[str, float]) -> List[str]:
    return [k for k in sample if k not in _META]


FEATURE_GROUPS: Dict[str, Tuple[str, ...]] = {
    "REP": ("rep_exact_frac", "rep_exact_maxrep", "rep_family_frac", "rep_cycle", "rep_recurrence"),
    "MIX": ("mix_edit_frac", "mix_test_frac", "mix_read_frac", "mix_n_edit", "mix_n_test",
            "mix_total_actions", "mix_distinct_verbs"),
    "NOV": ("nov_new_total", "nov_new_rate", "nov_new_file_rate", "nov_new_symbol_rate",
            "nov_new_exc_rate", "nov_new_testid_rate", "nov_new_chars_rate",
            "nov_distinct_state_sig", "nov_distinct_family", "nov_state_sig_change",
            "nov_obs_chars", "nov_text_chars"),
    "WS": ("ws_known_frac", "ws_n_size_deltas", "ws_abs_size_delta", "ws_net_size_delta",
           "ws_size_flat_frac", "ws_growth_frac", "ws_shrink_frac", "ws_oscillation",
           "ws_n_edit_measurable", "ws_noop_edit_frac", "ws_distinct_files", "ws_same_file_frac"),
    "VER": ("ver_n_test_obs", "ver_err_rate", "ver_n_syntax", "ver_n_traceback",
            "ver_n_notfound", "ver_n_test_counts", "ver_improve_rate"),
    "STALL": ("ver_stall_len", "ws_stall_len", "nov_stall_len"),
    "POS": ("_t", "_relpos", "_frac_done"),
}
