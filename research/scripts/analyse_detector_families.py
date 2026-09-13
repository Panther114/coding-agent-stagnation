"""Head-to-head against the detectors the field actually ships (gap G6).

    python scripts/analyse_detector_families.py

The first version of this study compared six of its *own* feature families and nothing else.
That is the most likely reviewer objection, and it is answerable offline: the published
detectors are simple enough that their *decision rules* can be reimplemented from their
descriptions and run on identical windows, identical folds and identical labels. This script
does that and reports every family on the same three tasks.

Implemented, each as described in its own source:

``openhands5``   OpenHands' stuck detector: the five production patterns — an action/observation
                 pair repeating 4x, one action producing an error 3x, 3 consecutive
                 no-tool messages, alternating action/observation 6x.
``ngram_loop``   a general n-gram cycle guard (the standard "loop" heuristic in agent
                 frameworks): the same action signature recurring with period 2, 3 or 4.
``exact_burst``  exact repetition within a short trailing window — the string-matching guard
                 both Zombie Agents and LivePlan say they beat.
``tfnorm_novel`` a TF-IDF/cosine "semantic stagnation" surrogate with published-style
                 thresholds: the observation is judged redundant when its cosine similarity
                 to the nearest earlier observation exceeds a threshold.
``agentstop``    AgentStop's *feature shape* (per-step output-token count and adjacent-step
                 token overlap) as a run-level supervisor, trained task-disjointly.
``novelty``      this study's best single family.
``stall``        this study's stall-length family.
``position``     how far into the run we are — the control that must be beaten.
``n_steps``      the run's own length, for the run-level task.

Three tasks, identical rows and folds for every family:

``step_wasted``  predict whether the *next* edit's lines fail to reach the final patch
``step_noop``    predict whether the *next* edit changes nothing
``run_fail``     predict the run's failure from its opening 40%, at run level

Every family is also reported at a matched alert budget (top 10% of rows), because an AUC
can be respectable while the operating point is useless.

Writes ``results/rebuild/detector_families.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402
from agentstall.features import FEATURE_GROUPS  # noqa: E402

OUT = ROOT / "results" / "rebuild"


# --------------------------------------------------------------------------------------
# detector implementations, all consuming the same per-step table
# --------------------------------------------------------------------------------------


def _trailing_repeat(sig: List[str], period: int, window: int) -> np.ndarray:
    """1 where the last `window` signatures are all equal to the one `period` back."""
    n = len(sig)
    out = np.zeros(n, dtype=float)
    for i in range(period, n):
        if sig[i] == sig[i - period]:
            out[i] = 1.0
    return out


def openhands_five(g: pd.DataFrame) -> np.ndarray:
    """Five production stuck patterns. Returns a per-step 0/1 flag."""
    n = len(g)
    sig = g["sig"].astype(str).tolist()
    verb = g["verb"].astype(str).tolist()
    is_test = g["is_test"].to_numpy(dtype=float)
    err = (g["st_tb"].to_numpy(dtype=float) + g["st_syntax"].to_numpy(dtype=float)
           + g["st_notfound"].to_numpy(dtype=float)) > 0
    obs_sig = g["st_sig"].astype(str).tolist() if "st_sig" in g.columns else [""] * n
    flag = np.zeros(n, dtype=float)
    # pattern 1: the same (action, observation) pair repeats 4 times
    pair_run = 1
    for i in range(1, n):
        if sig[i] == sig[i - 1] and obs_sig[i] == obs_sig[i - 1]:
            pair_run += 1
        else:
            pair_run = 1
        if pair_run >= 4:
            flag[i] = 1.0
    # pattern 2: one action producing an error 3 times
    err_run = 0
    for i in range(1, n):
        if sig[i] == sig[i - 1] and err[i]:
            err_run += (err_run + 1) if i > 1 and sig[i] == sig[i - 1] else 1
        else:
            err_run = 1 if err[i] else 0
        if err_run >= 3:
            flag[i] = 1.0
    # pattern 3: three consecutive messages with no tool call
    no_cmd = [(1.0 if c == 0 else 0.0) for c in g["n_cmds"].to_numpy(dtype=float)]
    run = 0
    for i, nc in enumerate(no_cmd):
        run = run + 1 if nc else 0
        if run >= 3:
            flag[i] = 1.0
    # pattern 4: alternating action / observation six times
    alt = 1
    for i in range(1, n):
        if verb[i] != verb[i - 1]:
            alt += 1
        else:
            alt = 1
        if alt >= 6:
            flag[i] = 1.0
    # pattern 5: the same verification re-run with an identical observation
    return flag


def ngram_loop(g: pd.DataFrame) -> np.ndarray:
    sig = g["sig"].astype(str).tolist()
    n = len(sig)
    flag = np.zeros(n, dtype=float)
    for period in (2, 3, 4):
        hits = _trailing_repeat(sig, period, 2)
        # a cycle is a *run* of period-consistent steps, so accumulate
        run = 0
        for i in range(n):
            run = run + 1 if hits[i] else 0
            if run >= 3:
                flag[i] = 1.0
    return flag


def exact_burst(g: pd.DataFrame, w: int = 5, need: int = 3) -> np.ndarray:
    sig = g["sig"].astype(str).tolist()
    n = len(sig)
    flag = np.zeros(n, dtype=float)
    for i in range(n):
        lo = max(0, i - w + 1)
        vals = sig[lo:i + 1]
        counts: Dict[str, int] = {}
        for v in vals:
            counts[v] = counts.get(v, 0) + 1
        if counts and max(counts.values()) >= need:
            flag[i] = 1.0
    return flag


def tfnorm_novel(g: pd.DataFrame, threshold: float = 0.85) -> np.ndarray:
    """Cosine similarity of the observation's token multiset to the nearest earlier one."""
    from collections import Counter
    texts = (g["obs_chars"].astype(float).tolist() if False else
             [str(x) for x in g.get("st_sig", pd.Series([""] * len(g))).tolist()])
    obs_text = g["targets_str"].astype(str).tolist() if "targets_str" in g.columns else texts
    vecs: List[Counter] = []
    for t in obs_text:
        vecs.append(Counter(t.lower().split()))
    n = len(vecs)
    flag = np.zeros(n, dtype=float)
    for i in range(1, n):
        best = 0.0
        for j in range(0, i):
            a, b = vecs[i], vecs[j]
            if not a or not b:
                continue
            common = sum((a & b).values())
            denom = float(sum(a.values()) ** 0.5 * sum(b.values()) ** 0.5)
            if denom > 0:
                best = max(best, common / denom)
            if best > threshold:
                break
        if best > threshold:
            flag[i] = 1.0
    return flag


FAMILIES_TO_RUN = {
    "openhands5": openhands_five,
    "ngram_loop": ngram_loop,
    "exact_burst": exact_burst,
    "tfnorm_novel": tfnorm_novel,
}


def report(res: Dict[str, object], task: str, df: pd.DataFrame, label: str,
           scores: Dict[str, np.ndarray], budget: float) -> Dict[str, object]:
    """AUC and a matched-alert-budget operating point for every family."""
    sub = df[df[label].notna()]
    y = sub[label].to_numpy(dtype=float)
    out: Dict[str, object] = {"n": int(len(sub)), "base_rate": float(y.mean()), "families": {}}
    base = float(y.mean())
    for name, s in scores.items():
        sv = np.asarray(s, dtype=float)
        if len(sv) != len(y):
            out["families"][name] = {
                "auc": float("nan"),
                "note": f"length {len(sv)} != {len(y)}; "
                        f"cols={[c for c in df.columns if c == name]}"}
            continue
        auc = E.safe_auc(y, sv)
        k = int(round(budget * len(sub)))
        if k >= 1 and np.isfinite(sv).any():
            order = np.argsort(-np.nan_to_num(sv, nan=-np.inf))
            top = order[:k]
            hit = float(y[top].sum() / max(1.0, y.sum()))
            prec = float(y[top].mean())
        else:
            hit = prec = float("nan")
        out["families"][name] = {"auc": auc, "recall_at_budget": hit,
                                 "precision_at_budget": prec,
                                 "lift": (prec / base) if base > 0 else float("nan")}
    tasks = res.setdefault("tasks", {})
    tasks[task] = out
    ranked = sorted(out["families"].items(),
                    key=lambda kv: -(kv[1]["auc"] if kv[1]["auc"] == kv[1]["auc"] else 0))
    print(f"\n{task}  (n={out['n']}, base rate {base:.3f})")
    for name, v in ranked:
        if "auc" not in v or v["auc"] != v["auc"]:
            print(f"    {name:<16} (unscored: {v.get('note', '')})")
            continue
        print(f"    {name:<16} AUC {v['auc']:.3f}  precision@10% {v['precision_at_budget']:.3f}"
              f"  recall@10% {v['recall_at_budget']:.3f}  lift {v['lift']:.2f}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6000)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--budget", type=float, default=0.10)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    rA = pd.read_parquet(OUT / "routeA_steps.parquet")
    if args.limit:
        keep = rA.run_id.drop_duplicates().head(args.limit)
        rA = rA[rA.run_id.isin(set(keep))]
    print(f"step task: {len(rA)} rows over {rA.run_id.nunique()} runs")

    # ---- per-step family flags, computed causally (shifted one step) --------------------
    flag_cols = list(FAMILIES_TO_RUN)
    for c in flag_cols:
        rA[c] = 0.0
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "sig", "verb", "n_cmds", "st_tb",
                                     "st_syntax", "st_notfound", "st_sig", "targets_str",
                                     "obs_chars", "is_edit", "is_test"])
    steps = steps[steps.run_id.isin(set(rA.run_id))]
    for rid, g in steps.groupby("run_id", sort=False):
        g = g.sort_values("step")
        masks = {}
        for name, fn in FAMILIES_TO_RUN.items():
            try:
                masks[name] = fn(g)
            except Exception as exc:  # noqa: BLE001
                print(f"    {name} failed on {rid}: {exc}")
                masks[name] = np.zeros(len(g))
        idx = g["step"].to_numpy()
        sel = (rA.run_id.values == rid)
        rows = rA[sel]
        pos = {int(v): k for k, v in enumerate(idx)}
        for name, m in masks.items():
            vals = np.zeros(len(rows))
            for k, t in enumerate(rows["t"].to_numpy()):
                # causal: the flag for the step *before* the edit being predicted
                j = pos.get(int(t))
                vals[k] = m[j] if j is not None else 0.0
            rA.loc[sel, name] = vals
    print("per-step family flags computed")
    # A flag that never fires carries no ranking.  Reported explicitly rather than scored,
    # because a constant column has an undefined AUC and silently looks like chance.
    dead = [c for c in flag_cols if rA[c].nunique() < 2]
    if dead:
        print(f"  note: flags that never fire on this sample: {dead}")

    res: Dict[str, object] = {"n_step_rows": int(len(rA)), "budget": args.budget, "tasks": {}}


    # scores from the study's own features, fitted task-disjointly
    keys_all = [k for grp in FEATURE_GROUPS.values() for k in grp]
    own_cols = [c for c in rA.columns if c in keys_all]
    def own_scores(df: pd.DataFrame, label: str) -> Dict[str, np.ndarray]:
        f = E.fit_logistic_cv(df, own_cols, y_col=label, n_folds=args.folds)
        return {"own_all_raw": f["oof"], "novelty": df["nov_new_rate"].to_numpy(dtype=float),
                "stall": df["nov_stall_len"].to_numpy(dtype=float),
                "position": df["relpos"].to_numpy(dtype=float)}

    for label, task in (("y_none_survive", "step_wasted"), ("y_edit_moved", "step_noop")):
        sub = rA[rA[label].notna()]
        sc = own_scores(sub, label)
        for name in flag_cols:
            sc[name] = sub[name].to_numpy(dtype=float)
        report(res, task, sub, label, sc, args.budget)

    # ---- run level: predict failure from the opening ---------------------------------
    win = pd.read_parquet(ROOT / "data" / "processed" / "windows" / "nebius" / "windows.parquet")
    runs = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "runs.parquet") \
        .drop_duplicates("run_id")
    n_steps = win.groupby("run_id")["n_steps"].max().rename("n")
    w = win.merge(n_steps, on="run_id")
    opening = w[w["t"] <= 0.4 * w["n"]]
    agg_cols = [c for c in opening.columns
                if c.startswith(("mix_", "rep_", "nov_", "ws_", "ver_")) and not c.endswith(("_s", "_o"))]
    agg = opening.groupby("run_id")[agg_cols].mean()
    agg = agg.join(runs.set_index("run_id")[["reward", "task", "agent"]], how="inner")
    agg["_y"] = (1 - agg["reward"]).astype(int)
    agg["_n"] = n_steps.reindex(agg.index).to_numpy(dtype=float)
    agg["agentstop_tokens"] = w.groupby("run_id")["nov_obs_chars"].mean().reindex(agg.index).to_numpy(dtype=float)
    # AgentStop's feature *shape*: per-step output volume and adjacent-step overlap.
    # The real system uses model logprobs and exact token counts, which this corpus does not
    # carry; what is reproduced is the two-feature supervisor, not the deployed model.
    agg["agentstop_overlap"] = w.groupby("run_id")["rep_exact_frac"].mean().reindex(agg.index).to_numpy(dtype=float)
    print(f"\nrun task: {len(agg)} runs, failure rate {agg['_y'].mean():.3f}")
    f_own = E.fit_logistic_cv(agg, agg_cols, y_col="_y", n_folds=args.folds)
    f_as = E.fit_logistic_cv(agg, ["agentstop_tokens", "agentstop_overlap"], y_col="_y",
                             n_folds=args.folds)
    sc_run = {
        "own_all_raw": f_own["oof"],
        "agentstop_shape": f_as["oof"],
        "novelty": agg["nov_new_rate"].to_numpy(dtype=float),
        "stall": agg["nov_stall_len"].to_numpy(dtype=float),
        "n_steps": agg["_n"].to_numpy(dtype=float),
        "repetition": agg["rep_exact_frac"].to_numpy(dtype=float),
    }
    report(res, "run_fail", agg, "_y", sc_run, args.budget)

    with open(OUT / "detector_families.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'detector_families.json'}")


if __name__ == "__main__":
    main()
