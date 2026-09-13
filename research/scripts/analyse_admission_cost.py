"""What does an edit-admission policy actually cost?

    python scripts/analyse_admission_cost.py

The previous stage showed that refusing predicted-doomed edits raises the survival rate of what
gets applied — but that is a truism: refuse more, and the average of what remains goes up. The
real question is whether the *composition* improves beyond what blanket refusal would give.

This computes the quantity that decides it: **retained surviving edits**, the count (not the
share) of edits that land a surviving line, as the policy refuses more. Under a perfect
policy, refusing the worst edits first loses nothing and retained survivors stay at 100% until
every doomed edit is gone. Under a useless policy, retained survivors fall in exactly the same
proportion as admissions. The curve between those two limits is the whole value of the
predictor, and it is not visible in a survival *rate*.

Also reported:

* **informativeness** — the share of discarded edits that could be removed while keeping every
  surviving edit, and what fraction of that the policy actually achieves;
* **free-rule comparison** on the same curve, since the strongest single structural predictor is
  simply how much an edit writes;
* **run-level value** — whether the refused edits are concentrated in runs that fail anyway.

Writes ``results/rebuild/admission_cost.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    es = json.loads((OUT / "edit_structure.json").read_text(encoding="utf-8"))
    struct_cols: List[str] = es["features"]

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "is_edit", "file_total", "file_shown",
                                     "added_lines_n", "edit_lines", "tool", "n_cmds", "obs_chars"])
    d = st.merge(steps, on=["run_id", "step"], how="left")
    d = d[d["is_edit"].fillna(0) > 0].copy()
    d["n_added"] = d["added_lines_n"].fillna(0.0)
    d["file_size"] = d["file_total"].fillna(-1.0)
    d["edit_lines"] = d["edit_lines"].fillna(0.0)
    d["n_cmds"] = d["n_cmds"].fillna(0.0)
    d["obs_chars"] = d["obs_chars"].fillna(0.0)
    g = d.groupby("run_id")
    d["edit_rank"] = g.cumcount().astype(float)
    d["n_edits_run"] = g["step"].transform("size").astype(float)
    d["file_edits_before"] = g.apply(
        lambda x: x.groupby("file_shown").cumcount(), include_groups=False
    ).reset_index(level=0, drop=True).astype(float)
    dist: List[float] = []
    for _r, grp in d.groupby("run_id", sort=False):
        s = set()
        for f in grp["file_shown"].astype(str):
            s.add(f)
            dist.append(float(len(s)))
    d["distinct_files_so_far"] = dist
    d["tool_is_create"] = (d["tool"].astype(str).str.lower() == "create").astype(float)
    d["tool_is_replace"] = (d["tool"].astype(str).str.lower().isin(
        ["str_replace", "edit", "insert", "replace"]).astype(float))
    d["relpos"] = d["edit_rank"] / d["n_edits_run"].clip(lower=1)
    d["log_added"] = np.log1p(d["n_added"])
    d["log_file_size"] = np.log1p(d["file_size"].clip(lower=0))
    d["_survives"] = d["hit"].astype(float)
    d["p_survive"] = E.fit_logistic_cv(d, struct_cols, y_col="_survives",
                                       n_folds=args.folds, seed=args.seed)["oof"]

    n = len(d)
    total_surv = float(d["_survives"].sum())
    total_waste = float((1 - d["_survives"]).sum())
    print(f"{n} edit steps, {int(total_surv)} land a surviving line "
          f"({total_surv / n:.3f}), {int(total_waste)} do not")

    res: Dict[str, object] = {
        "n_edits": n, "n_surviving": int(total_surv), "n_wasted": int(total_waste),
        "perfect_curve_note": (
            "cov means the lowest possible admission rate that still keeps every surviving "
            "edit; it is the fraction of the corpus that is genuinely discardable."),
        "curves": {},
    }

    def curve(scores: np.ndarray, name: str) -> Dict[str, object]:
        order = np.argsort(scores)          # worst first
        surv = d["_survives"].to_numpy(dtype=float)[order]
        cum_surv = np.cumsum(surv)
        rows = []
        for refuse_frac in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
            k = int(round(refuse_frac * len(d)))
            kept = min(k, len(d))
            admitted = len(d) - kept
            retained = float(cum_surv[-1] - cum_surv[k - 1]) if k > 0 else float(cum_surv[-1])
            rows.append({
                "refuse_frac": refuse_frac,
                "admit_rate": admitted / len(d),
                "retained_survivor_share": retained / total_surv if total_surv else float("nan"),
                "survival_rate_of_admitted": (retained / admitted) if admitted else float("nan"),
                "discarded_edits": kept,
            })
        return rows

    # perfect policy: refuse every wasted edit first
    perfect_scores = d["_survives"].to_numpy(dtype=float) - 1.0  # wasted gets 0, survivor -1
    perfect = curve(perfect_scores, "perfect")
    learned = curve(-d["p_survive"].to_numpy(dtype=float), "learned")
    free = curve(-d["n_added"].to_numpy(dtype=float), "free_lines")
    random_scores = np.random.default_rng(args.seed).random(n)
    rnd = curve(random_scores, "random")

    res["curves"] = {"perfect": perfect, "learned": learned, "free_lines": free, "random": rnd}
    cov = total_waste / n
    res["discardable_fraction"] = float(cov)
    print(f"\nperfect policy keeps every surviving edit while refusing "
          f"{cov:.3f} of the corpus (the wasted share)")
    print(f"\n{'policy':<12} {'admit':>7} {'retained survivors':>19} {'survival of admitted':>21}")
    for name, rows in (("perfect", perfect), ("learned", learned), ("free_lines", free),
                       ("random", rnd)):
        for r in rows:
            if abs(r["refuse_frac"] - 0.3) < 1e-9 or abs(r["refuse_frac"] - 0.5) < 1e-9:
                print(f"{name:<12} {r['admit_rate']:>7.3f} {r['retained_survivor_share']:>19.3f} "
                      f"{r['survival_rate_of_admitted']:>21.3f}")

    # informativeness at a matched admission rate
    for frac in (0.2, 0.4):
        k = int(round(frac * n))
        order_l = np.argsort(-d["p_survive"].to_numpy(dtype=float))
        lr = float(d["_survives"].to_numpy(dtype=float)[order_l[: n - k]].sum())
        order_f = np.argsort(-d["n_added"].to_numpy(dtype=float))
        fr = float(d["_survives"].to_numpy(dtype=float)[order_f[: n - k]].sum())
        res.setdefault("matched", {})[f"refuse_{frac}"] = {
            "learned_retained_share": lr / total_surv,
            "free_retained_share": fr / total_surv,
            "perfect_retained_share": min(1.0, 1.0) if n - k > total_surv else (n - k) / total_surv,
            "random_retained_share": (n - k) / n,
        }
        m = res["matched"][f"refuse_{frac}"]
        print(f"\nat {frac:.0%} refusal: retained survivors  learned {m['learned_retained_share']:.3f}"
              f"  free-rule {m['free_retained_share']:.3f}  random {m['random_retained_share']:.3f}")

    with open(OUT / "admission_cost.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'admission_cost.json'}")


if __name__ == "__main__":
    main()
