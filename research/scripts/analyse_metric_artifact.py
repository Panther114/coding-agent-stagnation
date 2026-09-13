"""The spine: is the frozen "failed runs localise better" result a measurement artefact?

This extends ``analyse_wrongness.py`` to the point where the claim can be stated rigorously or
withdrawn.  Four things are established here:

A. MECHANISM 1 -- "confident wrongness".  The frozen metric ``on_target`` is the share of a run's
   edits aimed at files in **its own final patch**.  A run that fixates on the WRONG file and never
   wavers scores 1.0 on it.  So the metric cannot separate "found the right file" from "consistently
   edited the wrong file", and it should REWARD failure.  Test: among failed runs, those that never
   touched a gold file should score HIGHER on the self-referential metric than those that did.

B. MECHANISM 2 -- patch breadth.  Failed runs write broader patches (2.20 files vs 1.35), which
   enlarges the self-referential target set and mechanically raises the score.  Test: compare the
   pooled difference against a directly-standardised difference over patch-width strata.

C. ROBUSTNESS -- the gold target is matched by basename; re-run with a stricter path match.

D. NON-CIRCULARITY -- where the self-referential set and the gold set coincide (single-file patch
   whose file IS a gold file), the two metrics should agree.  If they do not, one of them is broken.

Everything is computed from the same edit steps; nothing here is refit on the outcome.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RES = ROOT / "results" / "rebuild"
STEPS = ROOT / "data" / "processed" / "steps"
RNG = np.random.default_rng(20260913)


def basenames(s: str) -> set:
    return {Path(t).name for t in str(s or "").split() if t.strip()}


def paths(s: str) -> set:
    return {t.strip() for t in str(s or "").split() if t.strip()}


def boot_diff(a: np.ndarray, b: np.ndarray, n: int = 4000) -> tuple:
    if len(a) < 2 or len(b) < 2:
        return (float("nan"), float("nan"))
    d = np.empty(n)
    for i in range(n):
        d[i] = RNG.choice(a, len(a)).mean() - RNG.choice(b, len(b)).mean()
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main() -> None:
    st = pd.read_parquet(STEPS / "nebius" / "steps.parquet",
                         columns=["run_id", "task", "model", "reward", "step", "is_edit",
                                  "file_shown"])
    rn = pd.read_parquet(STEPS / "nebius" / "runs.parquet",
                         columns=["run_id", "reward", "patch_files", "patch_n_files"])
    ed = st[st.is_edit == 1].merge(rn[["run_id", "patch_files", "patch_n_files"]],
                                  on="run_id", how="left")
    ed["base"] = ed.file_shown.fillna("").apply(lambda s: Path(str(s)).name)
    gold = pd.read_parquet(RES / "gold_patches.parquet")
    gb = {r.instance_id: set(r.gold_basenames) for r in gold.itertuples(index=False)}

    rows = []
    for run_id, g in ed.groupby("run_id", sort=False):
        own_b = basenames(g["patch_files"].iloc[0])
        own_p = paths(g["patch_files"].iloc[0])
        iid = str(g["task"].iloc[0])
        gset = gb.get(iid, set())
        n = len(g)
        if n == 0 or not gset:
            continue
        bases = g["base"].tolist()
        shown = g["file_shown"].fillna("").tolist()
        n_self = sum(1 for b in bases if b and b in own_b)
        n_gold = sum(1 for b in bases if b and b in gset)
        n_gold_path = sum(1 for s in shown if any(str(s).endswith(x) for x in gset))
        rows.append({
            "run_id": run_id, "instance_id": iid, "model": str(g["model"].iloc[0]),
            "reward": int(g["reward"].iloc[0]), "n_edit": n,
            "n_distinct_files": len({b for b in bases if b}),
            "patch_n_files": int(g["patch_n_files"].iloc[0]) if pd.notna(
                g["patch_n_files"].iloc[0]) else 0,
            "on_target_self": n_self / n,
            "on_target_gold": n_gold / n,
            "on_target_gold_path": n_gold_path / n,
            "ever_touched_gold": int(n_gold > 0),
        })
    d = pd.DataFrame(rows)
    print(f"runs with gold + patch info: {len(d):,}")

    out: dict = {"n_runs": int(len(d)), "mechanisms": {}, "robustness": {},
                 "verdict": {}}

    # ---- A. confident wrongness --------------------------------------------------
    fl = d[d.reward == 0]
    lost = fl[fl.ever_touched_gold == 0]
    wrong = fl[fl.ever_touched_gold == 1]
    lo, hi = boot_diff(lost.on_target_self.to_numpy(), wrong.on_target_self.to_numpy())
    out["mechanisms"]["confident_wrongness"] = {
        "claim": ("a failed run that NEVER reached the right file should still score high on "
                  "the self-referential metric"),
        "on_target_self_lost_runs": round(float(lost.on_target_self.mean()), 4),
        "on_target_self_wrong_fix_runs": round(float(wrong.on_target_self.mean()), 4),
        "delta_lost_minus_wrongfix": round(
            float(lost.on_target_self.mean() - wrong.on_target_self.mean()), 4),
        "delta_ci95": [lo, hi],
        "n_lost": int(len(lost)), "n_wrong_fix": int(len(wrong)),
        "on_target_gold_lost_runs": round(float(lost.on_target_gold.mean()), 4),
        "on_target_gold_wrong_fix_runs": round(float(wrong.on_target_gold.mean()), 4),
    }

    # ---- B. patch breadth as a composition effect ---------------------------------
    d["pw"] = d.patch_n_files.clip(upper=4)
    strata = []
    for k, g in d.groupby("pw"):
        s, f = g[g.reward == 1], g[g.reward == 0]
        if len(s) < 30 or len(f) < 30:
            continue
        strata.append({
            "patch_n_files": int(k), "n_solved": int(len(s)), "n_failed": int(len(f)),
            "gold_solved": round(float(s.on_target_gold.mean()), 4),
            "gold_failed": round(float(f.on_target_gold.mean()), 4),
            "gold_delta": round(float(s.on_target_gold.mean() - f.on_target_gold.mean()), 4),
            "touch_solved": round(float(s.ever_touched_gold.mean()), 4),
            "touch_failed": round(float(f.ever_touched_gold.mean()), 4),
            "touch_delta": round(float(s.ever_touched_gold.mean() - f.ever_touched_gold.mean()), 4),
        })
    # direct standardisation onto the pooled stratum distribution
    w = d.groupby("pw").size()
    w = w / w.sum()
    std_s = std_f = 0.0
    for s in strata:
        wt = float(w.get(s["patch_n_files"], 0.0))
        std_s += wt * s["gold_solved"]
        std_f += wt * s["gold_failed"]
    pooled_s = float(d.loc[d.reward == 1, "on_target_gold"].mean())
    pooled_f = float(d.loc[d.reward == 0, "on_target_gold"].mean())
    out["mechanisms"]["patch_breadth"] = {
        "strata": strata,
        "pooled_gold_delta_solved_minus_failed": round(pooled_s - pooled_f, 4),
        "standardised_gold_delta": round(std_s - std_f, 4),
        "mean_patch_n_files_solved": round(float(d.loc[d.reward == 1, "patch_n_files"].mean()), 3),
        "mean_patch_n_files_failed": round(float(d.loc[d.reward == 0, "patch_n_files"].mean()), 3),
        "reading": ("pooled vs standardised: how much of the pooled gap is composition rather "
                    "than within-stratum effect"),
    }

    # ---- C. robustness: path-level gold matching ----------------------------------
    out["robustness"]["path_level_matching"] = {
        "pooled_gold_basename_solved": round(pooled_s, 4),
        "pooled_gold_basename_failed": round(pooled_f, 4),
        "pooled_gold_path_solved": round(float(d.loc[d.reward == 1, "on_target_gold_path"].mean()), 4),
        "pooled_gold_path_failed": round(float(d.loc[d.reward == 0, "on_target_gold_path"].mean()), 4),
        "note": "if basename and path versions agree in sign, the match rule is not driving it",
    }

    # ---- D. non-circularity check -------------------------------------------------
    sub = d[(d.pw == 1) & (d.ever_touched_gold == 1)]
    out["robustness"]["non_circularity"] = {
        "n": int(len(sub)),
        "mean_on_target_self": round(float(sub.on_target_self.mean()), 4),
        "mean_on_target_gold": round(float(sub.on_target_gold.mean()), 4),
        "mean_abs_gap": round(float((sub.on_target_self - sub.on_target_gold).abs().mean()), 4),
        "note": ("where the own-patch set is a single gold file the two metrics should nearly "
                 "agree; a large gap would mean one definition is broken"),
    }

    # ---- E. what the self-referential metric actually measures --------------------
    # Both proposed mechanisms failed: "confident wrongness" is falsified (lost runs score
    # slightly LOWER than wrong-fix runs) and standardising over patch width does not remove the
    # inversion -- the gap is largest in the narrowest stratum, where breadth cannot explain it.
    # The remaining candidate is FIXATION: the metric is high whenever a run concentrates its
    # edits on one file, whether or not that file is the right one, and failed runs concentrate.
    counts = (ed.assign(b=ed.base)
                .groupby(["run_id", "b"]).size().rename("k").reset_index())
    tot = counts.groupby("run_id").k.sum()
    top = counts.groupby("run_id").k.max()
    foc = (top / tot).rename("fixation").reset_index()
    d = d.merge(foc, on="run_id", how="left")
    fc = d.groupby("reward").fixation.mean()
    # does concentration explain the self-referential score?
    r_self_fix = float(np.corrcoef(d.on_target_self, d.fixation)[0, 1])
    r_gold_fix = float(np.corrcoef(d.on_target_gold, d.fixation)[0, 1])
    out["mechanisms"]["fixation"] = {
        "claim": ("the self-referential metric rewards concentrating edits on one file "
                  "(fixation) rather than aiming at the correct file"),
        "fixation_solved": round(float(fc.loc[1]), 4),
        "fixation_failed": round(float(fc.loc[0]), 4),
        "fixation_delta_solved_minus_failed": round(float(fc.loc[1] - fc.loc[0]), 4),
        "fixation_lost_runs": round(float(d.loc[(d.reward == 0) & (d.ever_touched_gold == 0),
                                                "fixation"].mean()), 4),
        "fixation_wrongfix_runs": round(float(d.loc[(d.reward == 0) & (d.ever_touched_gold == 1),
                                                    "fixation"].mean()), 4),
        "corr_on_target_self_vs_fixation": round(r_self_fix, 4),
        "corr_on_target_gold_vs_fixation": round(r_gold_fix, 4),
        "mean_n_edit_solved": round(float(d.loc[d.reward == 1, "n_edit"].mean()), 2),
        "mean_n_edit_failed": round(float(d.loc[d.reward == 0, "n_edit"].mean()), 2),
        "mean_distinct_files_solved": round(
            float(d.loc[d.reward == 1, "n_distinct_files"].mean()), 3),
        "mean_distinct_files_failed": round(
            float(d.loc[d.reward == 0, "n_distinct_files"].mean()), 3),
        "reading": ("if corr(self, fixation) >> corr(gold, fixation), the self-referential "
                    "metric is mostly a fixation measure"),
    }
    # standardised self delta, to show breadth does not rescue it either
    std_s_self = std_f_self = 0.0
    for k, g in d.groupby("pw"):
        s2, f2 = g[g.reward == 1], g[g.reward == 0]
        if len(s2) < 30 or len(f2) < 30:
            continue
        wt = float(w.get(k, 0.0))
        std_s_self += wt * float(s2.on_target_self.mean())
        std_f_self += wt * float(f2.on_target_self.mean())
    out["mechanisms"]["patch_breadth"]["standardised_self_delta"] = round(std_s_self - std_f_self, 4)
    out["mechanisms"]["patch_breadth"]["pooled_self_delta"] = round(
        float(d.loc[d.reward == 1, "on_target_self"].mean()
              - d.loc[d.reward == 0, "on_target_self"].mean()), 4)

    # ---- verdict ------------------------------------------------------------------
    cw = out["mechanisms"]["confident_wrongness"]
    pb = out["mechanisms"]["patch_breadth"]
    out["verdict"] = {
        "confident_wrongness_supported": bool(
            cw["delta_lost_minus_wrongfix"] > 0
            and cw["delta_ci95"][0] > 0),
        "self_referential_metric_inverts_sign": bool(
            d.loc[d.reward == 1, "on_target_self"].mean()
            < d.loc[d.reward == 0, "on_target_self"].mean()),
        "independent_metric_inverts_back": bool(pooled_s > pooled_f),
        "composition_share_of_pooled_gap": (
            None if abs(pooled_s - pooled_f) < 1e-9 else
            round(1 - (pb["standardised_gold_delta"] / (pooled_s - pooled_f)), 4)
            if (pooled_s - pooled_f) != 0 else None),
    }
    v = out["verdict"]
    print("\n=== VERDICT ===")
    print(f"  self-referential metric: solved {d.loc[d.reward==1,'on_target_self'].mean():.4f} "
          f"vs failed {d.loc[d.reward==0,'on_target_self'].mean():.4f} "
          f"-> inverts: {v['self_referential_metric_inverts_sign']}")
    print(f"  independent gold metric: solved {pooled_s:.4f} vs failed {pooled_f:.4f} "
          f"-> inverts back: {v['independent_metric_inverts_back']}")
    print(f"  confident wrongness: lost runs score {cw['on_target_self_lost_runs']:.4f} vs "
          f"wrong-fix {cw['on_target_self_wrong_fix_runs']:.4f} "
          f"-> supported: {v['confident_wrongness_supported']}")
    print(f"  standardised gold delta {pb['standardised_gold_delta']:+.4f} vs pooled "
          f"{pb['pooled_gold_delta_solved_minus_failed']:+.4f}")

    (RES / "metric_artifact.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"\nwrote {RES / 'metric_artifact.json'}")


if __name__ == "__main__":
    main()
