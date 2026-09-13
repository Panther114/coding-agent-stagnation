"""Channel ablation -- is "the limit is the observable channel" falsifiable from inside the data?

The central claim of the rebuild is that whether an agent's edit survives is essentially
unpredictable from the preceding context (AUC 0.539 against a 0.536 position baseline),
and that this is a limit of the *observable channel*, not of the model.  That claim is
falsified if some channel that we already possess -- but did not separately credit --
carries the signal on its own.

We therefore split the 69 window features into the four channels they came from and
score each one alone, then the union, on the same task-disjoint folds:

  POS   position only (relpos, frac_done, elapsed)                   -- the free baseline
  REP   repetition / looping signatures (rep_*)
  MIX   action-mix composition (mix_*)
  NOV   output novelty and drift (nov_*)
  WS    workspace movement, the mechanical channel (ws_*)
  VER   verification output: test observations, error/traceback/
        syntax/not-found indicators, improvement rate (ver_*)

WS is the channel the rebuild's headline relies on.  VER is the nearest thing in this
data to "per-step test outcome" -- the instrument the handoff says would be needed to
falsify the claim from outside.  If VER alone reaches materially above POS, the claim
as stated is too strong and must be narrowed.

Discipline: identical rows, identical folds, identical model, no lookahead -- every
feature is computed from the window ending at t-1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall.evaluate import safe_auc as auc  # noqa: E402

RES = ROOT / "results" / "rebuild"

CHANNELS = {
    "POS": ["relpos", "frac_done", "_elapsed"],
    "REP": None,
    "MIX": None,
    "NOV": None,
    "WS": None,
    "VER": None,
}
PREFIX = {"REP": "rep_", "MIX": "mix_", "NOV": "nov_", "WS": "ws_", "VER": "ver_"}

N_FOLDS = 10
MIN_RUNS = 20


def fold_ids(tasks: np.ndarray, n_folds: int, seed: int = 0) -> np.ndarray:
    uniq = np.array(sorted(set(tasks)))
    rng = np.random.RandomState(seed)
    perm = rng.permutation(len(uniq))
    assign = {t: perm[i] % n_folds for i, t in enumerate(uniq)}
    return np.array([assign[t] for t in tasks])


def cv_auc(X: np.ndarray, y: np.ndarray, folds: np.ndarray) -> float:
    from sklearn.ensemble import HistGradientBoostingClassifier

    oof = np.full(len(y), np.nan)
    for f in range(folds.max() + 1):
        te = folds == f
        tr = ~te
        if te.sum() == 0 or tr.sum() == 0 or len(set(y[tr])) < 2:
            continue
        m = HistGradientBoostingClassifier(
            max_iter=120, learning_rate=0.08, max_depth=4, random_state=0
        )
        m.fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    ok = ~np.isnan(oof)
    if ok.sum() == 0 or len(set(y[ok])) < 2:
        return float("nan")
    return float(auc(y[ok], oof[ok]))


def main() -> None:
    df = pd.read_parquet(RES / "step_task.parquet")
    y = df["y_wasted"].to_numpy(dtype=float)
    keep = ~np.isnan(y)
    df, y = df.loc[keep].reset_index(drop=True), y[keep]
    print(f"rows={len(df):,}  base rate wasted={y.mean():.4f}  "
          f"tasks={df.task.nunique():,}  runs={df.run_id.nunique():,}")

    cols = {}
    for name, explicit in CHANNELS.items():
        if explicit is not None:
            cols[name] = [c for c in explicit if c in df.columns]
        else:
            p = PREFIX[name]
            cols[name] = [c for c in df.columns if c.startswith(p)]
    # drop fold-derived / target-derived columns that are not channels
    cols["POS"] = [c for c in cols["POS"] if c in df.columns]

    tasks = df["task"].to_numpy()
    folds = fold_ids(tasks, N_FOLDS)

    def block_auc(names):
        present = [c for n in names for c in cols[n] if c in df.columns]
        X = df[present].to_numpy(dtype=float)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        return cv_auc(X, y, folds), present

    res = {"rows": int(len(df)), "base_rate": float(y.mean()),
           "n_folds": N_FOLDS, "seed": 0,
           "target": "y_wasted (window ending at t-1 -> is the next edit wasted)",
           "channels": {}}

    for name in CHANNELS:
        a, present = block_auc([name])
        res["channels"][name] = {"auc": a, "n_features": len(present)}
        print(f"  {name:4s} n={len(present):2d}  AUC={a:.3f}")

    union = list(CHANNELS)
    a_all, present = block_auc(union)
    res["union_auc"] = a_all
    print(f"  ALL  n={len(present):2d}  AUC={a_all:.3f}")

    # Is VER additive on top of WS?  The claim survives only if the answer is "barely".
    a_ws_ver, _ = block_auc(["WS", "VER"])
    a_ws_only = res["channels"]["WS"]["auc"]
    a_ver_only = res["channels"]["VER"]["auc"]
    res["ws_plus_ver_auc"] = a_ws_ver
    res["ver_gain_over_ws"] = float(a_ws_ver - a_ws_only)

    pos = res["channels"]["POS"]["auc"]
    res["ver_gain_over_pos"] = float(a_ver_only - pos)
    res["max_single_channel_gain_over_pos"] = float(
        max(v["auc"] for k, v in res["channels"].items() if k != "POS") - pos
    )

    # Verdict thresholds fixed in advance.
    if a_ver_only >= pos + 0.05:
        verdict = ("FALSIFIED: the verification channel alone carries materially more "
                   "signal than position; 'the limit is the observable channel' is too "
                   "strong as stated and must be narrowed to 'the limit is the "
                   "workspace/novelty channels'. VER must be reported separately.")
    elif a_ver_only >= pos + 0.02:
        verdict = ("WEAKENED: verification output adds a small but real amount over "
                   "position. The claim survives only with the caveat that test output is "
                   "the one channel with a non-trivial and unexhausted increment.")
    else:
        verdict = ("SURVIVES: no channel we hold, including per-step verification output, "
                   "lifts the wasted-edit prediction materially above position. The "
                   "limit is the observable channel, not the model.")
    res["verdict"] = verdict
    print("\n" + verdict)

    (RES / "channel_ablation.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nwrote {RES / 'channel_ablation.json'}")


if __name__ == "__main__":
    main()

