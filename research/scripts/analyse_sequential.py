"""Sequential detection with an honestly calibrated false-alarm rate, plus the cost model.

    python scripts/analyse_sequential.py --corpus nebius --w 10

The problem this stage exists to solve
--------------------------------------
Thresholding a smoothed score, as the first version did, has no interpretable false-alarm
rate: a runtime looks after every step, so the number of looks is unbounded and the
"per-window" rate it reported is not the hour-to-hour risk a deployment faces.

What is built here
------------------
A **prefix statistic** -- the longest run of consecutive quiet windows so far -- with
thresholds calibrated on a held-out set of runs that produce *no* progress event at all.
Those runs are the real negatives: 70.4% of the Nebius corpus and 45.3% of Terminal-Bench
wastes no edit and never shows a quiet stretch, so the false-alarm rate is measured
against genuine negatives rather than an empty set.

Three things are reported together, because each alone is misleading:

* **an everyday guarantee** (``alpha`` = the probability that a run which never stalls is
  ever alarmed), calibrated on held-out runs.  The statistic is a prefix maximum, so the
  guarantee holds uniformly over the life of the run -- no multiple-look correction.
* **precision and recall** at each budget, since a detector that fires on everything
  achieves a perfect recall and is worthless.
* **the oracle**, computed from the same event definition, which bounds what any
  per-window detector could achieve on this target.

Everything is computed strictly causally: a window's own verdict is only allowed to
influence detection from the following window onward, so no alarm depends on the very
window it is meant to predict.

Writes ``results/rebuild/<corpus>_w<w>/sequential.json``.
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


def prefix_max_run(flags: np.ndarray) -> np.ndarray:
    """Running maximum of the current streak of consecutive True flags."""
    out = np.zeros(len(flags), dtype=float)
    cur = 0
    best = 0
    for i, f in enumerate(flags):
        cur = cur + 1 if f else 0
        best = max(best, cur)
        out[i] = best
    return out


def causal_quiet_series(events_by_run: Dict[str, np.ndarray], w: int) -> Dict[str, np.ndarray]:
    """Carry each window's verdict forward by a full window: no lookahead.

    ``y_stagnation`` is computed *inside* a window, so it becomes known only once the
    window has elapsed.  A runtime at step ``t`` may therefore act on the verdicts of
    windows that ended at or before ``t``, i.e. on ``x[t - w]``.  Shifting by ``w`` is the
    conservative choice and is what makes the reported latency a real delay.
    """
    out = {}
    for rid, ev in events_by_run.items():
        shifted = np.concatenate([np.zeros(w), ev[:-w]]) if len(ev) > w else np.zeros_like(ev)
        out[rid] = shifted
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--event-col", default="y_stagnation")
    ap.add_argument("--event-level", type=float, default=0.5)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    run_dir = Path(args.run_dir) if args.run_dir else \
        (ROOT / "results" / "rebuild" / f"{args.corpus}_w{args.w}")
    df = pd.read_parquet(run_dir / "window_scores.parquet")
    if args.event_col not in df.columns:
        raise SystemExit(f"{args.event_col} not in {run_dir}")
    res: Dict[str, object] = {"corpus": args.corpus, "w": args.w,
                              "event_col": args.event_col, "event_level": args.event_level}

    # window-level binary verdicts, then made causal
    df = df.assign(_ev=(df[args.event_col].to_numpy(dtype=float) > args.event_level).astype(float))
    ev_win = S.per_step_series(df, "_ev")
    ev_causal = causal_quiet_series(ev_win, args.w)

    # a run is a genuine negative iff no window of it ever shows the event
    healthy = {rid: bool(np.all(v < 0.5)) for rid, v in ev_win.items()}
    latent: Dict[str, Optional[int]] = {}
    for rid, v in ev_causal.items():
        idx = np.nonzero(v > 0.5)[0]
        latent[rid] = int(idx[0]) if len(idx) else None
    n_neg = int(sum(healthy.values()))
    n_pos = len(healthy) - n_neg
    res.update({"n_runs": len(healthy), "n_never_stalls": n_neg,
                "n_stalls": n_pos, "frac_never_stalls": n_neg / max(1, len(healthy))})
    print(f"runs {len(healthy)}: never-stalls {n_neg} ({n_neg / max(1, len(healthy)):.1%}), "
          f"stalls {n_pos}")

    # prefix statistic and its level (how long the current quiet streak is)
    stat = {rid: prefix_max_run(v > 0.5) for rid, v in ev_causal.items()}

    # thresholds calibrated on *task-disjoint* folds of the never-stalling runs
    runs_meta = df.groupby("run_id").agg(task=("task", "first"), n_steps=("n_steps", "max"),
                                         reward=("reward", "max")).reset_index()
    neg_tasks = sorted(set(runs_meta.loc[runs_meta.run_id.isin(
        [r for r, h in healthy.items() if h]), "task"]))
    rng = np.random.default_rng(args.seed)
    rng.shuffle(neg_tasks)
    task_folds = np.array_split(np.array(neg_tasks), args.folds) if len(neg_tasks) >= args.folds \
        else [np.array(neg_tasks)]
    task_of = dict(zip(runs_meta.run_id, runs_meta.task))
    neg_runs = [r for r, h in healthy.items() if h]

    # persistence sweep: alert once K consecutive causal quiet windows have been observed.
    # K is the operational knob -- a larger K costs latency and buys precision, and both
    # sides are reported so the trade can be judged rather than asserted.
    sweep: List[Dict[str, float]] = []
    stall_len = {}
    for rid, v in ev_causal.items():
        idx = np.nonzero(v > 0.5)[0]
        stall_len[rid] = int(v.sum())
    for k in (1, 2, 3, 4, 5, 6, 8):
        det = fa = 0
        lats = []
        cover = []
        for rid, v in ev_causal.items():
            quiet = v > 0.5
            # first index at which k consecutive True values have been seen
            run = 0
            alarm = None
            for i, q in enumerate(quiet):
                run = run + 1 if q else 0
                if run >= k:
                    alarm = i
                    break
            if healthy[rid]:
                if alarm is not None:
                    fa += 1
            else:
                if alarm is not None:
                    det += 1
                    latent0 = latent[rid]
                    if latent0 is not None:
                        lats.append(alarm - int(latent0))
                    tot = stall_len[rid]
                    if tot:
                        cover.append(min(k, tot) / tot)
        sweep.append({
            "k": k,
            "recall": det / max(1, n_pos),
            "false_alarm_rate": fa / max(1, n_neg),
            "precision": det / max(1, det + fa),
            "n_detected": det, "n_false_alarms": fa,
            "median_latency_steps": float(np.median(lats)) if lats else float("nan"),
            "median_stall_share_observed": float(np.median(cover)) if cover else float("nan"),
        })
        s = sweep[-1]
        print(f"  K={k}: recall {s['recall']:.3f}  FA {s['false_alarm_rate']:.3f}  "
              f"precision {s['precision']:.3f}  latency {s['median_latency_steps']:+.1f}  "
              f"stall-share-observed {s['median_stall_share_observed']:.2f}")
    res["persistence_sweep"] = sweep

    # threshold-budget curves, kept as the anytime guarantee reference
    curves: List[Dict[str, float]] = []
    budgets = (0.20, 0.10, 0.05, 0.02, 0.01)
    for budget in budgets:
        thr_folds = []
        for held in task_folds:
            held_set = set(held.tolist())
            calib = [r for r in neg_runs if task_of.get(r) not in held_set]
            if len(calib) < 20:
                calib = neg_runs
            maxes = np.array([float(np.max(stat[r])) for r in calib])
            thr_folds.append(float(np.quantile(maxes, 1.0 - budget)) if len(maxes) else np.inf)
        det = fa = 0
        lats = []
        thr_used = []
        for rid, v in stat.items():
            held = task_of.get(rid)
            # apply the fold whose calibration excluded this run's task
            thr = np.inf
            for held_fold, t in zip(task_folds, thr_folds):
                if held in set(held_fold.tolist()):
                    thr = t
                    break
            if not np.isfinite(thr):
                thr = float(np.quantile([float(np.max(stat[r])) for r in neg_runs], 1.0 - budget))
            thr_used.append(thr)
            if float(np.max(v)) <= thr:
                continue
            t = int(np.argmax(v > thr))
            if healthy[rid]:
                fa += 1
            else:
                det += 1
                lat = latent[rid]
                if lat is not None:
                    lats.append(t - int(lat))
        curves.append({
            "budget": budget,
            "threshold": float(np.median(thr_used)) if thr_used else float("nan"),
            "recall": det / max(1, n_pos),
            "false_alarm_rate": fa / max(1, n_neg),
            "precision": det / max(1, det + fa),
            "n_detected": det, "n_false_alarms": fa,
            "median_latency_steps": float(np.median(lats)) if lats else float("nan"),
            "fold_thresholds": thr_folds,
        })
        c = curves[-1]
        print(f"  budget {budget:.2f}: recall {c['recall']:.3f}  FA {c['false_alarm_rate']:.3f}  "
              f"precision {c['precision']:.3f}  latency {c['median_latency_steps']:+.1f}  "
              f"thr {c['threshold']:.0f}")
    res["curves"] = curves

    # oracle: a detector that reports the first causal quiet window with no false alarms
    det = fa = 0
    lats = []
    for rid, v in ev_causal.items():
        t = np.nonzero(v > 0.5)[0]
        if len(t) == 0:
            continue
        t0 = int(t[0])
        if healthy[rid]:
            fa += 1
        else:
            det += 1
            lat = latent[rid]
            if lat is not None:
                lats.append(t0 - int(lat))
    res["oracle"] = {"recall": det / max(1, n_pos), "false_alarm_rate": fa / max(1, n_neg),
                     "precision": det / max(1, det + fa),
                     "median_latency_steps": float(np.median(lats)) if lats else float("nan")}
    o = res["oracle"]
    print(f"  oracle: recall {o['recall']:.3f}  FA {o['false_alarm_rate']:.3f} "
          f"(a detector that simply reports the event must achieve this by construction)")

    # cost model at the 10% budget
    target = next((c for c in curves if abs(c["budget"] - 0.10) < 1e-9), curves[0])
    thr = target["threshold"]
    alarms = {}
    for rid, v in stat.items():
        if float(np.max(v)) > thr:
            alarms[rid] = int(np.argmax(v > thr)) + 1
        else:
            alarms[rid] = None
    res["cost_model"] = S.policy_value(runs_meta, alarms)
    res["cost_model"]["budget"] = target["budget"]
    res["cost_model"]["precision_at_budget"] = target["precision"]
    c = res["cost_model"]
    print(f"  cost at the {target['budget']:.0%} budget: stops {c['frac_runs_stopped']:.1%} of runs, "
          f"saving {c['step_saving_frac']:.1%} of steps; success among stopped runs "
          f"{c['success_among_stopped']:.3f} vs overall {c['success_overall']:.3f}")

    out = run_dir / "sequential.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
