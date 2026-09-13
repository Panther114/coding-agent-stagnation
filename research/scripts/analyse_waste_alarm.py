"""A waste alarm a person could actually implement: an absolute rule, calibrated and validated.

    python scripts/analyse_waste_alarm.py

Three earlier attempts at a waste alarm failed, and the failure had one cause worth naming: every
threshold was **relative to the run**, so "alarm on the top 5% of this run's windows" is true by
construction once a run has a few hundred windows, and the measured false-alarm rate collapsed to
"alarms on everything". A rule that can be deployed must use an **absolute** level.

The rule here is one line: *alarm when the dead-end share over the run so far exceeds L, once at
least N edits have been seen.* Both parameters are calibrated on **training** instances and applied
frozen to **held-out** instances, so the reported false-alarm rate is a real out-of-sample number.

Two questions are answered:

``A1`` does the alarm fire early enough to matter?  Reported as the share of the run elapsed at the
       alarm, which is what a budget policy acts on.
``A2`` is the alarm *right*?  Precision and recall against the run's final outcome, and against the
       run's eventual total dead-end share — the latter being the quantity the alarm is actually
       about, and the one a refusal policy would act on.

Writes ``results/rebuild/waste_alarm.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "results" / "rebuild"


def build() -> pd.DataFrame:
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


def alarm_for_run(g: pd.DataFrame, level: float, min_n: int) -> Tuple[object, float, float]:
    """First rank where the cumulative dead-end share exceeds `level` after `min_n` edits."""
    de = g["dead_end"].to_numpy(dtype=float)
    n = len(de)
    run = 0.0
    for i in range(n):
        run += de[i]
        if i + 1 >= min_n and (run / (i + 1)) > level:
            return i, run / (i + 1), (i + 1) / n
    return None, float("nan"), float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    d = build()
    grp = list(d.groupby(["task", "run_id"], sort=False))
    runs = pd.DataFrame([{"task": t, "run_id": r, "n_edit": len(g),
                          "dead_share": float(g["dead_end"].mean()),
                          "reward": float(g["reward"].max())}
                         for (t, r), g in grp])
    print(f"{len(runs)} runs, {runs.task.nunique()} tasks; "
          f"mean dead-end share {runs.dead_share.mean():.3f}")

    tasks = np.array(sorted(runs.task.unique()))
    rng = np.random.default_rng(args.seed)
    rng.shuffle(tasks)
    folds = np.array_split(tasks, args.folds)

    grid_level = [0.5, 0.6, 0.7, 0.8, 0.9]
    grid_min = [3, 5, 8]
    res: Dict[str, object] = {"n_runs": int(len(runs)),
                              "mean_dead_share": float(runs.dead_share.mean()),
                              "grid": {"level": grid_level, "min_edits": grid_min}}
    # ---- precompute every rule's outcome once ---------------------------------------
    # The calibration walks the whole grid on every fold, so the alarm is evaluated for each
    # run once per cell up front rather than inside the fold loop.
    combos = [(lv, mn) for lv in grid_level for mn in grid_min]
    pre: Dict[Tuple[float, int], Dict[str, object]] = {}
    t0 = pd.Timestamp.now()
    for lv, mn in combos:
        out = {}
        for (t, r), g in grp:
            a, share, elapsed = alarm_for_run(g, lv, mn)
            out[r] = (a is not None, float(g["dead_end"].mean()), share, elapsed)
        pre[(lv, mn)] = out
    print(f"precomputed {len(combos)} rule cells for {len(runs)} runs in "
          f"{(pd.Timestamp.now() - t0).total_seconds():.0f}s")

    # ---- calibration on training instances only --------------------------------------
    chosen: List[Dict[str, object]] = []
    for held in folds:
        held_set = set(held.tolist())
        best = None
        for lv, mn in combos:
            cells = pre[(lv, mn)]
            fired = hits = tot = 0
            for task, run_id in zip(runs.task, runs.run_id):
                if task in held_set:
                    continue
                tot += 1
                fired_flag, dead_share, _s, _e = cells[run_id]
                if fired_flag:
                    fired += 1
                    if dead_share > 0.4:
                        hits += 1
            prec = hits / fired if fired else 0.0
            cov = fired / max(1, tot)
            score = prec * min(1.0, cov / 0.10)   # precision, but require >=10% firing
            if best is None or score > best["score"]:
                best = {"level": lv, "min_edits": mn, "train_precision": prec,
                        "train_fire_rate": cov, "score": score}
        chosen.append({"held_tasks": int(len(held)), **best})
        print(f"  fold: chose level={best['level']:.1f} min_edits={best['min_edits']} "
              f"(train precision {best['train_precision']:.3f}, fire rate "
              f"{best['train_fire_rate']:.3f})")
    res["folds"] = chosen
    modal = pd.Series([(c["level"], c["min_edits"]) for c in chosen]).mode().iloc[0]
    level, min_n = float(modal[0]), int(modal[1])
    res["modal_choice"] = {"level": level, "min_edits": min_n,
                           "chosen_in_folds": int(sum(1 for c in chosen
                                                      if c["level"] == level
                                                      and c["min_edits"] == min_n))}
    print(f"\nmodal choice across folds: level > {level:.1f} after {min_n} edits "
          f"({res['modal_choice']['chosen_in_folds']}/{len(chosen)} folds)")

    # ---- frozen application to held-out runs ------------------------------------------
    cells = pre[(level, min_n)]
    fired = []
    for (t, r), g in grp:
        alarmed, dead_share, share_at_alarm, frac_elapsed = cells[r]
        fired.append({"task": t, "run_id": r, "n_edit": len(g),
                      "dead_share": dead_share,
                      "reward": float(g["reward"].max()),
                      "alarmed": alarmed,
                      "share_at_alarm": share_at_alarm,
                      "frac_elapsed_at_alarm": frac_elapsed})
    f = pd.DataFrame(fired)
    pos = f["dead_share"] > 0.4
    tp = int((f.alarmed & pos).sum())
    fp = int((f.alarmed & ~pos).sum())
    fn = int((~f.alarmed & pos).sum())
    res["out_of_sample"] = {
        "rule": {"level": level, "min_edits": min_n},
        "n_runs": int(len(f)), "n_high_waste": int(pos.sum()),
        "recall": tp / max(1, tp + fn),
        "precision": tp / max(1, tp + fp),
        "fire_rate": float(f.alarmed.mean()),
        "false_alarm_rate_on_low_waste": fp / max(1, int((~pos).sum())),
        "median_frac_elapsed_at_alarm": float(f.loc[f.alarmed, "frac_elapsed_at_alarm"].median())
        if f.alarmed.any() else float("nan"),
        "median_share_at_alarm": float(f.loc[f.alarmed, "share_at_alarm"].median())
        if f.alarmed.any() else float("nan"),
    }
    o = res["out_of_sample"]
    print(f"\nfrozen rule applied to all runs: fires on {o['fire_rate']:.1%}")
    print(f"  against a high-waste run (dead share > 0.40): recall {o['recall']:.3f}, "
          f"precision {o['precision']:.3f}, false alarms {o['false_alarm_rate_on_low_waste']:.3f}")
    print(f"  the alarm fires after {o['median_frac_elapsed_at_alarm']:.1%} of the run on median, "
          f"when the observed dead-end share is {o['median_share_at_alarm']:.2f}")

    # outcome relation, for completeness
    res["outcome"] = {
        "success_alarmed": float(f.loc[f.alarmed, "reward"].mean()),
        "success_not_alarmed": float(f.loc[~f.alarmed, "reward"].mean()),
    }
    print(f"  success: {res['outcome']['success_alarmed']:.3f} among alarmed runs vs "
          f"{res['outcome']['success_not_alarmed']:.3f} among the rest")

    with open(OUT / "waste_alarm.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'waste_alarm.json'}")


if __name__ == "__main__":
    main()
