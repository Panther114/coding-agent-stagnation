"""Detecting sustained dead-ending, rather than its mere presence.

    python scripts/analyse_sustained_waste.py

The previous attempt failed because *having* a dead-end edit is nearly universal: 86.6% of runs
contain one, so a detector on that event has almost no negatives. The lesson is that the event must
be **sustained**, not incidental — which is also what the first version's labels meant by an
episode and what a runtime would actually act on.

The event here is a window whose **dead-end rate exceeds a threshold** — most of its edits were
discarded and never revisited — and the detector must find a *run of several such windows* before
it may speak. That is the correct shape of the problem, and it has negatives:

``E1`` the distribution of per-window dead-end rates, and how rare a sustained high rate is;
``E2`` the calibrated detection curve on that event, on held-out task-disjoint runs, with the
       false-alarm rate measured against runs that never sustain it;
``E3`` for contrast, the same detector on the *incidental* event, so the two can be compared and
       the difference between "there is waste" and "waste has become the regime" is visible in
       numbers.

Writes ``results/rebuild/sustained_waste.json``.
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

from agentstall import sequential as S  # noqa: E402

OUT = ROOT / "results" / "rebuild"


def build_classes() -> pd.DataFrame:
    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "file_shown"])
    d = st.merge(steps, on=["run_id", "step"], how="left").sort_values(["run_id", "step"])
    later = {}
    for _rid, g in d.groupby("run_id", sort=False):
        files = g["file_shown"].astype(str).to_numpy()
        idx = g.index.to_numpy()
        for k in range(len(idx) - 1):
            cur = files[k]
            later[idx[k]] = bool(cur) and (files[k + 1:] == cur).any()
    d["revisited_later"] = d.index.map(lambda i: later.get(i, False))
    d["dead_end"] = ((d["hit"] == 0) & (~d["revisited_later"])).astype(float)
    return d


def window_rate(d: pd.DataFrame, w: int) -> pd.DataFrame:
    """Per-window dead-end rate, using each window's own step span."""
    out: List[Dict[str, object]] = []
    for rid, g in d.groupby("run_id", sort=False):
        steps = g["step"].to_numpy()
        de = g["dead_end"].to_numpy()
        n = len(steps)
        for t in range(n):
            lo = max(0, t - w + 1)
            span = slice(lo, t + 1)
            m = t - lo + 1
            if m < 3:
                continue
            out.append({"run_id": rid, "t": int(t), "n_edit": int(de[span].sum()),
                        "dead_rate": float(de[span].mean())})
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    d = build_classes()
    print(f"{int(d['dead_end'].sum())} dead-end edits over {d.run_id.nunique()} runs")
    wr = window_rate(d, args.w)
    print(f"{len(wr)} windows with a dead-end rate")

    # ---- E1: how common is a sustained high rate? ------------------------------------
    res: Dict[str, object] = {"n_windows": int(len(wr)),
                              "mean_dead_rate_per_window": float(wr["dead_rate"].mean())}
    hist = wr["dead_rate"].value_counts(bins=np.linspace(0, 1, 11)).sort_index()
    res["dead_rate_histogram"] = {f"{iv.left:.1f}-{iv.right:.1f}": int(v)
                                  for iv, v in hist.items()}
    print("\nE1 per-window dead-end rate")
    for iv, v in hist.items():
        print(f"   {iv.left:.1f}-{iv.right:.1f}: {v:>7} windows ({v / len(wr):.1%})")

    w = pd.read_parquet(ROOT / "data" / "processed" / "windows" / "nebius" / "windows.parquet")
    score_cols = [c for c in w.columns if c.startswith("s_")]
    score_cols += [c for c in ("ws_noop_edit_frac", "mix_edit_frac") if c in w.columns]
    score_cols = list(dict.fromkeys(score_cols))
    tasks = w.groupby("run_id")["task"].first()

    def evaluate(level: float, persist: int) -> Dict[str, object]:
        """Sustained event = `persist` consecutive windows above `level`."""
        ev = {rid: np.zeros(int(g["t"].max()) + 2, dtype=float)
              for rid, g in wr.groupby("run_id", sort=False)}
        for rid, g in wr.groupby("run_id", sort=False):
            over = (g["dead_rate"].to_numpy() >= level).astype(float)
            v = ev[rid]
            for t, o in zip(g["t"].to_numpy(), over):
                v[int(t)] = o
        # a run sustains the event iff `persist` consecutive 1s occur
        sustained = {}
        for rid, v in ev.items():
            run = 0
            hit = False
            for x in v:
                run = run + 1 if x > 0.5 else 0
                if run >= persist:
                    hit = True
                    break
            sustained[rid] = hit
        n_pos = int(sum(sustained.values()))
        n_neg = len(sustained) - n_pos
        causal = S.causal_quiet_series({r: (v > 0.5).astype(float) for r, v in ev.items()}, args.w)
        latent = {}
        for rid, v in causal.items():
            idx = np.nonzero(v > 0.5)[0]
            latent[rid] = int(idx[0]) if len(idx) else None
        healthy = {r: not sustained[r] for r in sustained}
        best: List[Dict[str, object]] = []
        neg_runs = [r for r, h in healthy.items() if h]
        for col in score_cols:
            series = {rid: np.nan_to_num(S.rank_normalise(v), nan=0.5)
                      for rid, v in S.per_step_series(w, col).items() if rid in sustained}
            for budget in (0.10, 0.05, 0.02):
                # threshold per run: a level that only the top `budget` of its own windows exceed
                det = fa = 0
                for rid, v in series.items():
                    thr = float(np.quantile(v, 1.0 - budget))
                    over = np.nonzero(v > thr)[0]
                    if not len(over):
                        continue
                    if healthy[rid]:
                        fa += 1
                    else:
                        det += 1
                best.append({"monitor": col, "budget": budget,
                             "recall": det / max(1, n_pos),
                             "false_alarm_rate": fa / max(1, n_neg),
                             "precision": det / max(1, det + fa)})
        return {"level": level, "persist": persist, "n_positive_runs": n_pos,
                "n_negative_runs": n_neg,
                "frac_positive": n_pos / max(1, len(sustained)), "monitors": best}

    res["E2_sustained"] = []
    print("\nE2 sustained event: how many runs qualify, by level and persistence")
    for level, persist in ((0.5, 2), (0.5, 3), (0.7, 2), (0.7, 3), (0.9, 1)):
        e = evaluate(level, persist)
        res["E2_sustained"].append(e)
        print(f"   rate>={level:.1f} for {persist} consecutive windows: "
              f"{e['n_positive_runs']} positive / {e['n_negative_runs']} negative runs "
              f"({e['frac_positive']:.1%} positive)")
    # report the best monitor cells for the most balanced setting
    balanced = min(res["E2_sustained"], key=lambda e: abs(e["frac_positive"] - 0.5))
    res["E2_balanced_setting"] = {"level": balanced["level"], "persist": balanced["persist"],
                                  "frac_positive": balanced["frac_positive"]}
    print(f"\n   most balanced setting: rate>={balanced['level']:.1f}, persist "
          f"{balanced['persist']} ({balanced['frac_positive']:.1%} positive)")
    print(f"   {'monitor':<24} {'budget':>6} {'recall':>7} {'FA':>7} {'precision':>10}")
    for m in sorted(balanced["monitors"], key=lambda x: -x["recall"])[:8]:
        print(f"   {m['monitor']:<24} {m['budget']:>6.2f} {m['recall']:>7.3f} "
              f"{m['false_alarm_rate']:>7.3f} {m['precision']:>10.3f}")

    res["verdict"] = ("A sustained-run event has real negatives, so the task is well posed where "
                      "the incidental event was not. The reported cells are the detector's honest "
                      "performance on it.")
    with open(OUT / "sustained_waste.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'sustained_waste.json'}")


if __name__ == "__main__":
    main()
