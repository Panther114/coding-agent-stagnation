"""Route: a runnable demo of the runtime router.

The router answers one question a runtime system actually has to act on: when a coding agent is
struggling, is it LOST (it has not found the code that needs changing) or is it WRONG-FIX (it found
the right code and its change does not work)?  The answer decides what to do -- help it search, or
make it verify -- and the published stagnation/loop detectors cannot tell the two apart at all
(they score at or below chance on that question, while this router scores 0.68-0.77).

Usage
-----
    python demo/route.py --fit                 # train on shards 0-3, cache the model
    python demo/route.py --summary             # router vs baselines on HELD-OUT shards
    python demo/route.py --list                # list held-out runs to replay
    python demo/route.py --replay <run_id>     # step through one held-out run, turn by turn
    python demo/route.py --live <episodes.jsonl>   # route episodes from the live harness

Everything is offline and deterministic.  Labels come from the dataset's own gold patch, never from
the agent's output; features read only the prefix of the run, so nothing here looks ahead.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import pickle
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@contextlib.contextmanager
def quiet():
    """Silence the analysis module's per-run progress prints so the demo output stays readable."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_spec = importlib.util.spec_from_file_location(
    "route_modes", ROOT / "research" / "scripts" / "analyse_route_modes.py")
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)

RES = ROOT / "research" / "results" / "rebuild"
CACHE = ROOT / "demo" / "_cache"
CACHE.mkdir(parents=True, exist_ok=True)

FRAC = 0.20  # the deployed setting: decide after 20% of the run
SETS = {
    "train_A_shards0_3": (ROOT / "research" / "data" / "processed" / "steps", "gold_patches.parquet"),
    "heldout_B_shards4_7": (ROOT / "research" / "data" / "processed" / "steps_repl",
                            "gold_patches_repl.parquet"),
    "heldout_C_shards8_11": (ROOT / "research" / "data" / "processed" / "steps_repl2",
                             "gold_patches_repl2.parquet"),
}


def build(name: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    root, goldfile = SETS[name]
    gold_df = pd.read_parquet(RES / goldfile)
    gold = {str(k): set(v) for k, v in zip(gold_df["instance_id"], gold_df["gold_basenames"])}
    steps = pd.read_parquet(root / "nebius" / "steps.parquet", columns=arm.STEP_COLS)
    steps = steps[steps["task"].isin(gold)].copy()
    labels = arm.build_labels(steps, gold)
    with quiet():
        tables, _ = arm.prefix_features(steps, [FRAC])
    t = tables[FRAC].merge(labels[["run_id", "y_fail", "y_wrong_fix", "reward", "n_steps",
                                   "ever_touched_gold"]], on="run_id", how="inner")
    return t, labels


def fit() -> Dict[str, object]:
    """Fit the two heads on the training shards and cache them."""
    from sklearn.linear_model import LogisticRegression
    print("fitting on shards 0-3 ...", flush=True)
    tr, _ = build("train_A_shards0_3")
    cols = [c for c in arm.RATE_FEATURES if c in tr.columns]
    models = {}
    for ycol in ("y_fail", "y_wrong_fix"):
        d = tr[np.isfinite(tr[ycol].to_numpy(dtype=float))]
        X = arm._clean(d[cols].to_numpy())
        y = d[ycol].to_numpy(dtype=float)
        mu, sd = X.mean(axis=0), np.where(X.std(axis=0) < 1e-9, 1.0, X.std(axis=0))
        m = LogisticRegression(max_iter=3000, C=1.0, solver="lbfgs", random_state=0)
        m.fit((X - mu) / sd, y)
        models[ycol] = {"coef": m.coef_.ravel(), "intercept": float(m.intercept_[0]),
                        "mu": mu, "sd": sd, "n_train": int(len(d)),
                        "base_rate": float(y.mean())}
        print(f"  {ycol}: fitted on {len(d):,} runs, base rate {y.mean():.3f}")
    blob = {"cols": cols, "models": models, "fraction": FRAC}
    (CACHE / "router.pkl").write_bytes(pickle.dumps(blob))
    print(f"cached -> {CACHE / 'router.pkl'}")
    return blob


def load_model() -> Dict[str, object]:
    p = CACHE / "router.pkl"
    if not p.exists():
        return fit()
    return pickle.loads(p.read_bytes())


def score(blob, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    cols = blob["cols"]
    X = arm._clean(df[cols].to_numpy())
    out = {}
    for ycol, m in blob["models"].items():
        out[ycol] = 1.0 / (1.0 + np.exp(-(((X - m["mu"]) / m["sd"]) @ m["coef"] + m["intercept"])))
    return out["y_fail"], out["y_wrong_fix"]


def decide(p_fail: float, p_wrong: float, thresh: float = 0.5) -> str:
    if p_fail < thresh:
        return "no intervention (on track)"
    return "VERIFY (it is in the right place, make it check its fix)" if p_wrong >= 0.5 else \
           "SEARCH (it has not found the code yet -- supply a location hint)"


def cmd_summary(blob) -> None:
    print(f"\nrouter performance at {FRAC:.0%} of the run, trained on shards 0-3\n")
    for nm in SETS:
        if not nm.startswith("heldout"):
            continue
        t, _ = build(nm)
        pf, pw = score(blob, t)
        out = {}
        for ycol in ("y_fail", "y_wrong_fix"):
            d = t[np.isfinite(t[ycol].to_numpy(dtype=float))]
            idx = t.index[np.isfinite(t[ycol].to_numpy(dtype=float))]
            s = pf if ycol == "y_fail" else pw
            pos = np.isin(t.index, idx)
            y = t.loc[pos, ycol].to_numpy(dtype=float)
            out[ycol] = arm._auc(y, s[pos])
        print(f"  {nm:22s} n={len(t):>6,}  y_fail AUC={out['y_fail']:.3f}  "
              f"lost-vs-wrongfix AUC={out['y_wrong_fix']:.3f}")
    print("\n  published detector families on the same rows score 0.55-0.61 (failure) and "
          "at or below chance (mode); see results/rebuild/route_modes.json")


def cmd_list(blob, n: int = 20) -> None:
    t, _ = build("heldout_B_shards4_7")
    d = t[np.isfinite(t["y_wrong_fix"].to_numpy(dtype=float))]
    d = d.sample(n=min(n, len(d)), random_state=0)
    print(f"\n{len(d)} held-out runs (y=1 means WRONG-FIX, y=0 means LOST):\n")
    for r in d.itertuples(index=False):
        print(f"  {r.run_id[:56]:56s} reward={r.reward} mode={int(r.y_wrong_fix)} "
              f"steps={r.n_steps}")
    print("\n  replay one with:  python demo/route.py --replay <run_id>")


def cmd_replay(blob, run_id: str) -> None:
    root, goldfile = SETS["heldout_B_shards4_7"]
    gold_df = pd.read_parquet(RES / goldfile)
    gold = {str(k): set(v) for k, v in zip(gold_df["instance_id"], gold_df["gold_basenames"])}
    steps = pd.read_parquet(root / "nebius" / "steps.parquet", columns=arm.STEP_COLS)
    steps = steps[steps["task"].isin(gold)].copy()
    labels = arm.build_labels(steps, gold)
    match = labels[labels["run_id"].astype(str).str.startswith(run_id)]
    if not len(match):
        print(f"no held-out run matching {run_id!r}; try --list")
        return
    rid = str(match.iloc[0]["run_id"])
    one = steps[steps["run_id"].astype(str) == rid]
    print(f"\n=== replaying held-out run {rid[:60]} ===")
    print(f"    {int(match.iloc[0]['n_steps'])} steps total; router decides at "
          f"{FRAC:.0%} = step {int(round(FRAC*int(match.iloc[0]['n_steps'])))}")
    for f in (0.10, 0.20, 0.40, 0.60):
        with quiet():
            tabs, _ = arm.prefix_features(one, [f])
        t = tabs[f].merge(labels[["run_id", "y_fail", "y_wrong_fix"]], on="run_id", how="inner")
        if not len(t):
            continue
        pf, pw = score(blob, t)
        print(f"\n  at {f:>4.0%} of the run:")
        print(f"      P(fail) = {pf[0]:.3f}   P(wrong-fix | this is a failing run) = {pw[0]:.3f}")
        print(f"      -> {decide(pf[0], pw[0])}")
    truth_fail = int(match.iloc[0]["y_fail"])
    truth_mode = match.iloc[0]["y_wrong_fix"]
    got = "SOLVED" if truth_fail == 0 else ("WRONG-FIX" if truth_mode == 1 else "LOST")
    print(f"\n  ground truth: reward={int(match.iloc[0]['reward'])} -> {got}")


def cmd_live(blob, path: Path) -> None:
    if not path.exists():
        print(f"no such file: {path}")
        return
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"\nrouting {len(recs)} live episodes from {path.name}\n")
    ok = 0
    for r in recs[:20]:
        n = r.get("n_turns") or 0
        if not n:
            continue
        print(f"  {str(r['task_id'])[:44]:44s} arm={str(r.get('arm')):8s} "
              f"turns={n:>3} success={r.get('success')} "
              f"reached_gold={r.get('reached_gold')} "
              f"test_tamper={r.get('test_files_removed', 0)}")
        ok += 1
    print(f"\n  (live traces store turns, not per-step feature rows, so this view reports the "
          f"observable outcome signals the router is built from; see demo/README.md)")


def main() -> None:
    ap = argparse.ArgumentParser(description="runtime router demo")
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--replay", default=None)
    ap.add_argument("--live", default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if args.fit:
        fit()
        return
    blob = load_model()
    if args.summary:
        cmd_summary(blob)
    elif args.list:
        cmd_list(blob)
    elif args.replay:
        cmd_replay(blob, args.replay)
    elif args.live:
        cmd_live(blob, Path(args.live))
    else:
        ap.print_help()
        print("\nstart with:  python demo/route.py --fit && python demo/route.py --summary")


if __name__ == "__main__":
    main()
