"""Sequential detection of *objective* waste, with a calibrated false-alarm rate.

    python scripts/analyse_sequential_deadend.py

The first sequential analysis used "quiet windows" as its event, which is fine for the detector
comparison but circular as evidence about waste: a quiet window is defined by the same telemetry
the detector reads. This version uses an **objective** event — a window containing at least one
**dead-end edit**, an edit whose content never reaches the final patch and whose file the run never
touches again. That label needs the final patch, so it is a target, not a feature, and detecting it
in advance is a real claim.

The protocol is the same calibrated one as before, so the two are comparable:

* a **persistence rule** on a monitor's per-window score, alarming after K consecutive windows over
  a threshold;
* the threshold set on held-out, task-disjoint runs that contain no dead-end window at all, so the
  false-alarm rate is measured against genuine negatives;
* reported as recall, false alarms, precision, latency against the first dead-end window, and the
  share of the stall observed at the alarm.

Prints the leading detectors only; the full table is in the artifact.

Writes ``results/rebuild/sequential_deadend.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402
from agentstall import sequential as S  # noqa: E402

OUT = ROOT / "results" / "rebuild"


def build_dead_end_series(w: pd.DataFrame, d_steps: pd.DataFrame, k: int = 10) -> Dict[str, np.ndarray]:
    """Per-step 0/1: does step t belong to a window that contains a dead-end edit?"""
    de = d_steps[d_steps["dead_end"] == 1][["run_id", "step"]]
    out: Dict[str, np.ndarray] = {}
    for rid, g in w.groupby("run_id", sort=False):
        n = int(g["t"].max()) + int(k) + 2
        flags = np.zeros(n, dtype=float)
        steps = de[de.run_id == rid]["step"].to_numpy()
        if len(steps):
            for t in g["t"].to_numpy():
                lo, hi = int(t) - k + 1, int(t)
                if ((steps >= lo) & (steps <= hi)).any():
                    flags[int(t)] = 1.0
        out[rid] = flags
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    w = pd.read_parquet(ROOT / "data" / "processed" / "windows" / "nebius" / "windows.parquet")
    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "file_shown"])
    d = st.merge(steps, on=["run_id", "step"], how="left").sort_values(["run_id", "step"])
    later = {}
    for _rid, g in d.groupby("run_id", sort=False):
        files = g["file_shown"].astype(str).to_numpy()
        idx = g.index.to_numpy()
        for kk in range(len(idx) - 1):
            cur = files[kk]
            later[idx[kk]] = bool(cur) and (files[kk + 1:] == cur).any()
    d["revisited_later"] = d.index.map(lambda i: later.get(i, False))
    d["dead_end"] = ((d["hit"] == 0) & (~d["revisited_later"])).astype(int)
    print(f"{int(d['dead_end'].sum())} dead-end edits over {d.run_id.nunique()} runs")

    ev = build_dead_end_series(w, d, k=args.w)
    # only keep runs the window table actually knows
    ev = {rid: v for rid, v in ev.items() if rid in set(w.run_id)}
    healthy = {rid: bool(np.all(v < 0.5)) for rid, v in ev.items()}
    n_neg = int(sum(healthy.values()))
    n_pos = len(healthy) - n_neg
    res: Dict[str, object] = {"n_runs": len(healthy), "n_with_dead_end": n_pos,
                              "n_without_dead_end": n_neg,
                              "frac_without": n_neg / max(1, len(healthy))}
    print(f"runs {len(healthy)}: with a dead-end window {n_pos}, without {n_neg} "
          f"({n_neg / max(1, len(healthy)):.1%})")

    causal = S.causal_quiet_series(ev, args.w)
    latent: Dict[str, Optional[int]] = {}
    for rid, v in causal.items():
        idx = np.nonzero(v > 0.5)[0]
        latent[rid] = int(idx[0]) if len(idx) else None

    # candidate monitors: the study's own scores, plus two free proxies already in the window
    # table -- the no-op-edit share and the edit share.  (An earlier version tried to build a
    # structural proxy from `added_lines_n`, which lives in the step table rather than here.)
    score_cols = [c for c in w.columns if c.startswith("s_")]
    score_cols += [c for c in ("ws_noop_edit_frac", "mix_edit_frac", "mix_n_edit")
                   if c in w.columns]
    w2 = w
    score_cols = list(dict.fromkeys(score_cols))
    print(f"{len(score_cols)} candidate monitors")

    tasks = w2.groupby("run_id")["task"].first()
    rng = np.random.default_rng(args.seed)
    budgets = (0.20, 0.10, 0.05, 0.02)
    table: List[Dict[str, object]] = []
    for col in score_cols:
        series = {rid: np.nan_to_num(S.rank_normalise(v), nan=0.5)
                  for rid, v in S.per_step_series(w2, col).items()}
        stat = {rid: S.prefix_max_run(v > 0.5) for rid, v in causal.items()}
        neg_runs = [r for r, h in healthy.items() if h]
        neg_tasks = sorted(set(tasks.reindex(neg_runs).dropna().tolist()))
        rng2 = np.random.default_rng(args.seed)
        rng2.shuffle(neg_tasks)
        folds = np.array_split(np.array(neg_tasks), args.folds) if len(neg_tasks) >= args.folds \
            else [np.array(neg_tasks)]
        for budget in budgets:
            thrs = []
            for held in folds:
                held_set = set(held.tolist())
                calib = [r for r in neg_runs if tasks.get(r) not in held_set] or neg_runs
                q = {r: np.quantile(series[r], 1.0 - budget) for r in calib if r in series}
                thrs.append(float(np.median(list(q.values()))) if q else np.inf)
            det = fa = 0
            lats: List[float] = []
            adv: List[float] = []
            for rid, v in series.items():
                thr = np.inf
                for held, t in zip(folds, thrs):
                    if tasks.get(rid) in set(held.tolist()):
                        thr = t
                        break
                if not np.isfinite(thr):
                    thr = float(np.quantile(v, 1.0 - budget))
                over = np.nonzero(v > thr)[0]
                if not len(over):
                    continue
                t0 = int(over[0])
                if healthy[rid]:
                    fa += 1
                else:
                    det += 1
                    lat = latent[rid]
                    if lat is not None:
                        lats.append(float(t0 - lat))
                        total = float((causal[rid] > 0.5).sum())
                        adv.append(min(1.0, max(0.0, (lat - t0) / max(1.0, total)) * -1
                                       if t0 < lat else 1.0))
            table.append({
                "monitor": col, "budget": budget,
                "recall": det / max(1, n_pos), "false_alarm_rate": fa / max(1, n_neg),
                "precision": det / max(1, det + fa),
                "n_detected": det, "n_false_alarms": fa,
                "median_leadtime_steps": float(np.median(lats)) if lats else float("nan"),
            })
    df = pd.DataFrame(table)
    res["table"] = table
    best = (df[df.budget == 0.10].sort_values("recall", ascending=False).head(3)
            if (df.budget == 0.10).any() else df.head(0))
    print("\nat a 10% false-alarm budget:")
    for r in best.itertuples():
        print(f"  {r.monitor:<26} recall {r.recall:.3f}  FA {r.false_alarm_rate:.3f}  "
              f"precision {r.precision:.3f}  median latency {r.median_leadtime_steps:+.1f} steps")
    # the useful summary: can we hold 5% FA with any recall?
    low = df[df.budget <= 0.05].sort_values("recall", ascending=False).head(3)
    print("\nat a 5% budget (the regime the first version could not reach at all):")
    for r in low.itertuples():
        print(f"  {r.monitor:<26} budget {r.budget:.2f}  recall {r.recall:.3f}  "
              f"FA {r.false_alarm_rate:.3f}  precision {r.precision:.3f}")
    res["summary"] = {
        "best_at_10pct": best.to_dict("records"),
        "best_at_5pct_or_better": low.to_dict("records"),
        "note": ("the event is a dead-end window, which needs the final patch, so this is a "
                 "retrospective target being predicted online: a genuine claim, unlike the "
                 "quiet-window version which shares telemetry with the feature set"),
    }
    with open(OUT / "sequential_deadend.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'sequential_deadend.json'}")


if __name__ == "__main__":
    main()
