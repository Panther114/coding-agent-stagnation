"""Objective progress targets, mined from the corpora rather than judged.

The first version of the study labelled progress with human-written codebooks applied
by LLM readers (kappa = 0.70), and its most serious limitation is that the labels are
judgements.  A rebuild searched for an objective replacement and concluded that
"this release contains no dense objective progress signal to predict" -- true for
Terminal-Bench, whose release ships a single final reward.

Both corpora on disk contain more than that.  This module turns the observable record
into targets that no one has to judge:

Run level (both corpora)
    ``success``            the task's own oracle: TB2 ``reward``, or SWE-bench
                           ``target`` (tests from the linked PR applied to the patch).

Step level (editor telemetry, 96% of edit steps in the Nebius corpus)
    ``ws_delta[i]``        change in the shown file's total line count at step i.
                           Non-zero means the workspace objectively changed.
    ``noop_edit[i]``       an edit step whose file size did not change: the agent asked
                           for a change and the repository did not move.  This is the
                           closest thing to a mechanical definition of wasted work.

Window level (the unit a runtime would act on)
    ``stagnation``         share of steps in the window with no workspace change, no
                           new entity and no verification-state change.
    ``waste``              share of *measurable edit* steps in the window that were
                           no-ops.
    ``loop``               share of the window's steps whose action repeats one already
                           run earlier in the same run.
    ``forward_fail``       the run does not succeed, used only as a *predictive* target
                           to ask whether a window carries information about the future.

Every function here is explicit about whether it is a feature or a target; targets are
only ever read by evaluation code, and ``run_tests.py`` asserts that no target column
reaches a feature matrix.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

TARGET_COLUMNS = ("y_stagnation", "y_waste", "y_loop", "y_nochange", "y_forward_fail",
                  "y_reward", "y_ws_delta_absent")


def step_level_objective(rv) -> Dict[str, np.ndarray]:
    """Mechanical per-step verdicts, computed from the run's own observables only.

    No future information: every quantity at step ``i`` uses steps ``< i``.
    """
    n = rv.n
    delta = np.full(n, np.nan)
    noop = np.zeros(n, dtype=np.float64)
    changed = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if rv.file_total[i] >= 0 and i > 0 and rv.file_total[i - 1] >= 0 \
                and rv.file_shown[i] and rv.file_shown[i] == rv.file_shown[i - 1]:
            d = rv.file_total[i] - rv.file_total[i - 1]
            delta[i] = d
            changed[i] = 1.0 if d != 0 else 0.0
            if rv.is_edit[i] and d == 0:
                noop[i] = 1.0
    return {"ws_delta": delta, "ws_changed": changed, "noop_edit": noop}


def novelty_flags(rv) -> np.ndarray:
    """1 where step i mentions an entity never mentioned earlier in the run."""
    seen = set()
    out = np.zeros(rv.n, dtype=np.float64)
    for i, events in enumerate(rv.ent_text):
        c = 0
        for kind, val, _chars in events:
            k = kind + "|" + val
            if k not in seen:
                seen.add(k)
                c += 1
        out[i] = 1.0 if c > 0 else 0.0
    return out


def repeated_action_flags(rv) -> np.ndarray:
    seen = set()
    out = np.zeros(rv.n, dtype=np.float64)
    for i, s in enumerate(rv.sig):
        if s in seen:
            out[i] = 1.0
        seen.add(s)
    return out


def window_targets(rv, t: int, w: int, obj: Dict[str, np.ndarray],
                   novel: np.ndarray, repeated: np.ndarray) -> Dict[str, float]:
    """Retrospective targets describing the window [t-w+1, t].

    Kept for comparability with the first version's window-level labels, but note the
    circularity that this formulation creates: the target is computed from exactly the
    steps the features describe, so a feature that counts "did anything change in these
    steps" predicts it almost tautologically.  The *predictive* targets (``future_*``,
    below) are the ones an online monitor actually has to earn.
    """
    return _range_targets(rv, max(0, t - w + 1), t, obj, novel, repeated)


def future_targets(rv, t: int, w: int, obj: Dict[str, np.ndarray],
                   novel: np.ndarray, repeated: np.ndarray) -> Optional[Dict[str, float]]:
    """Targets for the window that *follows* the features: [t+1, t+w].

    This is the honest online question.  A runtime at step ``t`` knows the trajectory so
    far; it must say whether the agent is about to stop making progress.  Features come
    from steps ``<= t``, the target from steps ``> t``, so no quantity appears on both
    sides.  Returns ``None`` when the run ends before the future window is complete.
    """
    if t + w > rv.n - 1:
        return None
    out = _range_targets(rv, t + 1, t + w, obj, novel, repeated)
    return out


def _range_targets(rv, lo: int, hi: int, obj: Dict[str, np.ndarray],
                   novel: np.ndarray, repeated: np.ndarray) -> Dict[str, float]:
    m = hi - lo + 1
    if m <= 0:
        return {}
    sl = slice(lo, hi + 1)
    changed = obj["ws_changed"][sl]
    measurable = ~np.isnan(obj["ws_delta"][sl])
    noop = obj["noop_edit"][sl]
    edit = rv.is_edit[sl]
    edit_meas = edit * measurable

    sig_change = np.zeros(m, dtype=np.float64)
    for j, i in enumerate(range(lo, hi + 1)):
        if i > 0 and rv.st_sig[i] != rv.st_sig[i - 1]:
            sig_change[j] = 1.0
    event = np.maximum.reduce([changed, novel[sl], sig_change])
    out: Dict[str, float] = {}
    out["y_nochange"] = 1.0 - float(event.mean())
    out["y_stagnation"] = out["y_nochange"]
    n_edit_meas = float(edit_meas.sum())
    out["y_waste"] = float((noop * edit_meas).sum() / n_edit_meas) if n_edit_meas else np.nan
    out["y_waste_n"] = n_edit_meas
    out["y_loop"] = float(repeated[sl].mean())
    out["y_edit_frac"] = float(edit.mean())
    out["y_ws_measurable_frac"] = float(measurable.mean())
    out["y_forward_fail"] = 1.0 - float(rv.reward)
    out["y_reward"] = float(rv.reward)
    return out


def run_level_targets(rv) -> Dict[str, float]:
    obj = step_level_objective(rv)
    novel = novelty_flags(rv)
    repeated = repeated_action_flags(rv)
    delta = obj["ws_delta"]
    measurable = ~np.isnan(delta)
    return {
        "reward": float(rv.reward),
        "n_steps": float(rv.n),
        "n_edit": float(rv.is_edit.sum()),
        "n_test": float(rv.is_test.sum()),
        "n_novel_steps": float((novel > 0).sum()),
        "novel_step_frac": float(novel.mean()),
        "n_repeat_steps": float((repeated > 0).sum()),
        "repeat_step_frac": float(repeated.mean()),
        "n_measured_deltas": float(measurable.sum()),
        "measured_frac": float(measurable.mean()),
        "n_noop_edits": float(obj["noop_edit"].sum()),
        "noop_edit_frac_of_steps": float(obj["noop_edit"].sum() / max(1.0, rv.n)),
        "ws_change_frac": float(obj["ws_changed"][measurable].mean()) if measurable.any() else np.nan,
        "net_size_delta": float(np.nansum(delta)),
        "abs_size_delta": float(np.nansum(np.abs(delta))),
    }
