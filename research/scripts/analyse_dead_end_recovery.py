"""Is a wasted edit a cost, or a diagnostic?

    python scripts/analyse_dead_end_recovery.py

§2.19 found that **83.1% of successful runs contain at least one dead-end edit**. If a dead end
were pure loss, that number would be strange: successful runs would be the ones that avoided
wasteful writing. The alternative is that a dead end *teaches* something — the agent finds out its
approach is wrong — and the runs that succeed are the ones that notice and change course.

That is testable, because it makes a behavioural prediction: **after a dead end, a run should change
what it is doing.** Specifically, compared with the same run's edits before the first dead end, the
edits after it should touch *newer* files, be *larger*, and introduce *more new entities*. If
instead post-dead-end edits look identical to pre-dead-end ones, the dead end taught nothing and the
surviving-runs statistic is just a length effect.

Measured within runs, so run length and task are held fixed:

``R1`` trajectory change: new-file share, edit size and novelty before versus after the first dead end;
``R2`` course-change rate: the share of runs whose post-dead-end edits are measurably different,
       against a bootstrap null built by placing the "dead end" at a random rank;
``R3`` outcome: success rate for runs that change course after their first dead end versus those
       that do not.

Writes ``results/rebuild/dead_end_recovery.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "file_shown", "added_lines_n"])
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
    d["n_lines"] = d["added_lines_n"].fillna(0)
    d["rank"] = d.groupby("run_id").cumcount()

    rng = np.random.default_rng(args.seed)
    rows: List[Dict[str, float]] = []
    for rid, g in d.groupby("run_id", sort=False):
        de = np.nonzero(g["dead_end"].to_numpy() > 0)[0]
        if len(de) == 0 or len(g) < 6:
            continue
        first = int(de[0])
        if first < 2 or first > len(g) - 3:
            continue
        before, after = g.iloc[:first], g.iloc[first + 1:]
        if len(before) < 2 or len(after) < 2:
            continue
        new_before = before["file_shown"].nunique() / max(1, len(before))
        new_after = after["file_shown"].nunique() / max(1, len(after))
        # a bootstrap control: the same split at a random rank
        k = int(rng.integers(2, len(g) - 1))
        b2, a2 = g.iloc[:k], g.iloc[k + 1:]
        rows.append({
            "run_id": rid, "task": g["task"].iloc[0], "reward": float(g["reward"].max()),
            "first_dead": first, "n": len(g),
            "lines_before": float(before["n_lines"].mean()),
            "lines_after": float(after["n_lines"].mean()),
            "files_before": float(new_before), "files_after": float(new_after),
            "rand_lines_before": float(b2["n_lines"].mean()) if len(b2) else np.nan,
            "rand_lines_after": float(a2["n_lines"].mean()) if len(a2) else np.nan,
            "rand_files_before": float(b2["file_shown"].nunique() / max(1, len(b2))) if len(b2) else np.nan,
            "rand_files_after": float(a2["file_shown"].nunique() / max(1, len(a2))) if len(a2) else np.nan,
        })
    r = pd.DataFrame(rows)
    print(f"{len(r)} runs with a usable first dead end (at rank 2..n-3)")

    res: Dict[str, object] = {"n_runs": int(len(r))}
    # ---- R1: within-run change after the first dead end, against a random split ---------
    obs_lines = float((r["lines_after"] - r["lines_before"]).mean())
    ctl_lines = float((r["rand_lines_after"] - r["rand_lines_before"]).mean())
    obs_files = float((r["files_after"] - r["files_before"]).mean())
    ctl_files = float((r["rand_files_after"] - r["rand_files_before"]).mean())
    res["R1_change"] = {
        "edit_size_change_at_real_dead_end": obs_lines,
        "edit_size_change_at_random_split": ctl_lines,
        "new_file_rate_change_at_real_dead_end": obs_files,
        "new_file_rate_change_at_random_split": ctl_files,
        "p_lines": float(stats.wilcoxon(r["lines_after"] - r["lines_before"]).pvalue)
        if len(r) > 10 else float("nan"),
        "n_runs": int(len(r)),
    }
    print(f"\nR1 edit size after vs before: real dead end {obs_lines:+.2f} lines, "
          f"random split {ctl_lines:+.2f}")
    print(f"   new-file rate after vs before: real {obs_files:+.3f}, random {ctl_files:+.3f}")

    # ---- R2: how many runs change course measurably? -----------------------------------
    changed = float((r["lines_after"] > r["lines_before"] * 1.5).mean())
    unchanged = float((np.abs(r["lines_after"] - r["lines_before"]) < 1e-9).mean())
    res["R2_course_change"] = {
        "share_editing_larger_after": changed, "share_identical_size": unchanged,
        "control_share_larger_after": float((r["rand_lines_after"]
                                             > r["rand_lines_before"] * 1.5).mean()),
    }
    print(f"\nR2 after the dead end: {changed:.1%} of runs edit larger, {unchanged:.1%} unchanged "
          f"(random split basis: {res['R2_course_change']['control_share_larger_after']:.1%})")

    # ---- R3: does changing course predict success? -------------------------------------
    cc = r["lines_after"] > r["lines_before"]
    res["R3_outcome"] = {
        "success_when_larger_after": float(r.loc[cc, "reward"].mean()) if cc.any() else float("nan"),
        "success_when_not": float(r.loc[~cc, "reward"].mean()) if (~cc).any() else float("nan"),
        "n_larger": int(cc.sum()), "n_not": int((~cc).sum()),
        "p": float(stats.mannwhitneyu(r.loc[cc, "reward"], r.loc[~cc, "reward"]).pvalue)
        if cc.any() and (~cc).any() else float("nan"),
    }
    o = res["R3_outcome"]
    print(f"\nR3 success when the next edit is larger: {o['success_when_larger_after']:.3f} "
          f"({o['n_larger']} runs) vs {o['success_when_not']:.3f} ({o['n_not']} runs) "
          f"p={o['p']:.2e}")

    res["interpretation"] = (
        "If post-dead-end edits are measurably different from pre-dead-end ones and the difference "
        "exceeds the random-split control, a dead end carries information the agent uses; if the "
        "difference matches the control, the dead end taught nothing and the survivable-dead-end "
        "statistic of 2.19 is a length effect rather than a recovery.")
    print(f"\n{res['interpretation']}")
    with open(OUT / "dead_end_recovery.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"wrote {OUT / 'dead_end_recovery.json'}")


if __name__ == "__main__":
    main()
