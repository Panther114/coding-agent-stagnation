"""Honest validation of the operating point: tune hyperparameters on training runs only.

The sweep found B5_novelty + 3-step smoothing + k=1.0 reaching 0.53 detection at 0.168 window-level
false alarms. But that configuration was selected from 360 candidates evaluated on the SAME data,
so the number is optimistically biased by selection.

This does nested leave-one-run-out validation:
  outer loop   : hold out one run (or a fold of runs); it is never seen during tuning
  inner loop   : choose monitor / smoothing / k / m on the OTHER runs only, by the stated objective
                 (maximise detection subject to window-level false alarms < 20%)
  evaluation   : apply the chosen configuration and threshold, frozen, to the held-out runs

The threshold itself comes from the run's own opening phase, which is legitimate online. The
configuration is chosen without the held-out runs, which is what removes the selection bias.

Usage: python scripts/validate_target_nested.py
"""
from __future__ import annotations

import collections
import csv
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import pyarrow.parquet as pq

GOLD = "../datasets/annotations/tb2/adjudicated.csv"
SCORES = "results/final/tb2_v5/monitor_scores.parquet"
OUT = "results/final/v2"
W = 10
MONITORS = ("B4_semantic", "B5_novelty", "C3_evid_sem", "C4_all_hand", "L_sem", "L_nov")
SMOOTHS = (1, 3, 5)
KS = (0.0, 0.5, 1.0, 1.5, 2.0)
MS = (1, 2, 3)


def load_gold():
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    by_traj = collections.defaultdict(list)
    for r in gold:
        by_traj[r["traj_id"]].append(r)
    for t in by_traj:
        by_traj[t].sort(key=lambda r: int(r["t"]))
    return by_traj


def regions_of(rs):
    regs, cur = [], None
    for r in rs:
        lab, t = int(r["binary"]), int(r["t"])
        if cur and lab == cur["label"]:
            cur["windows"].append(t); cur["end"] = max(cur["end"], t)
        else:
            if cur:
                regs.append(cur)
            cur = {"traj": r["traj_id"], "label": lab, "start": t, "end": t, "windows": [t]}
    if cur:
        regs.append(cur)
    return regs


def prep(sc, k_sm):
    ts = sorted(t for t in sc if sc[t] == sc[t])
    v = np.array([sc[t] for t in ts], dtype=float)
    out = {}
    for i, t in enumerate(ts):
        lo = max(0, i - k_sm + 1)
        out[t] = float(np.mean(v[lo:i + 1]))
    return out


def opening_base(sc, n, frac=0.15):
    lim = frac * n
    b = [v for t, v in sc.items() if t <= lim]
    if len(b) < 5:
        return None
    return float(np.mean(b)), float(np.std(b)) + 1e-6


def score_run(mon_scores, k_sm, k, m, traj_regions, n_steps):
    """Return (detections, fa_windows, fa_episodes) for one run's regions."""
    sc = prep(mon_scores, k_sm)
    base = opening_base(sc, n_steps)
    if base is None:
        return None
    mu, sd = base
    thr = mu + k * sd

    def fires(region):
        run = 0
        for t in sorted(region["windows"]):
            v = sc.get(t)
            if v is None:
                continue
            if v > thr:
                run += 1
                if run >= m:
                    return True
            else:
                run = 0
        return False

    det = sum(1 for g in traj_regions if g["label"] == 1 and fires(g))
    tot_pos = sum(1 for g in traj_regions if g["label"] == 1)
    fa_w = sum(1 for g in traj_regions if g["label"] == 0
               for t in g["windows"] if sc.get(t) is not None and sc.get(t) > thr)
    fa_ep = sum(1 for g in traj_regions if g["label"] == 0 and fires(g))
    prod_windows = sum(len(g["windows"]) for g in traj_regions if g["label"] == 0)
    return det, tot_pos, fa_w, prod_windows, fa_ep


def main() -> None:
    by_traj = load_gold()
    tab = pq.read_table(SCORES, columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist()
    series = collections.defaultdict(lambda: collections.defaultdict(dict))
    for r in tab:
        if r["w"] == W and r["monitor"] in MONITORS:
            series[r["monitor"]][r["traj_id"]][r["t"]] = r["score"]

    regs_by_run = {}
    for tid, rs in by_traj.items():
        regs_by_run[tid] = regions_of(rs)
    n_steps = {t: max(int(r["n_steps"]) for r in rs) for t, rs in by_traj.items()}
    runs = sorted(regs_by_run)
    print(f"runs {len(runs)}; episodes "
          f"{sum(1 for t in runs for g in regs_by_run[t] if g['label']==1)}; "
          f"productive regions "
          f"{sum(1 for t in runs for g in regs_by_run[t] if g['label']==0)}")

    # outer folds: 5 folds of runs
    rng = np.random.default_rng(7)
    perm = rng.permutation(len(runs))
    folds = [set(np.array(runs)[f].tolist()) for f in np.array_split(perm, 5)]

    total_det = total_pos = total_faw = total_pw = total_fae = total_neg = 0
    chosen = collections.Counter()
    for fi, hold in enumerate(folds):
        train = [r for r in runs if r not in hold]
        # ---- inner: choose configuration on training runs ----
        best_cfg, best_det, best_fa = None, -1, 1.0
        for mon in MONITORS:
            for k_sm in SMOOTHS:
                for k in KS:
                    for m in MS:
                        d = p = fw = pw = fe = ng = 0
                        for tid in train:
                            res = score_run(series[mon][tid], k_sm, k, m,
                                            regs_by_run[tid], n_steps.get(tid, 1))
                            if res is None:
                                continue
                            d += res[0]; p += res[1]; fw += res[2]; pw += res[3]; fe += res[4]
                            ng += sum(1 for g in regs_by_run[tid] if g["label"] == 0)
                        if p == 0 or pw == 0:
                            continue
                        det = d / p
                        fa = fw / pw
                        if fa < 0.20 and det > best_det:
                            best_det, best_fa, best_cfg = det, fa, (mon, k_sm, k, m)
        if best_cfg is None:
            print(f"  fold {fi}: no configuration met the constraint on training runs")
            continue
        chosen[str(best_cfg)] += 1
        mon, k_sm, k, m = best_cfg
        # ---- outer: apply frozen configuration to held-out runs ----
        for tid in hold:
            res = score_run(series[mon][tid], k_sm, k, m, regs_by_run[tid], n_steps.get(tid, 1))
            if res is None:
                continue
            total_det += res[0]; total_pos += res[1]; total_faw += res[2]
            total_pw += res[3]; total_fae += res[4]
            total_neg += sum(1 for g in regs_by_run[tid] if g["label"] == 0)
        print(f"  fold {fi}: chose {best_cfg} (train det {best_det:.2f} fa {best_fa:.3f}); "
              f"held-out so far det {total_det/max(1,total_pos):.2f} "
              f"FA_win {total_faw/max(1,total_pw):.3f}")

    det = total_det / max(1, total_pos)
    fa_w = total_faw / max(1, total_pw)
    fa_e = total_fae / max(1, total_neg)
    print(f"\n=== NESTED held-out result ===")
    print(f"  detection           {det:.3f}  ({total_det}/{total_pos} episodes)")
    print(f"  false alarms/window {fa_w:.3f}  ({total_faw}/{total_pw})")
    print(f"  false alarms/region {fa_e:.3f}  ({total_fae}/{total_neg})")
    ok = det > 0.50 and fa_w < 0.20
    print(f"  objective (<20% FA, >50% det): {'MET' if ok else 'NOT MET'}")
    print(f"  configurations chosen across folds: {dict(chosen)}")

    json.dump({"detection": det, "fa_window": fa_w, "fa_region": fa_e,
               "episodes_detected": total_det, "episodes_total": total_pos,
               "target_met": bool(ok), "chosen": dict(chosen),
               "n_runs": len(runs)},
              open(os.path.join(OUT, "nested_validation.json"), "w", encoding="utf-8"), indent=2)
    print(f"wrote {OUT}/nested_validation.json")


if __name__ == "__main__":
    main()
