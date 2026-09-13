"""Cross-scaffold replication of the study's two mechanical results.

Runs on the step/run tables written by ``scripts/xscaffold_extract.py`` and answers,
per corpus, the three questions the replication asks:

1. **Footer.**  Does a step observation carry the SWE-agent editor footer
   ``[File: /abs/path.py (123 lines total)]`` -- the marker that makes every edit
   labelable -- or any equivalent structural marker naming the edited file with a
   measurable size?  Reported with the literal string found, or ``absent``.

2. **Taxonomy.**  The three-class edit taxonomy of the frozen study, computed by
   the *same rules* as ``scripts/analyse_dead_end.py``:

       kept     >= 1 introduced line hash survives into the run's final patch
       revised  nothing survives, but a later edit in the run touches the same file
       dead_end nothing survives, and no later edit touches that file again

   Reference (SWE-agent / Nebius, 236,137 edits): kept .157 / revised .652 / dead_end .191.

3. **Gold target.**  An independent target per instance: the gold patch basenames in
   ``results/rebuild/gold_patches.parquet``.  Per run,

       ever_touched_gold  did any edit step aim at a file in the instance's gold set
       on_target_gold     share of edit steps that did

   reported solved vs failed, pooled and within-instance (paired), alongside the
   study's own patch-derived ``on_target`` for comparison.

Writes ``results/rebuild/xscaffold_replication.json``.  Creates no other file and
modifies nothing.

    python scripts/xscaffold_analyse.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed" / "xscaffold"
OUT = ROOT / "results" / "rebuild"

# the frozen study's headline numbers, for the comparison column
REFERENCE = {
    "swe_agent_nebius": {
        "n_edits": 236137, "n_runs": 25681,
        "kept": 0.15734086568390385,
        "revised": 0.6515751449370493,
        "dead_end": 0.19108398937904691,
        "footer_rate_of_edit_steps": 0.958,
        "source": "results/rebuild/dead_end.json (SWE-agent / nebius SWE-agent-trajectories)",
    },
}

CORPORA_ORDER = ["nebius_openhands", "swegym", "pi", "smithmarines", "thoughtworks"]

LABELS = {
    "nebius_openhands": "OpenHands — nebius/SWE-rebench-openhands-trajectories",
    "swegym": "OpenHands — SWE-Gym/OpenHands-Sampled-Trajectories",
    "pi": "PI agent — whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces",
    "smithmarines": "mini-swe-agent-plus — Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k",
    "thoughtworks": "multi-framework — thoughtworks/agentic-coding-trajectories",
}


def _basename(s: str) -> str:
    return s.rsplit("/", 1)[-1] if s else ""


SCRATCH_NAME = re.compile(
    r"^(?:repro\w*|tmp\w*|temp\w*|scratch\w*|debug\w*|check_\w+|verify_\w+|demo\w*|"
    r"example\w*|test_\w+)", re.I)


def patch_basenames_from_str(s: str) -> set:
    return {_basename(x) for x in str(s or "").split() if x}


def wilcoxon(a: np.ndarray) -> Optional[float]:
    if len(a) < 5:
        return None
    try:
        from scipy import stats
        if np.all(a == 0):
            return None
        return float(stats.wilcoxon(a).pvalue)
    except Exception:
        return None


def taxonomy(ed: pd.DataFrame) -> Dict[str, Any]:
    """The frozen study's three-class labelling, applied to one corpus's edit table."""
    if ed.empty:
        return {"n_edits": 0}
    ed = ed.copy()
    if "instance_id" not in ed.columns and "task" in ed.columns:
        ed["instance_id"] = ed["task"]
    ed = ed.sort_values(["run_id", "step"]).reset_index(drop=True)
    patched = ed["patch_hashes"].fillna("").apply(
        lambda s: set(str(s).split()) if s else set())
    ed = ed.assign(
        hit=[len(set(str(a).split()) & p) > 0 if a else False
             for a, p in zip(ed["added_hashes"].fillna(""), patched)])

    later = np.zeros(len(ed), dtype=bool)
    for _rid, g in ed.groupby("run_id", sort=False):
        idx = g.index.to_numpy()
        files = g["file"].astype(str).to_numpy()
        for k in range(len(idx) - 1):
            cur = files[k]
            later[idx[k]] = bool(cur) and bool((files[k + 1:] == cur).any())
    ed = ed.assign(revisited_later=later)
    ed = ed.assign(
        kept=ed["hit"].astype(float),
        revised=((~ed["hit"]) & ed["revisited_later"]).astype(float),
        dead_end=((~ed["hit"]) & (~ed["revisited_later"])).astype(float),
    )

    n = len(ed)
    res: Dict[str, Any] = {
        "n_edits": int(n), "n_runs": int(ed.run_id.nunique()),
        "kept_rate": float(ed["kept"].mean()),
        "revised_rate": float(ed["revised"].mean()),
        "dead_end_rate": float(ed["dead_end"].mean()),
        "wasted_pooled": float(1 - ed["kept"].mean()),
        "decomposition_check": float(ed["kept"].mean() + ed["revised"].mean()
                                     + ed["dead_end"].mean()),
        "mean_edits_per_run": float(ed.groupby("run_id").size().mean()),
        "volume": {
            "kept_edits": int(ed["kept"].sum()),
            "revised_edits": int(ed["revised"].sum()),
            "dead_end_edits": int(ed["dead_end"].sum()),
            "mean_dead_end_per_run": float(ed.groupby("run_id")["dead_end"].sum().mean()),
            "frac_runs_with_no_dead_end": float(
                (ed.groupby("run_id")["dead_end"].sum() == 0).mean()),
        },
    }
    un = ed[~ed["revisited_later"]]
    if len(un) > 0:
        res["unsuperseded_subset"] = {"n": int(len(un)),
                                      "kept_rate": float(un["kept"].mean())}

    # A mechanical diagnostic for why `kept` differs so much between scaffolds: the final
    # patch of these corpora is the whole workspace diff, so a scratch file the agent wrote
    # and left behind counts as "shipped".  This measures the size of that channel without
    # judging anything: a *scratch-named* file is one whose basename starts with
    # repro/tmp/temp/scratch/debug/check/verify/demo/example or test_.
    base = ed["file"].fillna("").str.rsplit("/", n=1).str[-1]
    scr = base.str.match(SCRATCH_NAME, na=False)
    res["scratch_files"] = {
        "share_of_all_edits": float(scr.mean()),
        "share_of_kept_edits": float(scr[ed["kept"] == 1].mean()) if int(ed["kept"].sum()) else None,
        "share_of_dead_end_edits": float(scr[ed["dead_end"] == 1].mean())
        if int(ed["dead_end"].sum()) else None,
        "note": ("scratch-named = basename matches repro*/tmp*/temp*/scratch*/debug*/check*/"
                 "verify*/demo*/example*/test_*; these are files the agent itself created and "
                 "left in the tree, so they land in the workspace diff without being the "
                 "intended change"),
    }
    res["run_shape"] = {
        "mean_edits_per_run": float(ed.groupby("run_id").size().mean()),
        "median_edits_per_run": float(ed.groupby("run_id").size().median()),
        "frac_runs_editing_one_file_only": float(
            (ed.groupby("run_id")["file"].nunique() == 1).mean()),
        "mean_distinct_files_per_run": float(ed.groupby("run_id")["file"].nunique().mean()),
    }

    # within-instance relation to the outcome, exactly as analyse_dead_end.within_instance
    if ed["resolved"].notna().any() and ed["resolved"].nunique(dropna=True) > 1:
        per_run = ed.groupby(["instance_id", "run_id"]).agg(
            rate=("kept", "mean"), dead=("dead_end", "mean"),
            reward=("resolved", "max")).reset_index()
        wi: Dict[str, Any] = {}
        for col in ("rate", "dead"):
            deltas = []
            for _inst, g in per_run.groupby("instance_id"):
                if g["reward"].nunique() < 2:
                    continue
                ok = g.loc[g.reward == 1, col]
                no = g.loc[g.reward == 0, col]
                if len(ok) and len(no):
                    deltas.append(float(ok.mean() - no.mean()))
            if len(deltas) >= 5:
                a = np.asarray(deltas)
                wi[col] = {"n_instances": int(len(a)), "mean_delta": float(a.mean()),
                           "median_delta": float(np.median(a)),
                           "frac_positive": float((a > 0).mean()),
                           "p": wilcoxon(a)}
        res["within_instance"] = wi
    return res


def gold_metrics(ed: pd.DataFrame, gold_by_instance: Dict[str, set]) -> Dict[str, Any]:
    """ever_touched_gold / on_target_gold per run, against an independent gold target."""
    if ed.empty:
        return {"n_runs": 0}
    ed = ed.copy()
    ed["base"] = ed["file"].fillna("").apply(_basename)
    ed["gold_set"] = ed["instance_id"].map(lambda i: gold_by_instance.get(str(i), set()))
    ed["is_gold"] = [bool(b) and b in s for b, s in zip(ed["base"], ed["gold_set"])]
    per_run = ed.groupby(["run_id", "instance_id", "resolved"], dropna=False).agg(
        n_edit=("is_gold", "size"), n_gold=("is_gold", "sum")).reset_index()
    per_run["ever_touched_gold"] = (per_run.n_gold > 0).astype(float)
    per_run["on_target_gold"] = per_run.n_gold / per_run.n_edit
    per_run["has_gold"] = per_run["instance_id"].map(
        lambda i: str(i) in gold_by_instance).astype(int)

    res: Dict[str, Any] = {
        "n_runs_with_edits": int(len(per_run)),
        "n_instances_with_edits": int(per_run.instance_id.nunique()),
        "n_instances_with_gold": int(per_run.loc[per_run.has_gold == 1, "instance_id"].nunique()),
        "n_runs_with_gold": int(per_run.has_gold.sum()),
        "ever_touched_gold_all_runs": float(per_run.ever_touched_gold.mean()),
        "on_target_gold_all_runs": float(per_run.on_target_gold.mean()),
    }
    g = per_run[per_run.has_gold == 1]
    if len(g) == 0:
        res["note"] = "no instance of this corpus has a gold patch in gold_patches.parquet"
        return res
    res["pooled"] = {
        "n_runs": int(len(g)),
        "ever_touched_gold": float(g.ever_touched_gold.mean()),
        "on_target_gold": float(g.on_target_gold.mean()),
        "median_on_target_gold": float(g.on_target_gold.median()),
    }
    if g["resolved"].notna().any() and g["resolved"].nunique(dropna=True) > 1:
        ok = g[g.resolved == 1]
        no = g[g.resolved == 0]
        res["pooled"]["solved"] = {
            "n": int(len(ok)), "ever_touched_gold": float(ok.ever_touched_gold.mean()),
            "on_target_gold": float(ok.on_target_gold.mean())}
        res["pooled"]["failed"] = {
            "n": int(len(no)), "ever_touched_gold": float(no.ever_touched_gold.mean()),
            "on_target_gold": float(no.on_target_gold.mean())}
        res["pooled"]["delta_solved_minus_failed"] = {
            "ever_touched_gold": float(ok.ever_touched_gold.mean() - no.ever_touched_gold.mean()),
            "on_target_gold": float(ok.on_target_gold.mean() - no.on_target_gold.mean()),
        }

        # within-instance paired: only instances with both a solved and a failed run
        paired_rows = []
        for iid, gi in g.groupby("instance_id"):
            if gi["resolved"].nunique() < 2:
                continue
            a = gi[gi.resolved == 1]
            b = gi[gi.resolved == 0]
            if len(a) and len(b):
                paired_rows.append({
                    "instance_id": iid,
                    "n_solved": len(a), "n_failed": len(b),
                    "ever_ok": a.ever_touched_gold.mean(), "ever_no": b.ever_touched_gold.mean(),
                    "ontgt_ok": a.on_target_gold.mean(), "ontgt_no": b.on_target_gold.mean(),
                })
        pr = pd.DataFrame(paired_rows)
        if len(pr) >= 5:
            d_ever = (pr.ever_ok - pr.ever_no).to_numpy()
            d_ont = (pr.ontgt_ok - pr.ontgt_no).to_numpy()
            res["within_instance"] = {
                "n_instances": int(len(pr)),
                "n_runs": int(pr.n_solved.sum() + pr.n_failed.sum()),
                "ever_touched_gold": {
                    "solved": float(pr.ever_ok.mean()), "failed": float(pr.ever_no.mean()),
                    "mean_delta": float(d_ever.mean()),
                    "frac_positive": float((d_ever > 0).mean()),
                    "p": wilcoxon(d_ever)},
                "on_target_gold": {
                    "solved": float(pr.ontgt_ok.mean()), "failed": float(pr.ontgt_no.mean()),
                    "mean_delta": float(d_ont.mean()),
                    "frac_positive": float((d_ont > 0).mean()),
                    "p": wilcoxon(d_ont)},
            }
        else:
            res["within_instance"] = {"n_instances": int(len(pr)),
                                      "note": "too few contested instances"}
    else:
        res["pooled"]["note"] = ("this corpus has a single outcome value, so solved-vs-failed "
                                 "cannot be contrasted")
    return res


def own_patch_target(ed: pd.DataFrame) -> Dict[str, Any]:
    """The study's *existing* target definition, for comparison: the run's own final patch."""
    if ed.empty:
        return {"n_runs": 0}
    ed = ed.copy()
    ed["base"] = ed["file"].fillna("").apply(_basename)
    ed["pbase"] = ed["patch_files"].fillna("").apply(patch_basenames_from_str)
    ed["in_patch"] = [bool(b) and b in s for b, s in zip(ed["base"], ed["pbase"])]
    per_run = ed.groupby(["run_id", "resolved"], dropna=False).agg(
        n_edit=("in_patch", "size"), n_p=("in_patch", "sum")).reset_index()
    per_run["on_target_own_patch"] = per_run.n_p / per_run.n_edit
    out: Dict[str, Any] = {"n_runs": int(len(per_run)),
                           "mean_on_target_own_patch": float(per_run.on_target_own_patch.mean())}
    if per_run["resolved"].notna().any() and per_run["resolved"].nunique(dropna=True) > 1:
        out["solved"] = float(per_run.loc[per_run.resolved == 1, "on_target_own_patch"].mean())
        out["failed"] = float(per_run.loc[per_run.resolved == 0, "on_target_own_patch"].mean())
        out["delta_solved_minus_failed"] = out["solved"] - out["failed"]
    return out


def test_coverage(st: pd.DataFrame) -> Dict[str, Any]:
    n = len(st)
    if n == 0:
        return {"n_steps": 0}
    out = {
        "n_steps": int(n),
        "n_runs": int(st.run_id.nunique()),
        "strict_step_rate": float(st.test_strict.mean()),
        "loose_step_rate": float(st.test_loose.mean()),
        "runs_with_any_test_step": float(
            st.groupby("run_id")["test_loose"].max().mean()),
        "runs_with_strict_summary": float(
            st.groupby("run_id")["test_strict"].max().mean()),
        "exit_code_step_rate": float(st.exit_code.notna().mean()),
        "runs_with_exit_code": float(st.groupby("run_id")["exit_code"].apply(
            lambda s: s.notna().any()).mean()),
    }
    return out


def footer_coverage(st: pd.DataFrame) -> Dict[str, Any]:
    n = len(st)
    if n == 0:
        return {"n_steps": 0}
    ed = st[st.is_edit == 1]
    return {
        "n_steps": int(n),
        "n_edit_steps": int(len(ed)),
        "footer_step_rate": float(st.has_footer.mean()),
        "footer_edit_step_rate": float(ed.has_footer.mean()) if len(ed) else None,
        "lines_total_step_rate": float(st.has_lines_total.mean()),
        "catn_step_rate": float(st.has_catn.mean()),
        "truncated_step_rate": float(st.truncated.mean()),
        "runs_with_any_footer": float(st.groupby("run_id")["has_footer"].max().mean()),
        "edits_with_named_target_rate": (float((ed["file"].astype(str).str.len() > 0).mean())
                                         if len(ed) else None),
    }


# The study's *own* gold-target result, from results/rebuild/wrongness.json.  On the
# self-referential target (the run's own final patch) failed runs look better localised;
# on the independent gold target the sign REVERSES -- solved runs localise better.  That
# reversal is the current spine, so "the gold-target result replicates" below means
# "solved runs score higher than failed runs, on both gold measures".
GOLD_REFERENCE = {
    "source": "results/rebuild/wrongness.json (SWE-agent / nebius SWE-agent-trajectories)",
    "direction": "solved > failed",
    "pooled_on_target_gold": {"solved": 0.4771, "failed": 0.4069, "delta": 0.0703,
                              "n_solved": 3308, "n_failed": 16327},
    "pooled_ever_touched_gold": {"solved": 0.9819, "failed": 0.6705, "delta": 0.3114,
                                 "n_solved": 3308, "n_failed": 16327},
    "within_instance_on_target_gold": {"solved": 0.4959484844823932,
                                       "failed": 0.4476850143350839, "delta": 0.048263470147309306,
                                       "p": 0.007006189656934297, "n_instances": 228},
    "within_instance_ever_touched_gold": {"solved": 0.9699588354303266,
                                          "failed": 0.7799417087635024,
                                          "delta": 0.19001712666682413,
                                          "p": 1.608942202024541e-23, "n_instances": 228},
    "self_referential_counterpoint": {"delta_solved_minus_failed": -0.0765,
                                      "note": "the run's own patch; the opposite sign"},
}


def verdicts(entry: Dict[str, Any], ref: Dict[str, Any]) -> Dict[str, Any]:
    """Mechanical verdicts, so the replication claim is not a matter of taste.

    * footer   -- present if the SWE-agent footer covers >1% of steps
    * taxonomy -- L1 distance between this corpus's (kept, revised, dead_end) vector and the
                  SWE-agent reference vector: <=0.20 replicates, <=0.40 partially, else not
    * gold     -- replicates if failed runs localise at least as well as solved ones on both
                  gold measures, in the pooled and (where available) paired comparison
    * tests    -- present if a parseable pass/fail summary appears on >1% of steps
    """
    m = entry.get("markers", {})
    t = entry.get("taxonomy", {})
    g = entry.get("gold", {})
    tc = entry.get("test_outcomes", {})
    out: Dict[str, Any] = {}

    fr = m.get("footer_step_rate") or 0.0
    lt = m.get("lines_total_step_rate") or 0.0
    if fr > 0.01:
        out["footer"] = (f"PRESENT on {fr:.1%} of steps — the study's instrument ports "
                         f"unchanged")
    elif lt > 0:
        out["footer"] = (f"ABSENT as `[File: … (N lines total)]`; a size is stated on "
                         f"{lt:.3%} of steps only (an error path), so it cannot label edits")
    else:
        out["footer"] = "ABSENT — no observation states a file's line count"

    if t.get("n_edits"):
        vec = [t["kept_rate"], t["revised_rate"], t["dead_end_rate"]]
        rvec = [ref.get("kept", ref.get("kept_rate")), ref.get("revised", ref.get("revised_rate")),
                ref.get("dead_end", ref.get("dead_end_rate"))]
        rvec = [0.0 if x is None else float(x) for x in rvec]
        l1 = float(sum(abs(a - b) for a, b in zip(vec, rvec)))
        out["taxonomy_l1_vs_swe_agent"] = l1
        out["taxonomy_vector"] = vec
        if l1 <= 0.20:
            label = "REPLICATES"
        elif l1 <= 0.40:
            label = "PARTIALLY REPLICATES"
        else:
            label = "DOES NOT REPLICATE"
        es = entry.get("patch_coverage", {})
        out["taxonomy"] = (
            f"{label} — kept {t['kept_rate']:.3f} / revised {t['revised_rate']:.3f} / "
            f"dead_end {t['dead_end_rate']:.3f} (L1 {l1:.3f} from the SWE-agent vector), "
            f"over {t['n_edits']:,} edits in {t['n_runs']:,} runs, i.e. "
            f"{es.get('edit_coverage', float('nan')):.1%} of this corpus's edit steps")
    else:
        out["taxonomy"] = ("NOT COMPUTABLE — this corpus never exposes a final patch, so "
                           "`kept` has no definition; the revision/dead-end split alone "
                           "cannot be validated")

    if "pooled" in g and "solved" in g.get("pooled", {}):
        p = g["pooled"]
        d = p["delta_solved_minus_failed"]
        wi = g.get("within_instance", {})
        sig = ""
        if wi.get("on_target_gold"):
            w = wi["on_target_gold"]
            sig = (f"; within-instance on {wi['n_instances']} contested instances "
                   f"{w['solved']:.3f} solved vs {w['failed']:.3f} failed "
                   f"(delta {w['mean_delta']:+.3f}, p={w['p']})")
        if d["on_target_gold"] > 0 and d["ever_touched_gold"] > 0:
            label = "REPLICATES"
        elif d["on_target_gold"] < 0 and d["ever_touched_gold"] < 0:
            label = "INVERTED"
        else:
            label = "MIXED"
        thin = ""
        if p["solved"]["n"] < 50 or p["failed"]["n"] < 50:
            thin = (" — but the gold-covered sample is far too small to carry the claim "
                    f"({p['solved']['n']} solved / {p['failed']['n']} failed runs)")
        out["gold"] = (
            f"{label} — pooled solved runs on_target_gold {p['solved']['on_target_gold']:.3f} "
            f"vs failed {p['failed']['on_target_gold']:.3f} (delta {d['on_target_gold']:+.3f}); "
            f"ever_touched_gold {p['solved']['ever_touched_gold']:.3f} vs "
            f"{p['failed']['ever_touched_gold']:.3f} (delta {d['ever_touched_gold']:+.3f})"
            f"{sig}{thin}")
    elif "pooled" in g:
        p = g["pooled"]
        out["gold"] = (f"POOLED ONLY — {p['n_runs']:,} runs on gold-covered instances: "
                       f"ever_touched_gold {p['ever_touched_gold']:.3f}, "
                       f"on_target_gold {p['on_target_gold']:.3f}; no outcome contrast "
                       f"available in this corpus")
    else:
        out["gold"] = ("NOT COMPUTABLE — no instance of this corpus has a gold patch in "
                       "gold_patches.parquet")

    if tc.get("n_steps"):
        out["tests"] = (
            f"strict pytest/unittest summary on {tc['strict_step_rate']:.2%} of steps "
            f"({tc['loose_step_rate']:.2%} with any test marker, including framework "
            f"summaries); {tc['runs_with_strict_summary']:.1%} of runs contain one")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    # ---- independent gold target -------------------------------------------------------
    gold = pd.read_parquet(OUT / "gold_patches.parquet")
    gold_by_instance: Dict[str, set] = {}
    for r in gold.itertuples(index=False):
        try:
            names = json.loads(r.gold_basenames) if isinstance(r.gold_basenames, str) \
                else list(r.gold_basenames)
        except Exception:
            names = []
        gold_by_instance[str(r.instance_id)] = {_basename(x) for x in names if x}
    print(f"gold patches: {len(gold_by_instance):,} instances")

    cal = None
    cal_path = OUT / "xscaffold_calibration.json"
    if cal_path.exists():
        cal = json.loads(cal_path.read_text(encoding="utf-8"))

    result: Dict[str, Any] = {
        "reference": REFERENCE,
        "gold_reference": GOLD_REFERENCE,
        "gold_source": {
            "file": "results/rebuild/gold_patches.parquet",
            "n_instances": len(gold_by_instance),
            "note": ("gold basenames come from each dataset's own patch field and do not "
                     "depend on any agent run"),
        },
        "instrument_check": (cal or {}),
        "corpora": {},
    }

    keys = [args.corpus] if args.corpus else CORPORA_ORDER
    for key in keys:
        sp, rp = PROC / f"{key}_steps.parquet", PROC / f"{key}_runs.parquet"
        if not sp.exists():
            print(f"{key}: no extracted table — run scripts/xscaffold_extract.py --corpus {key}")
            continue
        try:
            st = pd.read_parquet(sp)
            rn = pd.read_parquet(rp)
        except Exception as e:      # a corpus still being extracted, or a failed run
            print(f"{key}: cannot read extracted tables ({type(e).__name__}: {str(e)[:120]})")
            continue
        print(f"\n{'='*78}\n{key}  ({LABELS.get(key,'')})\n{'='*78}")
        entry: Dict[str, Any] = {"label": LABELS.get(key, key)}

        # a: footer / structural marker
        entry["markers"] = footer_coverage(st)
        mp = OUT / f"xscaffold_markers_{key}.json"
        if mp.exists():
            entry["markers"].update(json.loads(mp.read_text(encoding="utf-8")).get(key, {}))
        m = entry["markers"]
        print(f"  footer on {m['n_steps']:,} steps: {m['footer_step_rate']:.4%}; "
              f"on {m['n_edit_steps']:,} edit steps: {m['footer_edit_step_rate']}")
        print(f"  edits with a named target file: {m['edits_with_named_target_rate']:.4%}")

        # b: taxonomy (scope made explicit — see the docstring of xscaffold_calibrate.py)
        empty_patch_is_real = key in ("nebius_openhands", "swegym")
        runs_nonempty = set(rn[rn.patch_chars > 0]["run_id"])
        runs_scope = set(rn["run_id"]) if empty_patch_is_real else set(runs_nonempty)
        ed = st[(st.is_edit == 1) & (st.run_id.isin(runs_scope))]
        ed = ed.merge(rn[["run_id", "patch_hashes", "patch_files", "patch_chars"]],
                      on="run_id", how="left")
        entry["patch_coverage"] = {
            "n_runs": int(len(rn)),
            "n_runs_with_patch": int((rn.patch_chars > 0).sum()),
            "run_patch_rate": float((rn.patch_chars > 0).mean()),
            "empty_patch_is_a_real_outcome": bool(empty_patch_is_real),
            "taxonomy_scope": ("every run; a run with an empty patch wrote nothing that could "
                               "ship" if empty_patch_is_real else
                               "runs whose final patch was recovered from the transcript"),
            "n_edits_total": int((st.is_edit == 1).sum()),
            "n_edits_in_scope": int(len(ed)),
            "edit_coverage": float(len(ed) / max(int((st.is_edit == 1).sum()), 1)),
            "patch_sources": rn.patch_source.value_counts().to_dict(),
        }
        pc = entry["patch_coverage"]
        print(f"  runs with a non-empty final patch: {pc['n_runs_with_patch']:,}/"
              f"{pc['n_runs']:,} ({pc['run_patch_rate']:.1%}); taxonomy scope covers "
              f"{pc['edit_coverage']:.1%} of edit steps")

        if len(ed) > 0:
            tx = taxonomy(ed)
            entry["taxonomy"] = tx
            print(f"  TAXONOMY on {tx['n_edits']:,} edits over {tx['n_runs']:,} runs: "
                  f"kept {tx['kept_rate']:.3f} / revised {tx['revised_rate']:.3f} / "
                  f"dead_end {tx['dead_end_rate']:.3f}")
            if empty_patch_is_real:
                tx2 = taxonomy(ed[ed.patch_chars > 0])
                entry["taxonomy_nonempty_patch_runs_only"] = tx2
                print(f"  same, runs with a non-empty patch only ({tx2['n_edits']:,} edits): "
                      f"kept {tx2['kept_rate']:.3f} / revised {tx2['revised_rate']:.3f} / "
                      f"dead_end {tx2['dead_end_rate']:.3f}")
        else:
            entry["taxonomy"] = {"n_edits": 0,
                                 "verdict": "not computable: no run in this corpus exposes a final patch"}
            print("  TAXONOMY: not computable (no final patch)")
        entry["taxonomy_all_edits_note"] = (
            "for the two corpora that ship a patch column (nebius_openhands, swegym) an empty "
            "patch is a real outcome and those runs are *in* scope, exactly as the frozen "
            "SWE-agent pipeline treated them; for the corpora whose patch is recovered from the "
            "transcript, a run with no recovered patch is unmeasurable rather than empty, so it "
            "is out of scope. See patch_coverage.edit_coverage.")

        # c: gold target
        ed_all = st[st.is_edit == 1].merge(
            rn[["run_id", "patch_files", "patch_hashes"]], on="run_id", how="left")
        entry["gold"] = gold_metrics(ed_all, gold_by_instance)
        entry["own_patch_target"] = own_patch_target(ed_all)
        gi = entry["gold"]
        print(f"  gold overlap: {gi.get('n_instances_with_gold',0):,} of "
              f"{gi.get('n_instances_with_edits',0):,} instances with edits "
              f"({gi.get('n_runs_with_gold',0):,} runs)")
        if "pooled" in gi:
            p = gi["pooled"]
            print(f"    pooled ever_touched_gold {p['ever_touched_gold']:.3f}, "
                  f"on_target_gold {p['on_target_gold']:.3f}")
            if "solved" in p:
                print(f"    solved(n={p['solved']['n']}) ever {p['solved']['ever_touched_gold']:.3f} "
                      f"on {p['solved']['on_target_gold']:.3f}  |  "
                      f"failed(n={p['failed']['n']}) ever {p['failed']['ever_touched_gold']:.3f} "
                      f"on {p['failed']['on_target_gold']:.3f}")
            if "solved" in p:
                d = p["delta_solved_minus_failed"]
                print(f"    pooled delta (solved - failed): ever {d['ever_touched_gold']:+.3f}, "
                      f"on_target {d['on_target_gold']:+.3f}")
        if "within_instance" in gi and "ever_touched_gold" in gi["within_instance"]:
            w = gi["within_instance"]
            print(f"    within-instance ({w['n_instances']} contested instances): "
                  f"ever {w['ever_touched_gold']['solved']:.3f} vs "
                  f"{w['ever_touched_gold']['failed']:.3f} "
                  f"(delta {w['ever_touched_gold']['mean_delta']:+.3f}, "
                  f"p={w['ever_touched_gold']['p']}); "
                  f"on_target {w['on_target_gold']['solved']:.3f} vs "
                  f"{w['on_target_gold']['failed']:.3f} "
                  f"(delta {w['on_target_gold']['mean_delta']:+.3f}, "
                  f"p={w['on_target_gold']['p']})")
        print(f"    own-patch target (frozen definition): {entry['own_patch_target']}")

        # d: per-step test outcomes
        entry["test_outcomes"] = test_coverage(st)
        tc = entry["test_outcomes"]
        print(f"  test outcomes: strict {tc['strict_step_rate']:.2%} of steps, "
              f"loose {tc['loose_step_rate']:.2%}; runs with a parseable test summary "
              f"{tc['runs_with_strict_summary']:.1%}")

        if key == "thoughtworks":
            entry["by_framework"] = {}
            fr = rn["extra"].fillna("{}").apply(
                lambda s: (json.loads(s) or {}).get("agent_framework") if s else None)
            st2 = st.copy()
            st2["framework"] = st2["run_id"].map(
                dict(zip(rn.run_id, fr)))
            for fw, g in st2.groupby("framework"):
                edf = g[(g.is_edit == 1)]
                runs_fw = set(rn.run_id[rn.run_id.isin(set(g.run_id))])
                rfw = rn[rn.run_id.isin(runs_fw)]
                sub = edf.merge(rn[["run_id", "patch_hashes", "patch_files"]],
                                on="run_id", how="left")
                e = {"n_runs": int(g.run_id.nunique()), "n_steps": int(len(g)),
                     "n_edits": int(len(edf)),
                     "footer_step_rate": float(g.has_footer.mean()),
                     "catn_step_rate": float(g.has_catn.mean()),
                     "strict_test_step_rate": float(g.test_strict.mean()),
                     "loose_test_step_rate": float(g.test_loose.mean()),
                     "run_patch_rate": float((rfw.patch_chars > 0).mean())}
                subp = sub[sub.run_id.isin(set(rfw[rfw.patch_chars > 0].run_id))]
                e["n_edits_in_patched_runs"] = int(len(subp))
                e["edit_coverage"] = float(len(subp) / max(len(sub), 1))
                if len(subp):
                    e["taxonomy"] = taxonomy(subp)
                e["gold"] = gold_metrics(sub, gold_by_instance)
                entry["by_framework"][str(fw)] = e
            print("  by framework:")
            for fw, e in entry["by_framework"].items():
                t = e.get("taxonomy", {})
                print(f"    {fw:<16} runs {e['n_runs']:>5} edits {e['n_edits']:>7} "
                      f"footer {e['footer_step_rate']:.3%} catn {e['catn_step_rate']:.2%} "
                      f"patchable {e['run_patch_rate']:.1%} "
                      + (f"kept {t.get('kept_rate',float('nan')):.3f} "
                         f"rev {t.get('revised_rate',float('nan')):.3f} "
                         f"dead {t.get('dead_end_rate',float('nan')):.3f}" if t else "taxonomy n/a"))

        result["corpora"][key] = entry
        if cal:
            scope = ("reference_all_runs"
                     if entry["patch_coverage"].get("empty_patch_is_a_real_outcome")
                     else "reference_nonempty_patch_runs_only")
            rref = cal[scope]
            result.setdefault("reference_matched_scope", {})[key] = {
                "scope": rref.get("scope"), "kept": rref["kept_rate"],
                "revised": rref["revised_rate"], "dead_end": rref["dead_end_rate"],
                "n_edits": rref["n_edits"], "source": "results/rebuild/xscaffold_calibration.json",
            }
            entry["verdicts"] = verdicts(entry, rref)
        else:
            entry["verdicts"] = verdicts(entry, REFERENCE["swe_agent_nebius"])
        print("\n  VERDICTS")
        for kk, vv in entry["verdicts"].items():
            print(f"    {kk:<10} {vv}")

    (OUT / "xscaffold_replication.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {OUT / 'xscaffold_replication.json'}")


if __name__ == "__main__":
    main()
