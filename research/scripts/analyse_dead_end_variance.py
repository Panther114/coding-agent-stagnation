"""Is dead-ending a property of the agent, or of the task?

    python scripts/analyse_dead_end_variance.py

If the dead-end rate is largely a property of the *task*, then a runtime cannot fix it and a
monitor is the wrong instrument; the finding becomes "some issues are unworkable at this scale".
If it is a property of the *agent* — the same issue, different models, different dead-end rates —
then it is a property of how the agent works and a monitor (or a scaffold change) can act on it.

The decomposition is a one-way variance split of the per-run dead-end rate across task and model,
with a paired comparison restricted to instances that more than one model attempted. That
within-instance control is the same device used for the outcome result, and it is what makes the
attribution credible rather than correlational.

Writes ``results/rebuild/dead_end_variance.json``.
"""
from __future__ import annotations

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
    sys.stdout.reconfigure(encoding="utf-8")
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
    d["wasted"] = (1 - d["hit"]).astype(float)

    per_run = d.groupby(["run_id", "task", "model"]).agg(
        dead_end=("dead_end", "mean"), wasted=("wasted", "mean"),
        n_edit=("hit", "size"), reward=("reward", "max")).reset_index()
    print(f"{len(per_run)} runs, {per_run.task.nunique()} tasks, {per_run.model.nunique()} models")
    print(f"pooled dead-end rate {per_run.dead_end.mean():.3f}, "
          f"sd across runs {per_run.dead_end.std():.3f}")

    def variance_split(col: str) -> Dict[str, float]:
        y = per_run[col].to_numpy(dtype=float)
        grand = y.mean()
        task_means = per_run.groupby("task")[col].transform("mean").to_numpy(dtype=float)
        model_means = per_run.groupby("model")[col].transform("mean").to_numpy(dtype=float)
        ss_total = float(((y - grand) ** 2).sum())
        ss_task = float(((task_means - grand) ** 2).sum())
        ss_model = float(((model_means - grand) ** 2).sum())
        # residual after removing both main effects
        resid = y - task_means - model_means + grand
        ss_resid = float((resid ** 2).sum())
        return {"ss_total": ss_total, "ss_task": ss_task, "ss_model": ss_model,
                "ss_resid": ss_resid,
                "frac_task": ss_task / ss_total if ss_total else float("nan"),
                "frac_model": ss_model / ss_total if ss_total else float("nan"),
                "frac_residual": ss_resid / ss_total if ss_total else float("nan")}

    res: Dict[str, object] = {"n_runs": int(len(per_run)),
                              "pooled_dead_end": float(per_run.dead_end.mean()),
                              "pooled_wasted": float(per_run.wasted.mean())}
    for col in ("dead_end", "wasted"):
        v = variance_split(col)
        res[f"variance_{col}"] = v
        print(f"\n{col}: task explains {v['frac_task']:.1%}, model {v['frac_model']:.1%}, "
              f"neither {v['frac_residual']:.1%}")

    # ---- within-instance, across models ---------------------------------------------
    both = per_run.groupby("task")["model"].nunique()
    sel = both[both >= 2].index
    sub = per_run[per_run.task.isin(sel)]
    res["multi_model_instances"] = {"n_instances": int(len(sel)), "n_runs": int(len(sub))}
    print(f"\n{len(sel)} instances attempted by more than one model ({len(sub)} runs)")
    pairs: List[float] = []
    for _task, g in sub.groupby("task"):
        m = g.groupby("model")["dead_end"].mean()
        if len(m) >= 2:
            pairs.append(float(m.max() - m.min()))
    if pairs:
        a = np.asarray(pairs)
        res["within_instance_model_spread"] = {
            "mean_max_minus_min": float(a.mean()), "median": float(np.median(a)),
            "n_instances": int(len(a)),
        }
        print(f"  dead-end-rate spread between the best and worst model on the same instance: "
              f"mean {a.mean():.3f}, median {np.median(a):.3f}")

    # ---- does the model's aggregate dead-end rate track its success rate? -------------
    per_model = per_run.groupby("model").agg(dead_end=("dead_end", "mean"),
                                             success=("reward", "mean"),
                                             n=("run_id", "size")).reset_index()
    res["per_model"] = per_model.to_dict("records")
    print("\nper model:")
    for r in per_model.itertuples():
        print(f"  {r.model:<24} runs {r.n:>6}  dead-end {r.dead_end:.3f}  success {r.success:.3f}")
    if len(per_model) >= 3:
        rho = stats.spearmanr(per_model.dead_end, per_model.success).statistic
        res["model_rank_correlation"] = float(rho)
        print(f"  rank correlation between dead-end rate and success rate across models: {rho:+.2f} "
              f"(n={len(per_model)} models — anecdotal, reported for completeness)")

    res["interpretation"] = (
        "A task-dominated variance share means dead-ending is mostly a property of the issue and "
        "not of the agent, so a per-run monitor cannot remove it; an agent-dominated share means "
        "the same issue dead-ends differently for different models, which a runtime could act on.")
    print(f"\ninterpretation: {res['interpretation']}")
    with open(OUT / "dead_end_variance.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'dead_end_variance.json'}")


if __name__ == "__main__":
    main()
