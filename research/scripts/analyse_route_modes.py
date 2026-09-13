"""SEARCH or VERIFY?  A causal, no-lookahead detector of *which way* a run is failing.

    python scripts/analyse_route_modes.py --stage all          # everything, resumable
    python scripts/analyse_route_modes.py --selftest           # causal-integrity test only
    python scripts/analyse_route_modes.py --limit 1500         # smoke run

The decision this study is about
--------------------------------
A coding agent fails in one of two ways:

``WRONG-FIX``  it edited a file the gold patch touches, but its change did not resolve the
               issue -- the *place* was right, the *content* was not;
``LOST``       it never edited a gold file at all -- it never found the place.

On this corpus 67.1% of failures are wrong-fix and 32.9% are lost.  A runtime facing a
struggling agent has one unit of help to spend: **SEARCH** (help it find the right place)
or **VERIFY** (make it check its own fix).  That choice is only useful if the mode is
predictable *from what has happened so far*.

What is built here
------------------
1. **Labels.**  For every run whose instance has a gold patch (an independent target: the
   dataset's own patch field, never the agent's own output), ``ever_touched_gold`` (did the
   run ever edit a file whose basename is in the gold set) and ``on_target_gold`` (share of
   edit steps aimed at a gold file).  Targets: ``y_fail = 1 - reward`` over all such runs,
   ``y_wrong_fix = ever_touched_gold`` over **failed** runs only.
2. **Prefix-only features.**  For each run and fraction f in {0.10,0.20,0.40,0.60} the
   feature vector uses steps ``0 .. L-1`` with ``L = max(1, round(f * n_steps))``.
   ``n_steps`` defines the cutoff (the protocol is "the first fraction f of the run") and
   appears in **no** feature.  ``--selftest`` proves this mechanically: it corrupts every
   step at or after the cutoff and asserts the features are unchanged.  The consequence is
   stated rather than hidden: ``position`` (= prefix length = f * n_steps) *is* a full-run
   quantity in disguise, so it is reported both as the study's strong baseline and as a
   leak diagnostic; the ``own_rates`` family excludes every length-carrying feature.
3. **Baselines on identical rows and folds.**  ``position``, ``agentstop_shape`` (per-step
   output length + adjacent-step overlap), ``edit_rate_free`` (one free feature) and the
   loop/redundancy detectors of the frozen study -- ``ngram_loop``, ``exact_burst``,
   ``tfnorm_novel`` -- reimplemented from ``scripts/analyse_detector_families.py`` (which is
   *not* modified; the reference implementations need a per-run table, so they are mirrored).
4. **Calibration with formal false-alarm control.**  A sequential rule over the four
   checkpoints with the Type-I budget split across them (union bound: valid under arbitrary
   dependence between checkpoints) *and* an e-value combination across checkpoints
   (``mean_f kappa * p_f^(kappa-1)``, itself an e-value under arbitrary dependence).  Nulls
   are measured on **held-out tasks**: for ``y_fail`` the null runs are the successful ones,
   for ``y_mode`` the null runs are the LOST ones.  ``null_checks`` reports the achieved
   alarm rate on never-failing runs instead of asserting zero.
5. **Decision curve.**  ``SEARCH``/``VERIFY`` routing against always-SEARCH, always-VERIFY
   and random routing under an explicit utility, conditional on failure and gated on the
   failure detector over all runs.

Writes ``results/rebuild/route_modes.json``.  Scratch caches live in
``_cache/route_modes/`` so an interrupted run resumes instead of restarting.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402

OUT = ROOT / "results" / "rebuild"
CACHE = ROOT / "_cache" / "route_modes"
FRACTIONS = (0.10, 0.20, 0.40, 0.60)
BUDGETS = (0.05, 0.10)

#: length-independent features: none of these grows merely because the prefix is longer,
#: so a model on them cannot smuggle the run's length back in.
RATE_FEATURES = [
    "no_edit_yet", "first_edit_frac", "edit_rate", "noop_edit_frac", "distinct_files_per_edit",
    "repeat_file_edit_frac", "any_file_edited_twice", "testish_per_step", "verify_frac",
    "run_frac", "read_frac", "search_frac", "finish_seen", "unique_sig_frac",
    "unique_cmdfam_frac", "sig_entropy", "cmdfam_entropy", "repeat_sig_frac",
    "max_consec_repeat_norm", "has_repeat_3plus", "obs_mean", "obs_last_over_mean",
    "obs_slope_norm", "obs_half_ratio", "text_chars_mean", "text_to_obs", "err_rate",
    "pass_seen_per_step", "fail_seen_per_step", "err_seen_per_step", "fail_minus_pass_norm",
    "any_test_fail_seen", "any_test_pass_seen", "obs_mean_over_text",
]

#: the full requested family list: adds raw counts, which grow with the prefix length (and
#: therefore with ``n_steps``).  Reported, and flagged as length-carrying.
COUNT_FEATURES = RATE_FEATURES + [
    "n_edit_prefix", "n_distinct_files", "n_testish", "n_verify", "n_run", "n_read",
    "n_search", "n_noop_edit", "st_pass_sum", "st_fail_sum", "st_err_sum",
    "first_edit_index", "obs_sum", "max_consec_repeat_abs", "n_repeat_file_edits",
]

BASELINE_METHODS = ["position", "agentstop_shape", "ngram_loop", "exact_burst",
                    "tfnorm_novel", "edit_rate_free"]
OWN_METHODS = ["own_rates", "own_all", "own_gbm_rates", "own_gbm_all"]
PRIMARY = "own_rates"

STEP_COLS = [
    "run_id", "task", "model", "reward", "step", "n_steps", "verb", "cmd_family",
    "is_edit", "is_read", "is_search", "is_run", "is_test", "is_finish", "obs_chars",
    "text_chars", "sig", "targets_str", "file_shown", "added_lines_n", "st_passed",
    "st_failed", "st_error", "st_tb", "st_syntax", "st_notfound", "st_sig",
]


# --------------------------------------------------------------------------------------
# labels
# --------------------------------------------------------------------------------------


def basenames(series: pd.Series) -> np.ndarray:
    """Basename of every path in a string column, '' when the path is missing."""
    s = series.fillna("").astype(str).str.replace("\\", "/", regex=False)
    return s.str.rsplit("/", n=1).str[-1].to_numpy()


def build_labels(steps: pd.DataFrame, gold: Dict[str, set]) -> pd.DataFrame:
    """Run-level labels.  ``ever_touched_gold``/``on_target_gold`` read the whole run: they
    are the *outcome definition*, never a feature."""
    sub = steps[steps["task"].isin(gold)].copy()
    base = basenames(sub["file_shown"])
    tcol = sub["task"].to_numpy()
    is_gold = np.array([1 if (b and b in gold[t]) else 0 for b, t in zip(base, tcol)],
                       dtype=np.int8)
    sub["_is_gold_edit"] = is_gold * sub["is_edit"].to_numpy(dtype=np.int8)
    sub["_edit_known"] = ((sub["is_edit"] == 1) & (base != "")).astype(np.int8)
    g = sub.groupby(["run_id", "task", "model"], sort=False).agg(
        reward=("reward", "first"),
        n_steps=("n_steps", "first"),
        n_edit_all=("is_edit", "sum"),
        n_edit_known=("_edit_known", "sum"),
        n_gold_edits=("_is_gold_edit", "sum"),
    ).reset_index()
    g["ever_touched_gold"] = (g["n_gold_edits"] > 0).astype(int)
    g["on_target_gold"] = np.where(g["n_edit_all"] > 0,
                                   g["n_gold_edits"] / g["n_edit_all"].clip(lower=1), np.nan)
    g["y_fail"] = (g["reward"] == 0).astype(int)
    # the mode target exists only for failed runs; it is defined for every failed run,
    # including runs that never edited anything (those are LOST by definition)
    g["y_wrong_fix"] = np.where(g["y_fail"] == 1, g["ever_touched_gold"], np.nan)
    return g


# --------------------------------------------------------------------------------------
# causal per-step reference detectors (mirrors scripts/analyse_detector_families.py)
# --------------------------------------------------------------------------------------


def _run_length(mask: np.ndarray) -> np.ndarray:
    """Length of the current run of True values in ``mask`` (1-based)."""
    n = len(mask)
    if n == 0:
        return np.zeros(0, dtype=int)
    idx = np.arange(n)
    start = np.maximum.accumulate(np.where(~mask, idx, 0))
    return idx - start + 1


def flags_ngram_loop(sig: np.ndarray) -> np.ndarray:
    """The same signature recurring with period 2, 3 or 4, three times in a row."""
    n = len(sig)
    flag = np.zeros(n, dtype=float)
    if n < 3:
        return flag
    for period in (2, 3, 4):
        if n <= period:
            continue
        eq = np.zeros(n, dtype=bool)
        eq[period:] = sig[period:] == sig[:-period]
        run = _run_length(eq)
        flag[eq & (run >= 3)] = 1.0
    return flag


def flags_exact_burst(sig: np.ndarray, w: int = 5, need: int = 3) -> np.ndarray:
    """``need`` identical signatures inside a trailing window of ``w`` steps."""
    n = len(sig)
    flag = np.zeros(n, dtype=float)
    if n < need:
        return flag
    sig_list = sig.tolist()
    for i in range(n):
        lo = max(0, i - w + 1)
        c = Counter(sig_list[lo:i + 1])
        if max(c.values()) >= need:
            flag[i] = 1.0
    return flag


def flags_tfnorm(texts: Sequence[str], threshold: float = 0.85) -> np.ndarray:
    """Cosine similarity of one step's token multiset to the nearest earlier one.

    Faithful to the frozen implementation, which tokenises ``targets_str`` (the paths a
    command targets), not the observation body -- this corpus does not carry observation
    text.  ``flags_tfnorm(st_sig)`` runs the same rule on the status-signature string, the
    closest available surrogate for "the observation did not change".
    """
    n = len(texts)
    vecs = [Counter(str(t).lower().split()) for t in texts]
    flag = np.zeros(n, dtype=float)
    for i in range(1, n):
        a = vecs[i]
        if not a:
            continue
        best = 0.0
        for j in range(i):
            b = vecs[j]
            if not b:
                continue
            common = sum((a & b).values())
            den = math.sqrt(sum(a.values()) * sum(b.values()))
            if den > 0:
                best = max(best, common / den)
            if best > threshold:
                break
        if best > threshold:
            flag[i] = 1.0
    return flag


def _entropy(counts: np.ndarray, l_n: float) -> float:
    if l_n <= 0 or counts.sum() == 0:
        return 0.0
    p = counts / counts.sum()
    p = p[p > 0]
    return float(-(p * np.log(p)).sum() / l_n)


# --------------------------------------------------------------------------------------
# prefix features
# --------------------------------------------------------------------------------------


def prefix_features(steps: pd.DataFrame, fractions: Sequence[float]
                    ) -> Tuple[Dict[float, pd.DataFrame], Dict[str, object]]:
    """One pass over the corpus; one feature row per run and fraction.

    Every per-step detector flag is backward-looking (the reference implementations only
    ever compare a step with earlier steps), so aggregating them over the prefix is
    identical to running the reference function on the prefix slice.
    """
    steps = steps.sort_values(["run_id", "step"], kind="stable")
    arr = {c: steps[c].to_numpy() for c in STEP_COLS}
    base_all = basenames(steps["file_shown"])
    n_tot = len(steps)

    rid = arr["run_id"]
    edges = np.flatnonzero(rid[1:] != rid[:-1]) + 1
    starts = np.concatenate([[0], edges])
    ends = np.concatenate([edges, [n_tot]])
    n_runs = len(starts)
    print(f"  walking {n_runs} runs / {n_tot} steps ...", flush=True)

    keys = ["run_id", "task", "model"] + list(COUNT_FEATURES) + [
        "_prefix_len", "_prefix_mean_flag_ngram", "_prefix_mean_flag_burst",
        "_prefix_mean_flag_tfnorm", "_prefix_mean_flag_tfnorm_stsig",
        "_agentstop_outlen", "_agentstop_overlap"]
    rows: Dict[float, List[Dict[str, float]]] = {f: [] for f in fractions}

    is_edit_all = arr["is_edit"].astype(np.int8)
    added_all = arr["added_lines_n"].astype(np.int64)
    obs_all = arr["obs_chars"].astype(np.float64)
    txt_all = arr["text_chars"].astype(np.float64)
    is_test_all = arr["is_test"].astype(np.int8)
    is_run_all = arr["is_run"].astype(np.int8)
    is_read_all = arr["is_read"].astype(np.int8)
    is_search_all = arr["is_search"].astype(np.int8)
    is_finish_all = arr["is_finish"].astype(np.int8)
    st_p_all = np.clip(arr["st_passed"].astype(np.int64), 0, None)
    st_f_all = np.clip(arr["st_failed"].astype(np.int64), 0, None)
    st_e_all = np.clip(arr["st_error"].astype(np.int64), 0, None)
    err_all = ((arr["st_tb"].astype(np.int64) > 0) | (arr["st_syntax"].astype(np.int64) > 0)
               | (arr["st_notfound"].astype(np.int64) > 0)
               | (arr["st_error"].astype(np.int64) > 0)).astype(np.int8)
    verb_all = arr["verb"]
    fam_all = arr["cmd_family"]
    sig_all = arr["sig"]
    tgt_all = arr["targets_str"]
    stsig_all = arr["st_sig"]
    nsteps_all = arr["n_steps"].astype(np.int64)

    t0 = time.time()
    for k in range(n_runs):
        s, e = int(starts[k]), int(ends[k])
        n = e - s
        is_edit = is_edit_all[s:e]
        added = added_all[s:e]
        obs = obs_all[s:e]
        txt = txt_all[s:e]
        sig = sig_all[s:e]
        base = base_all[s:e]
        verb = verb_all[s:e]
        fam = fam_all[s:e]

        is_testish = ((is_test_all[s:e] == 1) | (verb == "verify")).astype(np.int8)
        is_verify = (verb == "verify").astype(np.int8)
        is_run = ((is_run_all[s:e] == 1) | (verb == "run")).astype(np.int8)
        noop = (is_edit.astype(np.int8) & (added == 0).astype(np.int8)).astype(np.int8)

        c_edit = np.cumsum(is_edit, dtype=np.int64)
        c_noop = np.cumsum(noop, dtype=np.int64)
        c_tst = np.cumsum(is_testish, dtype=np.int64)
        c_ver = np.cumsum(is_verify, dtype=np.int64)
        c_run = np.cumsum(is_run, dtype=np.int64)
        c_read = np.cumsum(is_read_all[s:e], dtype=np.int64)
        c_srch = np.cumsum(is_search_all[s:e], dtype=np.int64)
        c_fin = np.cumsum(is_finish_all[s:e], dtype=np.int64)
        c_pass = np.cumsum(st_p_all[s:e], dtype=np.int64)
        c_fail = np.cumsum(st_f_all[s:e], dtype=np.int64)
        c_err = np.cumsum(st_e_all[s:e], dtype=np.int64)
        c_obs = np.cumsum(obs, dtype=np.float64)
        c_txt = np.cumsum(txt, dtype=np.float64)
        c_errflag = np.cumsum(err_all[s:e], dtype=np.int64)

        x = np.arange(1, n + 1, dtype=np.float64)
        c_x, c_x2 = np.cumsum(x), np.cumsum(x * x)
        c_xobs = np.cumsum(x * obs)

        same = np.zeros(n, dtype=bool)
        if n > 1:
            same[1:] = sig[1:] == sig[:-1]
        c_same = np.cumsum(same, dtype=np.int64)
        consec = _run_length(same)
        c_consec3 = np.cumsum(consec >= 3, dtype=np.int64) if n else np.zeros(0, dtype=np.int64)
        max_consec = np.maximum.accumulate(consec) if n else np.zeros(0, dtype=np.int64)

        sig_uniq = np.empty(n, dtype=np.int64)
        fam_uniq = np.empty(n, dtype=np.int64)
        seen_sig: set = set()
        seen_fam: set = set()
        for i in range(n):
            seen_sig.add(sig[i])
            seen_fam.add(fam[i])
            sig_uniq[i] = len(seen_sig)
            fam_uniq[i] = len(seen_fam)

        n_distinct = np.zeros(n, dtype=np.int64)
        rep_edit = np.zeros(n, dtype=np.int64)
        first_edit_idx = np.zeros(n, dtype=np.int64)
        cnt: Dict[str, int] = {}
        nfile = 0
        fidx = 0
        for i in range(n):
            if is_edit[i] and base[i]:
                b = base[i]
                if b in cnt:
                    cnt[b] += 1
                    rep_edit[i] = 1
                else:
                    cnt[b] = 1
                    nfile += 1
                if fidx == 0:
                    fidx = i + 1
            n_distinct[i] = nfile
            first_edit_idx[i] = fidx
        c_repedit = np.cumsum(rep_edit, dtype=np.int64)

        c_ng = np.cumsum(flags_ngram_loop(sig))
        c_eb = np.cumsum(flags_exact_burst(sig))
        c_tf = np.cumsum(flags_tfnorm(tgt_all[s:e].tolist()))
        c_ts = np.cumsum(flags_tfnorm(stsig_all[s:e].tolist()))

        nst = int(nsteps_all[s])
        for f in fractions:
            L = max(1, min(n, int(round(f * nst))))
            i = L - 1
            nE = int(c_edit[i])
            d: Dict[str, float] = {
                "run_id": arr["run_id"][s], "task": arr["task"][s], "model": arr["model"][s],
                "_prefix_len": float(L),
                "no_edit_yet": float(nE == 0),
                "first_edit_frac": float(first_edit_idx[i]) / L if first_edit_idx[i] else 0.0,
                "edit_rate": nE / L,
                "noop_edit_frac": float(c_noop[i]) / nE if nE else 0.0,
                "distinct_files_per_edit": float(n_distinct[i]) / nE if nE else 0.0,
                "repeat_file_edit_frac": float(c_repedit[i]) / nE if nE else 0.0,
                "any_file_edited_twice": float(c_repedit[i] > 0),
                "testish_per_step": float(c_tst[i]) / L,
                "verify_frac": float(c_ver[i]) / L,
                "run_frac": float(c_run[i]) / L,
                "read_frac": float(c_read[i]) / L,
                "search_frac": float(c_srch[i]) / L,
                "finish_seen": float(c_fin[i] > 0),
                "unique_sig_frac": float(sig_uniq[i]) / L,
                "unique_cmdfam_frac": float(fam_uniq[i]) / L,
                "sig_entropy": _entropy(np.unique(sig[:L], return_counts=True)[1], math.log(L + 1)),
                "cmdfam_entropy": _entropy(np.unique(fam[:L], return_counts=True)[1],
                                           math.log(L + 1)),
                "repeat_sig_frac": float(c_same[i]) / max(1, L - 1),
                "max_consec_repeat_norm": float(max_consec[i]) / L,
                "has_repeat_3plus": float(c_consec3[i] > 0),
                "obs_mean": float(c_obs[i]) / L,
                "obs_last_over_mean": float(obs[i]) / (float(c_obs[i]) / L + 1.0),
                "obs_slope_norm": 0.0,
                "obs_half_ratio": 1.0,
                "text_chars_mean": float(c_txt[i]) / L,
                "text_to_obs": float(c_txt[i]) / (float(c_obs[i]) + 1.0),
                "obs_mean_over_text": float(c_obs[i]) / (float(c_txt[i]) + 1.0),
                "err_rate": float(c_errflag[i]) / L,
                "pass_seen_per_step": float(c_pass[i]) / L,
                "fail_seen_per_step": float(c_fail[i]) / L,
                "err_seen_per_step": float(c_err[i]) / L,
                "fail_minus_pass_norm": float(c_fail[i] - c_pass[i]) / L,
                "any_test_fail_seen": float(c_fail[i] > 0),
                "any_test_pass_seen": float(c_pass[i] > 0),
                # raw counts (length-carrying; flagged in the report)
                "n_edit_prefix": float(nE),
                "n_distinct_files": float(n_distinct[i]),
                "n_testish": float(c_tst[i]),
                "n_verify": float(c_ver[i]),
                "n_run": float(c_run[i]),
                "n_read": float(c_read[i]),
                "n_search": float(c_srch[i]),
                "n_noop_edit": float(c_noop[i]),
                "st_pass_sum": float(c_pass[i]),
                "st_fail_sum": float(c_fail[i]),
                "st_err_sum": float(c_err[i]),
                "first_edit_index": float(first_edit_idx[i]),
                "obs_sum": float(c_obs[i]),
                "max_consec_repeat_abs": float(max_consec[i]),
                "n_repeat_file_edits": float(c_repedit[i]),
                # baseline inputs
                "_prefix_mean_flag_ngram": float(c_ng[i]) / L,
                "_prefix_mean_flag_burst": float(c_eb[i]) / L,
                "_prefix_mean_flag_tfnorm": float(c_tf[i]) / L,
                "_prefix_mean_flag_tfnorm_stsig": float(c_ts[i]) / L,
                "_agentstop_outlen": float(c_txt[i]) / L,
                "_agentstop_overlap": float(c_same[i]) / max(1, L - 1),
            }
            if L >= 4:
                den = L * c_x2[i] - c_x[i] ** 2
                if abs(den) > 1e-9:
                    slope = (L * c_xobs[i] - c_x[i] * c_obs[i]) / den
                    d["obs_slope_norm"] = float(slope) / (float(c_obs[i]) / L + 1.0)
                half = L // 2
                a = obs[:half].mean()
                b2 = obs[half:L].mean()          # second half *of the prefix*, never past it
                d["obs_half_ratio"] = float(b2) / (float(a) + 1.0)
            rows[f].append(d)
        if (k + 1) % 2000 == 0:
            print(f"    {k + 1}/{n_runs} runs  ({time.time() - t0:.1f}s)", flush=True)

    tables = {f: pd.DataFrame(rows[f])[keys] for f in fractions}
    meta = {
        "n_runs": n_runs, "n_steps": n_tot,
        "prefix_len_quantiles": {
            str(f): {str(q): float(np.quantile(tables[f]["_prefix_len"], q))
                     for q in (0.05, 0.25, 0.5, 0.75, 0.95)} for f in fractions},
        "prefix_len_mean": {str(f): float(tables[f]["_prefix_len"].mean()) for f in fractions},
        "tfnorm_targets_nonempty_frac": float(
            (pd.Series(tgt_all).astype(str).str.len() > 0).mean()),
        "n_features_rates": len(RATE_FEATURES), "n_features_counts": len(COUNT_FEATURES),
        "rate_features": list(RATE_FEATURES), "count_features": list(COUNT_FEATURES),
    }
    return tables, meta


# --------------------------------------------------------------------------------------
# fitting and metrics
# --------------------------------------------------------------------------------------


def _clean(X) -> np.ndarray:
    return np.nan_to_num(np.asarray(X, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, cols: Sequence[str], y_col: str,
                kind: str = "logit", C: float = 1.0) -> np.ndarray:
    Xtr = _clean(train[list(cols)].to_numpy())
    Xte = _clean(test[list(cols)].to_numpy())
    ytr = train[y_col].to_numpy(dtype=float)
    mu, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    if kind == "gbm":
        from sklearn.ensemble import HistGradientBoostingClassifier
        model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3,
                                               random_state=0)
    else:
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(max_iter=2000, C=C, solver="lbfgs", random_state=0)
    model.fit((Xtr - mu) / sd, ytr)
    return np.asarray(model.predict_proba((Xte - mu) / sd)[:, 1], dtype=float)


def oof_scores(df: pd.DataFrame, cols: Sequence[str], y_col: str, n_folds: int = 5,
               seed: int = 0, kind: str = "logit") -> np.ndarray:
    """Out-of-fold scores over whole-task folds (never fits on a test task)."""
    oof = np.full(len(df), np.nan)
    y = df[y_col].to_numpy(dtype=float)
    for tr, te in E.task_disjoint_folds(df, n_folds=n_folds, seed=seed):
        if len(np.unique(y[tr])) < 2 or len(te) < 5:
            continue
        oof[te] = fit_predict(df.iloc[tr], df.iloc[te], cols, y_col, kind=kind)
    return oof


def _auc(y: np.ndarray, s: np.ndarray) -> float:
    return E.safe_auc(np.asarray(y, dtype=float), np.asarray(s, dtype=float))


def _recall_at(y: np.ndarray, s: np.ndarray, budget: float) -> float:
    k = int(round(budget * len(y)))
    if k < 1 or y.sum() == 0:
        return float("nan")
    order = np.argsort(-np.nan_to_num(s, nan=-np.inf), kind="stable")
    return float(y[order[:k]].sum() / y.sum())


def evaluate_methods(df: pd.DataFrame, y_col: str, method_oof: Dict[str, List[np.ndarray]],
                     budgets: Sequence[float] = BUDGETS, n_boot: int = 500, boot_seed: int = 7,
                     primary: str = PRIMARY) -> Dict[str, object]:
    """AUC (mean over fold seeds) + bootstrap CI over *tasks* + recall at alert budgets +
    paired deltas against every baseline.

    The CI resamples whole tasks -- the unit the folds hold out -- so it covers sampling
    noise and fold assignment.  Pairwise deltas are computed inside the *same* bootstrap
    sample, which makes them paired.  The point AUC is the mean over fold seeds; the
    bootstrap uses the fold-seed-averaged score (averaging scores is not identical to
    averaging AUCs; both are reported when they differ).
    """
    y = df[y_col].to_numpy(dtype=float)
    tasks = df["task"].to_numpy()
    uniq, idx_by = _make_clusters(tasks)
    rng = np.random.default_rng(boot_seed)
    methods = list(method_oof)
    avg_score = {m: np.nanmean(np.vstack(method_oof[m]), axis=0) for m in methods}
    point: Dict[str, float] = {}
    sd: Dict[str, float] = {}
    a_of_avg: Dict[str, float] = {}
    recall: Dict[str, Dict[str, float]] = {}
    for m in methods:
        per_seed = [a for a in (_auc(y, o) for o in method_oof[m]) if not np.isnan(a)]
        point[m] = float(np.mean(per_seed)) if per_seed else float("nan")
        sd[m] = float(np.std(per_seed, ddof=1)) if len(per_seed) > 1 else 0.0
        a_of_avg[m] = _auc(y, avg_score[m])
        recall[m] = {str(b): _recall_at(y, avg_score[m], b) for b in budgets}
    boot: Dict[str, List[float]] = {m: [] for m in methods}
    boot_rec: Dict[str, List[float]] = {m: [] for m in methods}
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by[t] for t in pick])
        yy = y[idx]
        if len(np.unique(yy)) < 2:
            continue
        for m in methods:
            boot[m].append(_auc(yy, avg_score[m][idx]))
            boot_rec[m].append(_recall_at(yy, avg_score[m][idx], budgets[-1]))
    out_methods: Dict[str, object] = {}
    for m in methods:
        a = np.asarray([v for v in boot[m] if not np.isnan(v)])
        r = np.asarray([v for v in boot_rec[m] if not np.isnan(v)])
        out_methods[m] = {
            "auc": point[m],
            "auc_of_seed_averaged_score": a_of_avg[m],
            "auc_ci95": [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
            if len(a) > 10 else [float("nan")] * 2,
            "auc_sd_over_fold_seeds": sd[m],
            "recall_at_budget": recall[m],
            "recall_ci95_at_10pct": [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))]
            if len(r) > 10 else [float("nan")] * 2,
        }
    deltas: Dict[str, object] = {}
    if primary in methods:
        pa = np.asarray(boot[primary])
        for m in methods:
            if m == primary:
                continue
            d = pa - np.asarray(boot[m])
            d = d[~np.isnan(d)]
            deltas[m] = {
                "delta": point[primary] - point[m],
                "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]
                if len(d) > 10 else [float("nan")] * 2,
                "p_two_sided": float(2 * min((d <= 0).mean(), (d >= 0).mean())) if len(d) > 10
                else float("nan"),
                "primary_beats": bool(len(d) > 10 and np.percentile(d, 2.5) > 0),
            }
    return {"n": int(len(df)), "base_rate": float(np.nanmean(y)),
            "y_positive": int(np.nansum(y)), "methods": out_methods,
            "deltas_primary_vs_baselines": deltas, "primary": primary, "n_bootstrap": n_boot}


def _make_clusters(tasks: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    uniq = np.unique(tasks)
    return uniq, {t: np.flatnonzero(tasks == t) for t in uniq}


# --------------------------------------------------------------------------------------
# calibration
# --------------------------------------------------------------------------------------


def _pvals(score: np.ndarray, null_scores: np.ndarray) -> np.ndarray:
    """Right-tail p-value against the calibration null, with +1 smoothing."""
    ns = np.sort(null_scores)
    n = len(ns)
    ge = n - np.searchsorted(ns, score, side="left")
    return (1.0 + ge) / (1.0 + n)


def calibration_study(tables: Dict[float, pd.DataFrame], labels: pd.DataFrame,
                      fractions: Sequence[float], y_col: str, cols: Sequence[str],
                      alphas: Sequence[float] = (0.05, 0.10, 0.20, 0.50), n_seeds: int = 5,
                      kappa: float = 0.5) -> Dict[str, object]:
    """Sequential alarm rules whose Type-I error is controlled on held-out tasks.

    Tasks are split three ways (train / calibration / test) by whole tasks.  The model is
    fitted on ``train``, the null distribution of the score is estimated on the *negative*
    runs of ``calibration``, and every reported rate is measured on ``test``.

    Two combination rules across the four checkpoints, both valid under **arbitrary
    dependence** between checkpoints (the prefixes are nested, so they are certainly
    dependent):

    ``seq_threshold``  alarm at the first checkpoint where ``p_f <= alpha * w_f``; the union
                       bound gives sequence-level Type-I error ``<= alpha``.
    ``e_value_mean``   ``e_f = kappa * p_f ** (kappa - 1)`` is an e-value for any
                       ``kappa in (0,1)``; the mean of e-values is itself an e-value under
                       arbitrary dependence, so ``mean_f e_f >= 1/alpha`` has Type-I error
                       ``<= alpha``.
    """
    joined: Dict[float, pd.DataFrame] = {}
    for f in fractions:
        t = tables[f].merge(labels[["run_id", y_col, "reward", "n_steps"]], on="run_id",
                            how="inner")
        t = t[t[y_col].notna()].reset_index(drop=True)
        joined[f] = t
    order = joined[fractions[0]]["run_id"].tolist()
    for f in fractions:
        assert joined[f]["run_id"].tolist() == order, "prefix tables must share a row order"
    base_tasks = np.array(sorted(joined[fractions[0]]["task"].unique()))
    per_alpha: Dict[str, List[Dict[str, float]]] = {str(a): [] for a in alphas}
    per_alpha_e: Dict[str, List[Dict[str, float]]] = {str(a): [] for a in alphas}
    detail_seed0: Optional[Dict[str, object]] = None
    for seed in range(n_seeds):
        rng = np.random.default_rng(1000 + seed)
        tasks = base_tasks.copy()
        rng.shuffle(tasks)
        nA = int(round(0.50 * len(tasks)))
        nB = int(round(0.25 * len(tasks)))
        tr_t, ca_t, te_t = (set(tasks[:nA].tolist()), set(tasks[nA:nA + nB].tolist()),
                            set(tasks[nA + nB:].tolist()))
        pvals: Dict[float, np.ndarray] = {}
        n_null_calib = 0
        for f in fractions:
            t = joined[f]
            tr = t[t["task"].isin(tr_t)]
            ca = t[t["task"].isin(ca_t)]
            te_m = t["task"].isin(te_t).to_numpy()
            if len(te_m) == 0 or len(np.unique(tr[y_col].to_numpy(dtype=float))) < 2:
                pvals[f] = np.full(len(t), np.nan)
                continue
            sc_te = fit_predict(tr, t[te_m], cols, y_col)
            sc_ca = fit_predict(tr, ca, cols, y_col)
            null_scores = sc_ca[ca[y_col].to_numpy(dtype=float) == 0]
            n_null_calib = len(null_scores)
            if len(null_scores) < 20:
                pvals[f] = np.full(len(t), np.nan)
                continue
            full = np.full(len(t), np.nan)
            full[te_m] = _pvals(sc_te, null_scores)
            pvals[f] = full
        te_mask = joined[fractions[0]]["task"].isin(te_t).to_numpy()
        yv = joined[fractions[0]][y_col].to_numpy(dtype=float)[te_mask]
        pos, neg = yv == 1, yv == 0
        for a in alphas:
            w = np.full(len(fractions), 1.0 / len(fractions))
            alarm_f = np.full(int(te_mask.sum()), np.nan)
            for fi, f in enumerate(fractions):
                pv = pvals[f][te_mask]
                fresh = np.isnan(alarm_f) & (pv <= a * w[fi])
                alarm_f[fresh] = f
            fired = ~np.isnan(alarm_f)
            rec: Dict[str, float] = {
                "detection_rate_any_checkpoint": float(fired[pos].mean()) if pos.sum() else float("nan"),
                "false_alarm_rate": float(fired[neg].mean()) if neg.sum() else float("nan"),
                "n_test": float(len(yv)), "n_pos": float(pos.sum()), "n_neg": float(neg.sum()),
                "n_null_calibration": float(n_null_calib),
            }
            for f in fractions:
                rec[f"detection_by_{f}"] = (float(np.nansum(fired[pos] & (alarm_f[pos] <= f + 1e-9)))
                                            / max(1.0, float(pos.sum())))
                rec[f"false_alarm_by_{f}"] = (float(np.nansum(fired[neg] & (alarm_f[neg] <= f + 1e-9)))
                                              / max(1.0, float(neg.sum())))
            rec["mean_alarm_fraction_among_detected"] = (
                float(np.nanmean(alarm_f[pos & fired])) if (pos & fired).sum() else float("nan"))
            per_alpha[str(a)].append(rec)
            e = np.zeros(int(te_mask.sum()))
            for f in fractions:
                pv = np.clip(pvals[f][te_mask], 1e-12, 1.0)
                e = e + kappa * pv ** (kappa - 1.0)
            e = e / len(fractions)
            e_alarm = e >= 1.0 / a
            per_alpha_e[str(a)].append({
                "detection_rate_any_checkpoint": float(e_alarm[pos].mean()) if pos.sum() else float("nan"),
                "false_alarm_rate": float(e_alarm[neg].mean()) if neg.sum() else float("nan"),
                "n_test": float(len(yv)), "n_pos": float(pos.sum()), "n_neg": float(neg.sum()),
                "mean_e_value_on_nulls": float(e[neg].mean()) if neg.sum() else float("nan"),
                "mean_e_value_on_positives": float(e[pos].mean()) if pos.sum() else float("nan"),
            })
            if seed == 0:
                detail_seed0 = {
                    "alpha": a, "n_test_runs": int(len(yv)),
                    "detection_by_checkpoint": {str(f): rec[f"detection_by_{f}"] for f in fractions},
                    "false_alarm_by_checkpoint": {str(f): rec[f"false_alarm_by_{f}"] for f in fractions},
                    "e_value_rule": per_alpha_e[str(a)][-1],
                }
    out: Dict[str, object] = {"alpha_levels": list(alphas), "n_seeds": n_seeds,
                              "kappa": kappa,
                              "design": "whole-task train(50%)/calibration(25%)/test(25%) split; "
                                        "null = negative runs of the calibration block",
                              "by_alpha": {}, "detail_seed0": detail_seed0}
    for a in alphas:
        arr, arrev = per_alpha[str(a)], per_alpha_e[str(a)]
        out["by_alpha"][str(a)] = {
            "seq_threshold": {
                "false_alarm_rate_mean": float(np.nanmean([r["false_alarm_rate"] for r in arr])),
                "false_alarm_rate_max": float(np.nanmax([r["false_alarm_rate"] for r in arr])),
                "detection_rate_mean": float(np.nanmean([r["detection_rate_any_checkpoint"] for r in arr])),
                "detection_rate_min": float(np.nanmin([r["detection_rate_any_checkpoint"] for r in arr])),
                "detection_by_checkpoint_mean": {str(f): float(np.nanmean([r[f"detection_by_{f}"] for r in arr]))
                                                 for f in fractions},
                "false_alarm_by_checkpoint_mean": {str(f): float(np.nanmean([r[f"false_alarm_by_{f}"] for r in arr]))
                                                   for f in fractions},
                "mean_alarm_fraction_among_detected": float(
                    np.nanmean([r["mean_alarm_fraction_among_detected"] for r in arr])),
                "n_test_runs_mean": float(np.nanmean([r["n_test"] for r in arr])),
                "n_null_calibration_mean": float(np.nanmean([r["n_null_calibration"] for r in arr])),
            },
            "e_value_mean": {
                "false_alarm_rate_mean": float(np.nanmean([r["false_alarm_rate"] for r in arrev])),
                "false_alarm_rate_max": float(np.nanmax([r["false_alarm_rate"] for r in arrev])),
                "detection_rate_mean": float(np.nanmean([r["detection_rate_any_checkpoint"] for r in arrev])),
                "mean_e_value_on_nulls": float(np.nanmean([r["mean_e_value_on_nulls"] for r in arrev])),
                "mean_e_value_on_positives": float(np.nanmean([r["mean_e_value_on_positives"] for r in arrev])),
            },
        }
    return out


# --------------------------------------------------------------------------------------
# decision curve
# --------------------------------------------------------------------------------------


def decision_curve(df: pd.DataFrame, y_mode: np.ndarray, score: np.ndarray,
                   lambdas: Sequence[float] = (0.0, 0.25, 0.5), n_boot: int = 400,
                   boot_seed: int = 11) -> Dict[str, object]:
    """SEARCH vs VERIFY routing, conditional on the run failing.

    A failing run routed to the mode it actually has yields full credit (1.0); routed to
    the wrong mode it yields ``lambda`` (partial credit -- the other intervention is not
    worthless, it is the wrong bet).  ``lambda = 0`` is the clean "correct routing" reading.
    """
    y = np.asarray(y_mode, dtype=float)          # 1 = WRONG-FIX (=> VERIFY), 0 = LOST (=> SEARCH)
    s = np.asarray(score, dtype=float)
    ok = ~np.isnan(y) & ~np.isnan(s)
    y, s, tasks = y[ok], s[ok], df["task"].to_numpy()[ok]
    route = (s > 0.5).astype(int)                # 1 = VERIFY
    uniq, idx_by = _make_clusters(tasks)
    p1 = float(y.mean())
    out: Dict[str, object] = {"n_failing_runs": int(len(y)), "base_rate_wrong_fix": p1,
                              "definition": "credit 1.0 if routed to the run's true mode, "
                                            "lambda otherwise",
                              "routing_accuracy": float((route == y.astype(int)).mean()),
                              "verify_rate": float(route.mean()), "by_lambda": {}}
    rng = np.random.default_rng(boot_seed)
    picks = [np.concatenate([idx_by[t] for t in rng.choice(uniq, size=len(uniq), replace=True)])
             for _ in range(n_boot)]
    for lam in lambdas:
        cred = np.where(route == y.astype(int), 1.0, lam)
        base_search = float(np.where(y == 0, 1.0, lam).mean())
        base_verify = float(np.where(y == 1, 1.0, lam).mean())
        base_random = float(p1 * (p1 * 1.0 + (1 - p1) * lam)
                            + (1 - p1) * (p1 * lam + (1 - p1) * 1.0))
        best_base = max(base_search, base_verify, base_random)
        d = []
        for idx in picks:
            yy, cc = y[idx], cred[idx]
            if len(yy) == 0:
                continue
            pb = float(yy.mean())
            br = float(pb * (pb * 1.0 + (1 - pb) * lam) + (1 - pb) * (pb * lam + (1 - pb) * 1.0))
            d.append(float(cc.mean()) - max(float(np.where(yy == 0, 1.0, lam).mean()),
                                            float(np.where(yy == 1, 1.0, lam).mean()), br))
        d = np.asarray(d)
        out["by_lambda"][str(lam)] = {
            "detector": float(cred.mean()), "always_search": base_search,
            "always_verify": base_verify, "random_routing": base_random,
            "best_baseline": best_base, "delta_vs_best_baseline": float(cred.mean() - best_base),
            "delta_ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]
            if len(d) > 10 else [float("nan")] * 2,
            "beats_all_three": bool(len(d) > 10 and np.percentile(d, 2.5) > 0),
        }
    return out


def gated_utility(df_all: pd.DataFrame, p_fail: np.ndarray, p_mode: np.ndarray,
                  lam: float = 0.25, cost: float = 0.0, n_boot: int = 400,
                  boot_seed: int = 13) -> Dict[str, object]:
    """Over *all* runs: intervene only when the failure detector fires, then route.

    Utility over every run in the population (failures addressed, minus the cost of
    intervening).  ``always_search``/``always_verify`` intervene on everything and route
    one way; ``random_routing`` intervenes on everything and flips a fair coin.
    """
    yf = np.asarray(df_all["y_fail"].to_numpy(dtype=float))
    ym = np.asarray(df_all["y_wrong_fix"].to_numpy(dtype=float))
    pf = np.asarray(p_fail, dtype=float)
    pm = np.asarray(p_mode, dtype=float)
    tasks = df_all["task"].to_numpy()
    alarm = pf > 0.5
    route = (pm > 0.5).astype(float)
    credit = np.where(route == np.nan_to_num(ym, nan=-1.0), 1.0, lam)
    u_det = float((np.where(alarm & ~np.isnan(ym), credit, 0.0).mean()) - cost * alarm.mean())
    base_s = float(np.where(ym == 0, 1.0, lam).mean() * yf.mean() - cost)
    base_v = float(np.where(ym == 1, 1.0, lam).mean() * yf.mean() - cost)
    p1 = float(np.nanmean(ym))
    base_r = float(0.5 * (p1 * 1.0 + (1 - p1) * lam) + 0.5 * ((1 - p1) * 1.0 + p1 * lam))
    base_r = base_r * float(yf.mean()) - cost
    n_fail = float((yf == 1).sum())
    addressed = float(np.where(alarm & ~np.isnan(ym), credit, 0.0).sum() / max(1.0, n_fail))
    uniq, idx_by = _make_clusters(tasks)
    rng = np.random.default_rng(boot_seed)
    d = []
    for _ in range(n_boot):
        idx = np.concatenate([idx_by[t] for t in rng.choice(uniq, size=len(uniq), replace=True)])
        yyf, yym, aa, cc = yf[idx], ym[idx], alarm[idx], credit[idx]
        u = float(np.where(aa & ~np.isnan(yym), cc, 0.0).mean()) - cost * float(aa.mean())
        bs = float(np.where(yym == 0, 1.0, lam).mean() * yyf.mean() - cost)
        bv = float(np.where(yym == 1, 1.0, lam).mean() * yyf.mean() - cost)
        pb = float(np.nanmean(yym))
        br = (0.5 * (pb * 1.0 + (1 - pb) * lam) + 0.5 * ((1 - pb) * 1.0 + pb * lam)) \
            * float(yyf.mean()) - cost
        d.append(u - max(bs, bv, br))
    d = np.asarray(d)
    return {"n_runs": int(len(df_all)), "lambda": lam, "cost_per_intervention": cost,
            "detector_utility": u_det, "detector_share_of_failures_addressed": addressed,
            "intervention_rate": float(alarm.mean()),
            "always_search_utility": base_s, "always_verify_utility": base_v,
            "random_utility": base_r,
            "delta_ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]
            if len(d) > 10 else [float("nan")] * 2,
            "beats_all_three": bool(len(d) > 10 and np.percentile(d, 2.5) > 0)}


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------


def load_inputs(limit: Optional[int], seed: int = 0):
    gold_df = pd.read_parquet(OUT / "gold_patches.parquet")
    gold = {str(k): set(v) for k, v in zip(gold_df["instance_id"], gold_df["gold_basenames"])}
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=STEP_COLS)
    steps = steps[steps["task"].isin(gold)].copy()
    if limit:
        rng = np.random.default_rng(seed)
        tasks = np.array(sorted(steps["task"].unique()))
        tasks = tasks[rng.permutation(len(tasks))][:max(8, limit // 20)]
        steps = steps[steps["task"].isin(set(tasks.tolist()))]
        keep = steps["run_id"].drop_duplicates()
        if len(keep) > limit:
            keep = keep.iloc[:limit]
        steps = steps[steps["run_id"].isin(set(keep.tolist()))]
    return steps, gold


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                    choices=["all", "labels", "features", "eval", "calib", "decision"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--calib-seeds", type=int, default=5)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = args.tag or (f"_lim{args.limit}" if args.limit else "")
    t_start = time.time()

    steps, gold = load_inputs(args.limit)
    print(f"steps {len(steps)} over {steps.run_id.nunique()} runs, "
          f"{steps.task.nunique()} instances with a gold patch")

    labels = build_labels(steps, gold)
    labels.to_parquet(CACHE / f"labels{tag}.parquet", index=False)
    n_edit_steps = int((steps["is_edit"] == 1).sum())
    unknown = int(((steps["is_edit"] == 1) & (basenames(steps["file_shown"]) == "")).sum())
    coverage = {
        "instances_in_corpus": 1213, "instances_with_gold": len(gold),
        "instances_used": int(labels["task"].nunique()),
        "runs_in_corpus": int(pd.read_parquet(
            ROOT / "data" / "processed" / "steps" / "nebius" / "runs.parquet",
            columns=["run_id"]).shape[0]),
        "runs_with_gold": int(len(labels)),
        "edit_steps": n_edit_steps,
        "edit_steps_with_unknown_file": unknown,
        "edit_steps_with_unknown_file_frac": unknown / max(1, n_edit_steps),
    }
    failed = labels[labels["y_fail"] == 1]
    failed_edit = failed[failed["n_edit_all"] > 0]
    label_block = {
        "runs_with_gold": int(len(labels)),
        "y_fail_base_rate": float(labels["y_fail"].mean()),
        "n_failed": int(len(failed)), "n_success": int((labels["y_fail"] == 0).sum()),
        "failed_runs_with_at_least_one_edit": int(len(failed_edit)),
        "y_wrong_fix_base_rate_over_failed": float(failed["ever_touched_gold"].mean()),
        "y_wrong_fix_base_rate_over_failed_with_edits": float(
            failed_edit["ever_touched_gold"].mean()),
        "success_runs_ever_touched_gold": float(
            labels.loc[labels["y_fail"] == 0, "ever_touched_gold"].mean()),
        "on_target_gold_mean_failed": float(failed["on_target_gold"].mean()),
        "on_target_gold_mean_success": float(
            labels.loc[labels["y_fail"] == 0, "on_target_gold"].mean()),
        "lost_runs_that_never_edited": int(((labels["y_fail"] == 1)
                                            & (labels["ever_touched_gold"] == 0)
                                            & (labels["n_edit_all"] == 0)).sum()),
    }
    print(f"labels: {len(labels)} runs with gold; y_fail {label_block['y_fail_base_rate']:.4f}; "
          f"y_wrong_fix over failed {label_block['y_wrong_fix_base_rate_over_failed']:.4f}")

    rpi = labels.groupby("task").size()
    mixed = labels.groupby("task")["y_fail"].nunique()
    noise = {
        "runs_per_instance_mean": float(rpi.mean()),
        "runs_per_instance_median": float(rpi.median()),
        "runs_per_instance_p90": float(rpi.quantile(0.90)),
        "runs_per_instance_max": int(rpi.max()),
        "instances_with_both_outcomes": int((mixed == 2).sum()),
        "instances_with_both_outcomes_frac": float((mixed == 2).mean()),
        "note": "temperature-0 API inference flips about 9% of per-instance outcomes on this "
                "corpus, so any within-instance contrast has a ~9% label-flip floor; "
                "runs-per-instance is reported next to every within-instance claim",
    }

    # ---- features ---------------------------------------------------------------------
    fcache = CACHE / f"prefix_features{tag}.parquet"
    mcache = CACHE / f"prefix_meta{tag}.json"
    if fcache.exists() and mcache.exists() and not args.force:
        print("loading cached prefix features")
        allf = pd.read_parquet(fcache)
        tables = {f: allf[allf["_fraction"] == f].drop(columns=["_fraction"]).reset_index(drop=True)
                  for f in FRACTIONS}
        meta = json.loads(mcache.read_text(encoding="utf-8"))
    else:
        tables, meta = prefix_features(steps, FRACTIONS)
        pd.concat([t.assign(_fraction=f) for f, t in tables.items()]).to_parquet(fcache, index=False)
        mcache.write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    print(f"features: {meta['n_runs']} runs; mean prefix length "
          f"{meta['prefix_len_mean']}")

    res: Dict[str, object] = {
        "study": "route_modes (SEARCH vs VERIFY)",
        "generated_by": "scripts/analyse_route_modes.py",
        "protocol": {
            "fractions": list(FRACTIONS),
            "prefix_len": "L = max(1, round(f * n_steps)); features use steps 0..L-1 only",
            "n_steps_in_features": False,
            "folds": "task-disjoint, whole tasks held out",
            "fold_seeds": args.seeds, "n_folds": args.folds,
            "bootstrap": f"{args.n_boot} resamples of whole tasks (clusters = tasks)",
            "alert_budgets": list(BUDGETS),
            "rows": "identical rows and folds for every method",
        },
        "coverage": coverage, "labels": label_block, "noise_floor": noise, "features": meta,
        "tasks": {}, "integrity_checks": {},
    }

    # ---- evaluation -------------------------------------------------------------------
    frames: Dict[str, Dict[float, pd.DataFrame]] = {"y_fail": {}, "y_mode": {}}
    oofs: Dict[str, Dict[float, Dict[str, List[np.ndarray]]]] = {"y_fail": {}, "y_mode": {}}
    for task_name, label_col in (("y_fail", "y_fail"), ("y_mode", "y_wrong_fix")):
        res["tasks"][task_name] = {"label": label_col, "fractions": {}}
        for f in FRACTIONS:
            t = tables[f].merge(labels[["run_id", "y_fail", "y_wrong_fix", "reward", "n_steps",
                                        "n_edit_all"]],
                                on="run_id", how="inner").reset_index(drop=True)
            frames["y_fail"][f] = t
            if task_name == "y_mode":
                tf = t[t["y_fail"] == 1].reset_index(drop=True)
                frames["y_mode"][f] = tf
            else:
                tf = t
            y = tf[label_col].to_numpy(dtype=float)
            if len(np.unique(y)) < 2:
                continue
            o: Dict[str, List[np.ndarray]] = {}
            for seed in range(args.seeds):
                o.setdefault("position", []).append(tf["_prefix_len"].to_numpy(dtype=float))
                o.setdefault("edit_rate_free", []).append(tf["edit_rate"].to_numpy(dtype=float))
                o.setdefault("ngram_loop", []).append(
                    tf["_prefix_mean_flag_ngram"].to_numpy(dtype=float))
                o.setdefault("exact_burst", []).append(
                    tf["_prefix_mean_flag_burst"].to_numpy(dtype=float))
                o.setdefault("tfnorm_novel", []).append(
                    tf["_prefix_mean_flag_tfnorm"].to_numpy(dtype=float))
                o.setdefault("agentstop_shape", []).append(
                    oof_scores(tf, ["_agentstop_outlen", "_agentstop_overlap"], label_col,
                               n_folds=args.folds, seed=seed))
                o.setdefault("own_rates", []).append(
                    oof_scores(tf, RATE_FEATURES, label_col, n_folds=args.folds, seed=seed))
                o.setdefault("own_all", []).append(
                    oof_scores(tf, COUNT_FEATURES, label_col, n_folds=args.folds, seed=seed))
                o.setdefault("own_gbm_rates", []).append(
                    oof_scores(tf, RATE_FEATURES, label_col, n_folds=args.folds, seed=seed,
                               kind="gbm"))
                o.setdefault("own_gbm_all", []).append(
                    oof_scores(tf, COUNT_FEATURES, label_col, n_folds=args.folds, seed=seed,
                               kind="gbm"))
                # the free baseline plus the prefix features: does the feature set add
                # anything at all on top of knowing how long the run has been going?
                o.setdefault("own_rates_plus_position", []).append(
                    oof_scores(tf, RATE_FEATURES + ["_prefix_len"], label_col,
                               n_folds=args.folds, seed=seed))
            oofs[task_name][f] = o
            ev = evaluate_methods(tf, label_col, o, n_boot=args.n_boot)
            ev["mean_prefix_len"] = float(tf["_prefix_len"].mean())
            tbl = sorted(ev["methods"].items(),
                         key=lambda kv: -(kv[1]["auc"] if kv[1]["auc"] == kv[1]["auc"] else -1))
            print(f"\n  {task_name}  f={f}  n={ev['n']}  base rate {ev['base_rate']:.3f}"
                  f"  mean prefix {ev['mean_prefix_len']:.1f}")
            for m, v in tbl:
                d = ev["deltas_primary_vs_baselines"].get(m, {})
                star = "*" if d.get("primary_beats") else " "
                print(f"    {m:<16} AUC {v['auc']:.3f} [{v['auc_ci95'][0]:.3f},{v['auc_ci95'][1]:.3f}]"
                      f" sd {v['auc_sd_over_fold_seeds']:.3f}  "
                      f"r@5% {v['recall_at_budget']['0.05']:.3f}  "
                      f"r@10% {v['recall_at_budget']['0.1']:.3f} {star}")
            # length-matched control: inside one prefix-length band, position is inert
            for L0 in (5, 10, 20):
                sel = (np.abs(tf["_prefix_len"].to_numpy() - L0) < 1e-9)
                if int(sel.sum()) < 400 or len(np.unique(y[sel])) < 2:
                    continue
                sub = tf[sel].reset_index(drop=True)
                sub_o = {m: [oo[sel] for oo in o[m]] for m in ("position", "own_rates", "own_all",
                                                               "agentstop_shape")}
                lm = evaluate_methods(sub, label_col, sub_o, n_boot=200)
                ev.setdefault("length_matched", {})[str(L0)] = lm
                print(f"      length-matched L={L0} (n={len(sub)}): "
                      f"position {lm['methods']['position']['auc']:.3f} "
                      f"own_rates {lm['methods']['own_rates']['auc']:.3f} "
                      f"agentstop {lm['methods']['agentstop_shape']['auc']:.3f}")
            res["tasks"][task_name]["fractions"][str(f)] = ev
    (CACHE / f"progress_eval{tag}.json").write_text(json.dumps(res, indent=2, default=float),
                                                    encoding="utf-8")
    if args.stage in ("labels", "features", "eval"):
        print(f"\nstage={args.stage}: stopping (caches written)")
        return

    # ---- sensitivity: failed runs *that edited something* ------------------------------
    # Runs that never edited anything are LOST by definition, so the mode target is easiest
    # to predict exactly there.  This arm removes them, using the same fitted scores.
    res["y_mode_edited_only"] = {"label": "y_wrong_fix on failed runs with >=1 edit step",
                                "fractions": {}}
    for f in FRACTIONS:
        tf = frames["y_mode"][f]
        sel = (tf["n_edit_all"].to_numpy() > 0) & tf["y_wrong_fix"].notna().to_numpy()
        if int(sel.sum()) < 200 or tf.loc[sel, "y_wrong_fix"].nunique() < 2:
            continue
        sub = tf[sel].reset_index(drop=True)
        sub_o = {m: [oo[sel] for oo in oofs["y_mode"][f][m]] for m in oofs["y_mode"][f]}
        ev = evaluate_methods(sub, "y_wrong_fix", sub_o, n_boot=args.n_boot)
        res["y_mode_edited_only"]["fractions"][str(f)] = ev
        print(f"\n  y_mode_edited_only f={f} n={ev['n']} base rate {ev['base_rate']:.3f}: "
              f"own_rates {ev['methods']['own_rates']['auc']:.3f} "
              f"position {ev['methods']['position']['auc']:.3f} "
              f"agentstop {ev['methods']['agentstop_shape']['auc']:.3f}")
    (CACHE / f"progress_eval{tag}.json").write_text(json.dumps(res, indent=2, default=float),
                                                    encoding="utf-8")

    # ---- within-instance contrast for y_fail (with the runs-per-instance caveat) -------
    t40 = frames["y_fail"][0.40]
    ow = t40.assign(_oof=oofs["y_fail"][0.40]["own_rates"][0])
    wi = []
    for _, g in ow.groupby("task"):
        if g["y_fail"].nunique() < 2 or len(g) < 4:
            continue
        a = _auc(g["y_fail"].to_numpy(dtype=float), g["_oof"].to_numpy(dtype=float))
        if not np.isnan(a):
            wi.append(a)
    res["within_instance"] = {
        "fraction": 0.40, "metric": "per-instance AUC of the prefix failure detector (own_rates)",
        "n_instances_with_both_outcomes": len(wi),
        "mean_auc": float(np.mean(wi)) if wi else float("nan"),
        "frac_above_half": float(np.mean(np.asarray(wi) > 0.5)) if wi else float("nan"),
        "runs_per_instance_mean": noise["runs_per_instance_mean"],
        "noise_floor_note": noise["note"],
    }
    print(f"\nwithin-instance AUC of the failure detector at f=0.40: "
          f"{res['within_instance']['mean_auc']:.3f} over {len(wi)} instances "
          f"(mean {noise['runs_per_instance_mean']:.1f} runs per instance)")

    # ---- calibration ------------------------------------------------------------------
    ccache = CACHE / f"calib{tag}.json"
    if ccache.exists() and not args.force:
        calib = json.loads(ccache.read_text(encoding="utf-8"))
    else:
        calib = {}
        for task_name, label_col in (("y_fail", "y_fail"), ("y_mode", "y_wrong_fix")):
            print(f"\ncalibration for {task_name} ...", flush=True)
            calib[task_name] = calibration_study(tables, labels, FRACTIONS, label_col,
                                                 RATE_FEATURES, n_seeds=args.calib_seeds)
        ccache.write_text(json.dumps(calib, indent=2, default=float), encoding="utf-8")
    res["calibration"] = calib
    for task_name in ("y_fail", "y_mode"):
        for a, v in calib[task_name]["by_alpha"].items():
            s = v["seq_threshold"]
            print(f"  {task_name} alpha={a}: achieved FA {s['false_alarm_rate_mean']:.4f} "
                  f"(max {s['false_alarm_rate_max']:.4f})  detection {s['detection_rate_mean']:.3f}"
                  f"  | e-value rule FA {v['e_value_mean']['false_alarm_rate_mean']:.4f}"
                  f" det {v['e_value_mean']['detection_rate_mean']:.3f}")
    if args.stage == "calib":
        res["calibration"] = calib
        res["runtime_seconds"] = time.time() - t_start
        with open(OUT / "route_modes.json", "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2, default=float)
        print(f"\nstage=calib: stopping after calibration; wrote {OUT / 'route_modes.json'}")
        return

    # ---- null / non-circularity checks -------------------------------------------------
    t60 = frames["y_fail"][0.60]
    t60f = frames["y_mode"][0.60]
    succ_oof = oofs["y_fail"][0.60]["own_rates"][0]
    mode_oof = oofs["y_mode"][0.60]["own_rates"][0]
    succ = t60["y_fail"].to_numpy(dtype=float) == 0
    lost = t60f["y_wrong_fix"].to_numpy(dtype=float) == 0
    cal_rule = res.get("calibration", {}).get("y_fail", {}).get("by_alpha", {}).get("0.05", {})
    res["null_checks"] = {
        "fraction": 0.60,
        "never_failing_runs": int(succ.sum()),
        "never_failing_runs_mean_failure_score": float(np.nanmean(succ_oof[succ])),
        "failing_runs_mean_failure_score": float(np.nanmean(succ_oof[~succ])),
        "raw_0.5_threshold_flag_rate_on_never_failing_runs": float(np.nanmean(succ_oof[succ] > 0.5)),
        "raw_0.5_threshold_flag_rate_on_failing_runs": float(np.nanmean(succ_oof[~succ] > 0.5)),
        "raw_0.5_threshold_verdict": "a raw 0.5 threshold on an uncalibrated logistic score is "
                                     "not a controlled rule -- it is reported here to show why "
                                     "the calibration stage is necessary rather than to claim a "
                                     "false-alarm rate",
        "calibrated_rule_false_alarm_on_never_failing_runs_alpha_0.05": (
            None if not cal_rule else cal_rule["seq_threshold"]["false_alarm_rate_mean"]),
        "lost_runs_n": int(lost.sum()),
        "lost_runs_mean_mode_score": float(np.nanmean(mode_oof[lost])),
        "wrong_fix_runs_mean_mode_score": float(np.nanmean(mode_oof[~lost])),
        "lost_runs_routed_to_verify_raw_0.5": float(np.nanmean(mode_oof[lost] > 0.5)),
        "note": "the controlled claim is the union-bound sequential rule in the calibration "
                "section, whose null is measured on held-out tasks; the withdrawn frozen-study "
                "claim came from scoring a detector against its own statistic, whereas here the "
                "label is the gold patch and every score is prefix-only",
    }
    print(f"\nnull check: raw 0.5 threshold flags "
          f"{res['null_checks']['raw_0.5_threshold_flag_rate_on_never_failing_runs']:.3f} of "
          f"never-failing runs; calibrated rule at alpha=0.05 flags "
          f"{res['null_checks']['calibrated_rule_false_alarm_on_never_failing_runs_alpha_0.05']}")

    # ---- decision curve ---------------------------------------------------------------
    dec: Dict[str, object] = {"conditional_on_failure": {}, "gated_all_runs": {}}
    for f in FRACTIONS:
        tf = frames["y_mode"][f]
        dec["conditional_on_failure"][str(f)] = decision_curve(
            tf, tf["y_wrong_fix"].to_numpy(dtype=float), oofs["y_mode"][f]["own_rates"][0])
        tall = frames["y_fail"][f]
        mask = tall["y_fail"].to_numpy(dtype=float) == 1
        p_mode_full = np.full(len(tall), np.nan)
        p_mode_full[mask] = oofs["y_mode"][f]["own_rates"][0]
        dec["gated_all_runs"][str(f)] = gated_utility(
            tall, oofs["y_fail"][f]["own_rates"][0], p_mode_full, lam=0.25, cost=0.0)
    res["decision_curve"] = dec
    print("\ndecision curve (conditional on failing, lambda=0.25):")
    for f in FRACTIONS:
        d = dec["conditional_on_failure"][str(f)]
        b = d["by_lambda"]["0.25"]
        print(f"  f={f}: detector {b['detector']:.3f} | search {b['always_search']:.3f} | "
              f"verify {b['always_verify']:.3f} | random {b['random_routing']:.3f} "
              f"-> delta {b['delta_vs_best_baseline']:+.3f} "
              f"[{b['delta_ci95'][0]:+.3f},{b['delta_ci95'][1]:+.3f}] "
              f"beats_all={b['beats_all_three']} (acc {d['routing_accuracy']:.3f})")

    res["integrity_checks"] = {
        "label_source": "results/rebuild/gold_patches.parquet (the dataset's own patch field, "
                        "independent of the agent's output)",
        "labels_from_gold_patch": True,
        "no_n_steps_feature": True,
        "no_lookahead": "features read steps 0..L-1 only; --selftest corrupts every later step "
                        "and asserts the features are unchanged",
        "position_is_a_full_run_quantity": "position = prefix length = round(f*n_steps), so it "
                                           "encodes the run's length; reported as the study's "
                                           "baseline and flagged as a leak diagnostic.  The "
                                           "own_rates family excludes it and every other "
                                           "length-carrying column.",
        "count_features_are_length_carrying": "own_all adds raw counts that grow with the "
                                              "prefix; own_rates is the leak-free variant",
    }
    res["runtime_seconds"] = time.time() - t_start
    res["verdict"] = build_verdict(res, FRACTIONS)
    with open(OUT / "route_modes.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'route_modes.json'}  ({res['runtime_seconds']:.0f}s)")
    print(json.dumps(res["verdict"], indent=2, default=float))


def build_verdict(res: Dict[str, object], fractions: Sequence[float]) -> Dict[str, object]:
    out: Dict[str, object] = {"per_task": {}}
    for task_name in ("y_fail", "y_mode"):
        per_f: Dict[str, object] = {}
        for f in fractions:
            ev = res["tasks"].get(task_name, {}).get("fractions", {}).get(str(f))
            if not ev:
                continue
            meth = ev["methods"]
            deltas = ev.get("deltas_primary_vs_baselines", {})
            row = {
                "n": ev["n"], "base_rate": ev["base_rate"],
                "auc": {m: meth[m]["auc"] for m in meth},
                "recall_at_5pct": {m: meth[m]["recall_at_budget"]["0.05"] for m in meth},
                "recall_at_10pct": {m: meth[m]["recall_at_budget"]["0.1"] for m in meth},
                "primary": PRIMARY,
                "beats": {m: deltas[m]["primary_beats"] for m in deltas},
                "delta_vs": {m: deltas[m]["delta"] for m in deltas},
                "delta_ci95_vs": {m: deltas[m]["ci95"] for m in deltas},
            }
            lm = ev.get("length_matched", {})
            row["length_matched_auc"] = {
                L: {m: v["methods"][m]["auc"] for m in v["methods"]} for L, v in lm.items()}
            per_f[str(f)] = row
        out["per_task"][task_name] = per_f
    cal = res.get("calibration", {})
    out["calibration_ok"] = {
        f"{k}@{a}": {
            "alpha": float(a),
            "achieved_false_alarm_seq_rule": v["seq_threshold"]["false_alarm_rate_mean"],
            "achieved_false_alarm_max_over_seed_splits": v["seq_threshold"]["false_alarm_rate_max"],
            "detection": v["seq_threshold"]["detection_rate_mean"],
            "controlled": bool(v["seq_threshold"]["false_alarm_rate_mean"] <= float(a)),
            "e_value_rule_false_alarm": v["e_value_mean"]["false_alarm_rate_mean"],
            "e_value_rule_detection": v["e_value_mean"]["detection_rate_mean"],
        }
        for k, vv in cal.items() for a, v in vv.get("by_alpha", {}).items()
    }
    dec = res.get("decision_curve", {}).get("conditional_on_failure", {})
    out["decision_beats_all_baselines"] = {
        f: {lam: v["by_lambda"][lam]["beats_all_three"] for lam in v["by_lambda"]}
        for f, v in dec.items()}
    out["gated_beats_all_baselines"] = {
        f: v.get("beats_all_three") for f, v in res.get("decision_curve", {})
        .get("gated_all_runs", {}).items()}
    out["published_bar"] = {
        "agentstop_published_auc_range": [0.6, 0.7],
        "note": "agentstop_shape is refitted here on identical rows and folds; the published "
                "range is not strictly comparable because the deployed system uses model "
                "logprobs, which this corpus does not carry",
    }
    return out


def selftest() -> None:
    """Mechanical check: nothing after the cutoff may influence a feature.

    For each fraction the rows at *and after* the cutoff are overwritten with garbage and
    the features are re-derived; every feature column must be unchanged.
    """
    print("selftest: corrupting every step at or after each cutoff and re-deriving features")
    steps, gold = load_inputs(limit=1200)
    nst = steps["n_steps"].to_numpy()
    pos = steps.groupby("run_id").cumcount().to_numpy()
    fractions = (0.10, 0.40)
    base_tables, _ = prefix_features(steps, fractions)
    bad_cols = []
    n_cols = 0
    for f in fractions:
        L = np.clip(np.round(f * nst).astype(int), 1, nst)   # prefix length, 0-based
        m = pos >= L
        print(f"  f={f}: corrupting {int(m.sum())} of {len(steps)} steps")
        bad = steps.copy()
        bad.loc[m, "obs_chars"] = 123456
        bad.loc[m, "text_chars"] = 654321
        bad.loc[m, "sig"] = "CORRUPTED"
        bad.loc[m, "is_edit"] = 1
        bad.loc[m, "is_read"] = 1
        bad.loc[m, "is_search"] = 1
        bad.loc[m, "is_run"] = 1
        bad.loc[m, "is_test"] = 1
        bad.loc[m, "is_finish"] = 1
        bad.loc[m, "added_lines_n"] = 0
        bad.loc[m, "file_shown"] = "/corrupt/nope.py"
        bad.loc[m, "st_failed"] = 99
        bad.loc[m, "st_passed"] = 99
        bad.loc[m, "st_error"] = 99
        bad.loc[m, "st_tb"] = 99
        bad.loc[m, "targets_str"] = "zzz zzz zzz"
        bad.loc[m, "st_sig"] = "CORRUPTED"
        bad.loc[m, "verb"] = "edit"
        bad.loc[m, "cmd_family"] = "edit"
        new_tables, _ = prefix_features(bad, [f])
        merged = base_tables[f].merge(new_tables[f], on=["run_id", "task", "model"],
                                      suffixes=("_a", "_b"))
        for c in base_tables[f].columns:
            if c in ("run_id", "task", "model"):
                continue
            n_cols += 1
            a = merged[f"{c}_a"].to_numpy(dtype=float)
            b = merged[f"{c}_b"].to_numpy(dtype=float)
            if not np.allclose(a, b, equal_nan=True, rtol=1e-12, atol=1e-12):
                bad_cols.append((f, c, int(np.sum(~np.isclose(a, b, equal_nan=True)))))
    print("  feature columns checked:", n_cols)
    print("  columns changed by post-cutoff corruption:", bad_cols if bad_cols else "none")
    assert not bad_cols, f"LOOKAHEAD LEAK: {bad_cols}"
    print("  PASS: no feature depends on any step at or after the cutoff")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
