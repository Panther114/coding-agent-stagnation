"""Stability of the channel-ablation numbers (§2.27).

The ablation changed a headline, so the numbers it produced have to be shown to be
stable rather than artefacts of one learner, one fold seed, or one feature form.
Re-runs every channel and the union under:

  learner   logistic (L2, standardised)  /  HistGradientBoosting
  seed      3 task-disjoint fold partitions
  form      raw features  /  within-task z-scored features (level-free)

and reports mean and sd per channel, plus the fraction of the (learner, seed, form)
grid on which each channel beats the position baseline by more than its own sd.

Nothing is refit on the outcome; folds are task-disjoint throughout.
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
PREFIX = {"REP": "rep_", "MIX": "mix_", "NOV": "nov_", "WS": "ws_", "VER": "ver_"}
EXPLICIT = {"POS": ["relpos", "frac_done", "_elapsed"]}
N_FOLDS = 10
SEEDS = [0, 1, 2]
LEARNERS = ["logit", "gbm"]
FORMS = ["raw", "ztask"]


def fold_ids(tasks: np.ndarray, seed: int) -> np.ndarray:
    uniq = np.array(sorted(set(tasks)))
    perm = np.random.RandomState(seed).permutation(len(uniq))
    assign = {t: perm[i] % N_FOLDS for i, t in enumerate(uniq)}
    return np.array([assign[t] for t in tasks])


def ztask(X: np.ndarray, tasks: np.ndarray) -> np.ndarray:
    out = np.empty_like(X)
    for t in np.unique(tasks):
        m = tasks == t
        mu = np.nanmean(X[m], axis=0)
        sd = np.nanstd(X[m], axis=0)
        sd[sd == 0] = 1.0
        out[m] = (X[m] - mu) / sd
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def make(learner: str):
    if learner == "gbm":
        from sklearn.ensemble import HistGradientBoostingClassifier
        return HistGradientBoostingClassifier(
            max_iter=120, learning_rate=0.08, max_depth=4, random_state=0
        )
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(LogisticRegression(max_iter=2000, C=1.0))


def cv_auc(X: np.ndarray, y: np.ndarray, folds: np.ndarray, learner: str) -> float:
    oof = np.full(len(y), np.nan)
    for f in range(N_FOLDS):
        te, tr = folds == f, folds != f
        if te.sum() == 0 or len(set(y[tr])) < 2:
            continue
        m = make(learner)
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
    tasks = df["task"].to_numpy()

    chans = dict(EXPLICIT)
    for n, p in PREFIX.items():
        chans[n] = [c for c in df.columns if c.startswith(p)]
    cols = {n: [c for c in v if c in df.columns] for n, v in chans.items()}
    cols["ALL"] = [c for n in ("POS", "REP", "MIX", "NOV", "WS", "VER") for c in cols[n]]

    grids = {}
    for name, present in cols.items():
        X0 = np.nan_to_num(df[present].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
        vals = []
        for form in FORMS:
            X = X0 if form == "raw" else ztask(X0, tasks)
            for seed in SEEDS:
                folds = fold_ids(tasks, seed)
                for learner in LEARNERS:
                    a = cv_auc(X, y, folds, learner)
                    vals.append(a)
                    print(f"  {name:4s} {form:5s} seed{seed} {learner:5s} AUC={a:.3f}",
                          flush=True)
        grids[name] = vals

    pos = np.array(grids["POS"])
    res = {
        "rows": int(len(df)), "base_rate": float(y.mean()),
        "n_folds": N_FOLDS, "seeds": SEEDS, "learners": LEARNERS, "forms": FORMS,
        "grid_size": len(SEEDS) * len(LEARNERS) * len(FORMS),
        "note": "every cell is task-disjoint 10-fold CV on y_wasted; nothing sees the outcome",
        "channels": {},
    }
    for name, vals in grids.items():
        v = np.array(vals)
        res["channels"][name] = {
            "mean": float(np.nanmean(v)), "sd": float(np.nanstd(v)),
            "min": float(np.nanmin(v)), "max": float(np.nanmax(v)),
        }
    # does each channel beat position across the grid?
    for name, vals in grids.items():
        if name == "POS":
            continue
        d = np.array(vals) - pos
        res["channels"][name]["frac_beats_pos"] = float(np.mean(d > 0))
        res["channels"][name]["mean_gain_over_pos"] = float(np.nanmean(d))
        res["channels"][name]["gain_sd"] = float(np.nanstd(d))
    res["pos_range"] = [float(pos.min()), float(pos.max())]

    print("\nchannel | mean | sd | min..max | gain over POS | frac(grid) gain>0")
    for n, c in res["channels"].items():
        g = c.get("mean_gain_over_pos", float("nan"))
        f = c.get("frac_beats_pos", float("nan"))
        print(f"  {n:4s} | {c['mean']:.3f} | {c['sd']:.3f} | "
              f"{c['min']:.3f}..{c['max']:.3f} | {g:+.3f} | {f:.2f}")

    allc = res["channels"]["ALL"]
    verc = res["channels"]["VER"]
    novc = res["channels"]["NOV"]
    res["verdict"] = (
        f"ALL = {allc['mean']:.3f} +/- {allc['sd']:.3f} (range "
        f"{allc['min']:.3f}-{allc['max']:.3f}); POS = {np.nanmean(pos):.3f} "
        f"(range {res['pos_range'][0]:.3f}-{res['pos_range'][1]:.3f}); "
        f"VER gain {verc['mean_gain_over_pos']:+.3f} (beats POS in "
        f"{verc['frac_beats_pos']:.2f} of grid cells); NOV gain "
        f"{novc['mean_gain_over_pos']:+.3f} (beats POS in {novc['frac_beats_pos']:.2f})."
    )
    print("\n" + res["verdict"])

    (RES / "channel_ablation_stability.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nwrote {RES / 'channel_ablation_stability.json'}")


if __name__ == "__main__":
    main()
