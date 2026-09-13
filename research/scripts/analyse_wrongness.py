"""The headline analysis: do agents fail by being WRONG rather than LOST?

Why this script exists
----------------------
The frozen study reports that failed runs aim a *higher* share of their edits at the file that
ends up in their patch (0.620) than solved runs do (0.576), p = 3.3e-4.  Read naively that says
"agents do not fail by mis-locating the bug".

But the frozen ``on_target`` is computed against **the run's own final patch**
(``patch_files`` comes from that same run), which makes it a statement about *patch breadth*
rather than about localisation: a run that edits one file and patches that one file scores 1.0
whether or not it fixed anything.  So the reversal could be pure artefact.

This script therefore computes a target that is independent of the run:

  ``on_target_gold``   share of the run's edit steps aimed at a file in the instance's GOLD patch
  ``ever_touched_gold`` whether the run ever edited a gold file at all

and then does the two things the headline needs:

  1. Re-tests the reversal against the independent target, with run length, edit breadth and
     own-patch breadth controlled (within-instance pairing, and matched comparisons).
  2. Decomposes failure into the two mechanical classes the claim is about:
        LOST      failed, never edited any gold file
        WRONG_FIX failed, did edit a gold file
     and reports what share of failures each is, per model and per corpus.

Nothing here looks at content quality: "found the file" and "fixed the bug" are different
questions, and keeping them apart is the entire point.
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


def patch_basenames(patch_files: str) -> set:
    out = set()
    for tok in str(patch_files or "").split():
        tok = tok.strip()
        if tok:
            out.add(Path(tok).name)
    return out


def bonf(p: float, n: int) -> float:
    return min(1.0, p * n)


def wilcoxon(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import wilcoxon as w

    if len(a) < 5 or len(a) != len(b):
        return float("nan")
    if np.allclose(a, b):
        return float("nan")
    try:
        return float(w(a, b).pvalue)
    except Exception:
        return float("nan")


def boot_mean(x: np.ndarray, n: int = 2000) -> tuple:
    if len(x) == 0:
        return (float("nan"), float("nan"))
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    m = x[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def per_run_table(corpus: str = "nebius") -> pd.DataFrame:
    """One row per run: targeting shares under both definitions, plus the confound controls."""
    steps_p = STEPS / corpus / "steps.parquet"
    runs_p = STEPS / corpus / "runs.parquet"
    cols = ["run_id", "task", "model", "reward", "step", "is_edit", "file_shown"]
    st = pd.read_parquet(steps_p, columns=cols)
    ed = st[st.is_edit == 1].copy()
    ed["base"] = ed.file_shown.fillna("").apply(lambda s: Path(str(s)).name)
    print(f"  {corpus}: {len(ed):,} edit steps over {ed.run_id.nunique():,} runs")

    rn = pd.read_parquet(runs_p, columns=[
        "run_id", "task", "model", "reward", "n_steps", "n_edit", "patch_files",
        "patch_n_files", "ev_ran", "ev_pass", "ev_fail", "exit_status"])

    # The steps table has no patch_files column.  Joining it in is what makes the
    # self-referential target computable at all; without the join every run silently gets an
    # empty patch set and ``on_target_self`` is identically zero.  That bug was live for one
    # run of this script and produced a plausible-looking "delta 0.0".
    ed = ed.merge(rn[["run_id", "patch_files"]], on="run_id", how="left")
    missing_patch = int(ed.patch_files.isna().sum())
    if missing_patch:
        print(f"  WARNING: {missing_patch:,} edit steps have no patch_files after the join")

    gold = pd.read_parquet(RES / "gold_patches.parquet")
    gold_map = {r.instance_id: set(r.gold_basenames) for r in gold.itertuples(index=False)}

    rows = []
    for run_id, g in ed.groupby("run_id", sort=False):
        own = patch_basenames(g["patch_files"].iloc[0]) if "patch_files" in g else set()
        iid = str(g["task"].iloc[0])
        gset = gold_map.get(iid, set())
        n = len(g)
        if n == 0:
            continue
        bases = g["base"].tolist()
        n_own = sum(1 for b in bases if b and b in own)
        n_gold = sum(1 for b in bases if b and b in gset)
        rows.append({
            "run_id": run_id,
            "instance_id": iid,
            "model": str(g["model"].iloc[0]),
            "reward": int(g["reward"].iloc[0]),
            "n_edit": n,
            "n_distinct_files": len({b for b in bases if b}),
            "on_target_self": n_own / n,
            "on_target_gold": (n_gold / n) if gset else np.nan,
            "ever_touched_gold": (1 if n_gold > 0 else 0) if gset else np.nan,
            "has_gold": bool(gset),
        })
    per_run = pd.DataFrame(rows).merge(
        rn[["run_id", "patch_n_files", "ev_ran", "ev_pass", "ev_fail", "exit_status"]],
        on="run_id", how="left")
    return per_run


def paired_within_instance(df: pd.DataFrame, col: str, min_runs: int = 20) -> dict:
    """Wilcoxon over instance means: solved runs vs failed runs on the same instance."""
    d = df[df[col].notna()]
    g = d.groupby(["instance_id", "reward"])[col].mean().unstack()
    if 0 not in g.columns or 1 not in g.columns:
        return {"n_instances": 0}
    g = g.dropna()
    if len(g) < min_runs:
        return {"n_instances": int(len(g))}
    ok, no = g[1].to_numpy(), g[0].to_numpy()
    lo, hi = boot_mean(ok - no)
    return {
        "n_instances": int(len(g)),
        "solved_mean": float(ok.mean()),
        "failed_mean": float(no.mean()),
        "delta": float(ok.mean() - no.mean()),
        "delta_ci95": [lo, hi],
        "p_wilcoxon": wilcoxon(ok, no),
        "frac_instances_solved_higher": float((ok > no).mean()),
    }


def main() -> None:
    out: dict = {"question": "do failed runs localise WORSE (lost) or equally/better (wrong-fix)?",
                 "corpora": {}}

    for corpus in ("nebius",):
        p = STEPS / corpus / "steps.parquet"
        if not p.exists():
            continue
        print(f"\n=== {corpus} ===")
        pr = per_run_table(corpus)
        gold = pr[pr.has_gold].copy()
        print(f"  runs with a gold target: {len(gold):,} of {len(pr):,} "
              f"({len(gold)/len(pr):.1%})")

        # ---------- 1. the reversal, under both definitions -----------------------------
        res = {}
        res["reversal_on_target_self"] = paired_within_instance(pr, "on_target_self")
        res["reversal_on_target_gold"] = paired_within_instance(gold, "on_target_gold")
        res["reversal_ever_touched_gold"] = paired_within_instance(gold, "ever_touched_gold")

        # pooled (run-level) versions too, because the frozen study's headline was pooled and
        # the within-instance test answers a different question
        def pooled(frame, col):
            d = frame[frame[col].notna()]
            g2 = d.groupby("reward")[col].mean()
            if 1 not in g2.index or 0 not in g2.index:
                return {}
            return {"solved": round(float(g2.loc[1]), 4), "failed": round(float(g2.loc[0]), 4),
                    "delta_solved_minus_failed": round(float(g2.loc[1] - g2.loc[0]), 4),
                    "n_solved": int((d.reward == 1).sum()), "n_failed": int((d.reward == 0).sum())}
        res["pooled_on_target_self"] = pooled(pr, "on_target_self")
        res["pooled_on_target_gold"] = pooled(gold, "on_target_gold")
        res["pooled_ever_touched_gold"] = pooled(gold, "ever_touched_gold")

        # ---------- 2. the confound: is breadth different between solved and failed? -----
        def ctrl(frame, col):
            d = frame[frame[col].notna()]
            return {
                "n_edit": d.groupby("reward")[col].size().to_dict(),
                "mean_n_edit": d.groupby("reward").n_edit.mean().round(2).to_dict(),
                "mean_distinct_files": d.groupby("reward").n_distinct_files.mean().round(3).to_dict(),
                "mean_patch_n_files": d.groupby("reward").patch_n_files.mean().round(3).to_dict(),
                "median_n_edit": d.groupby("reward").n_edit.median().to_dict(),
            }

        res["breadth_by_outcome"] = ctrl(gold, "on_target_gold")

        # matched on edit count: compare solved vs failed at the same n_edit
        matched = []
        d = gold.dropna(subset=["on_target_gold"])
        for lo, hi in [(1, 3), (4, 7), (8, 15), (16, 30), (31, 10 ** 6)]:
            b = d[(d.n_edit >= lo) & (d.n_edit <= hi)]
            if b.reward.nunique() < 2:
                continue
            m = b.groupby("reward").on_target_gold.agg(["mean", "size"])
            matched.append({"n_edit_bin": f"{lo}-{hi if hi < 10**6 else '+'}",
                            "solved": round(float(m.loc[1, "mean"]), 4),
                            "failed": round(float(m.loc[0, "mean"]), 4),
                            "n_solved": int(m.loc[1, "size"]), "n_failed": int(m.loc[0, "size"])})
        res["on_target_gold_by_matched_edit_count"] = matched

        # ---------- 2b. THE MECHANISM ------------------------------------------------
        # Hypothesis: the self-referential target is inflated for failed runs because failed
        # runs write BROADER patches, so more of their files sit inside their own patch set.
        # If that is the mechanism, the spurious reversal must vanish among runs whose patch
        # touches exactly one file -- there the self-referential set IS the gold-like set.
        strat = []
        for k, g3 in pr.groupby(pr.patch_n_files.fillna(0).clip(upper=3)):
            if g3.reward.nunique() < 2:
                continue
            m = g3.groupby("reward")[["on_target_self", "on_target_gold"]].mean()
            n = g3.groupby("reward").size()
            strat.append({
                "patch_n_files": int(k),
                "n_solved": int(n.get(1, 0)), "n_failed": int(n.get(0, 0)),
                "on_target_self_solved": round(float(m.loc[1, "on_target_self"]), 4),
                "on_target_self_failed": round(float(m.loc[0, "on_target_self"]), 4),
                "self_delta_solved_minus_failed": round(
                    float(m.loc[1, "on_target_self"] - m.loc[0, "on_target_self"]), 4),
                "on_target_gold_solved": round(float(m.loc[1, "on_target_gold"]), 4)
                if not np.isnan(m.loc[1, "on_target_gold"]) else None,
                "on_target_gold_failed": round(float(m.loc[0, "on_target_gold"]), 4)
                if not np.isnan(m.loc[0, "on_target_gold"]) else None,
            })
        res["mechanism_patch_breadth_strata"] = strat
        res["patch_breadth_by_outcome"] = {
            "mean_patch_n_files_solved": round(float(pr.loc[pr.reward == 1, "patch_n_files"].mean()), 3),
            "mean_patch_n_files_failed": round(float(pr.loc[pr.reward == 0, "patch_n_files"].mean()), 3),
            "frac_broad_patch_gt1_solved": round(float((pr.loc[pr.reward == 1, "patch_n_files"] > 1).mean()), 4),
            "frac_broad_patch_gt1_failed": round(float((pr.loc[pr.reward == 0, "patch_n_files"] > 1).mean()), 4),
        }

        # ---------- 3. the failure decomposition (the headline quantity) ----------------
        fails = pr[(pr.reward == 0) & pr.has_gold]
        lost = int((fails.ever_touched_gold == 0).sum())
        wrong = int((fails.ever_touched_gold == 1).sum())
        res["failure_decomposition"] = {
            "n_failed_runs_with_gold": int(len(fails)),
            "lost_never_touched_gold": lost,
            "wrong_fix_touched_gold": wrong,
            "frac_wrong_fix": round(wrong / max(len(fails), 1), 4),
            "note": ("WRONG_FIX = failed run that DID edit a gold file; LOST = failed run that "
                     "never edited one. Neither says the edit was correct -- only that the agent "
                     "was in the right place."),
        }
        # same split for solved runs, as a sanity check that the measure is not degenerate
        s = pr[(pr.reward == 1) & pr.has_gold]
        res["solved_touched_gold"] = {
            "n": int(len(s)), "frac_touched_gold": round(float(s.ever_touched_gold.mean()), 4)
        }

        # per model
        per_model = {}
        for m, g2 in pr[pr.has_gold].groupby("model"):
            f2 = g2[g2.reward == 0]
            per_model[m] = {
                "n_runs": int(len(g2)),
                "solve_rate": round(float(g2.reward.mean()), 4),
                "n_failed": int(len(f2)),
                "frac_wrong_fix_among_failed": round(float(f2.ever_touched_gold.mean()), 4)
                if len(f2) else None,
            }
        res["per_model"] = per_model

        # ---------- 4. gold-patch width as a difficulty control ------------------------
        w = gold.merge(pd.read_parquet(RES / "gold_patches.parquet")[
            ["instance_id", "n_gold_files"]], on="instance_id", how="left")
        bywidth = []
        for k, g3 in w.groupby(w.n_gold_files.clip(upper=4)):
            f3 = g3[g3.reward == 0]
            bywidth.append({"n_gold_files": int(k), "n_runs": int(len(g3)),
                            "solve_rate": round(float(g3.reward.mean()), 4),
                            "frac_wrong_fix_among_failed": round(float(f3.ever_touched_gold.mean()), 4)
                            if len(f3) else None})
        res["by_gold_patch_width"] = bywidth

        out["corpora"][corpus] = res

    # ---------- verdict ---------------------------------------------------------------
    nb = out["corpora"].get("nebius", {})
    rg = nb.get("reversal_on_target_gold", {})
    rs = nb.get("reversal_on_target_self", {})
    fd = nb.get("failure_decomposition", {})
    out["verdict"] = {
        "reversal_replicates_on_self_referential_target": bool(rs.get("delta", 0) < 0),
        "reversal_on_independent_gold_target": {
            "solved": rg.get("solved_mean"), "failed": rg.get("failed_mean"),
            "p": rg.get("p_wilcoxon")},
        "headline": (f"{fd.get('frac_wrong_fix', float('nan')):.1%} of failed runs that have a "
                     f"known gold patch DID edit a gold file; {fd.get('lost_never_touched_gold')} "
                     f"never did (n={fd.get('n_failed_runs_with_gold')})"),
    }

    (RES / "wrongness.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=float),
                                        encoding="utf-8")
    print("\n" + json.dumps(out["verdict"], indent=2, ensure_ascii=False, default=float))
    print(f"\nwrote {RES / 'wrongness.json'}")


if __name__ == "__main__":
    main()
