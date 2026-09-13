"""Objective alignment: how much of the agent's work is *genuinely* on the solution path?

The single strongest objection to every stagnation study, including this one, is that
"stagnation" is a judgement.  This script removes the judgement.

Mechanically, for every edit step we know the text lines that step introduced
(``added_hashes`` in the step table).  For the Nebius corpus we also know the agent's own
final patch (``generated_patch``) and, from the evaluation transcript, whether that patch
actually resolved the issue.  So each edit step can be classified without any reader:

  ``genuine``        the step introduced at least one line that is present in the final
                     patch -- what the agent wrote is part of what it shipped.
  ``wrong_address``  the step edited a file the final patch never touches.
  ``abandoned``      the step edited a file the final patch does touch, but introduced
                     nothing that survived: right place, discarded content.

And at run level:

  ``precise``  the share of edit steps that landed lines in the final patch.
  ``on_target`` the share of edit steps aimed at a file the final patch touches.

Two things are then asked, in order:

1. **Description** -- is wasted work concentrated?  Does precision differ between
   resolved and unresolved runs once the *instance* is held fixed?
2. **Prediction** -- can a runtime, seeing only the trajectory up to the step *before* an
   edit, say whether that edit will turn out to have been wasted?  This is the clean
   online formulation of the research question: reference-free, no gold patch, no future,
   and the label is mechanical.  Requires the raw patches, so it runs here rather than in
   ``extract_windows.py``.

Writes ``results/rebuild/alignment.json`` and ``alignment_steps.parquet``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "results" / "rebuild"

_ADDED = re.compile(r"^\+(?!\+\+)(.*)$", re.M)
_DIFF_FILE = re.compile(r"^diff --git a/(\S+)", re.M)


def line_hash(s: str) -> str:
    return hashlib.blake2b(s.strip().encode("utf-8", "ignore"), digest_size=6).hexdigest()


def patch_sets(patch: str) -> Tuple[Set[str], Set[str]]:
    """(hashes of added lines, basenames of touched files)."""
    if not patch:
        return set(), set()
    lines = {line_hash(m.group(1)) for m in _ADDED.finditer(patch)
             if len(m.group(1).strip()) >= 3}
    files = {Path(f).name for f in _DIFF_FILE.findall(patch)}
    return lines, files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="nebius", choices=["nebius"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--steps-root", default=None,
                    help="step-table root; default is the frozen data/processed/steps. Point at "
                         "data/processed/steps_full to replicate on the full corpus without "
                         "touching the frozen table.")
    ap.add_argument("--out-suffix", default="",
                    help="suffix for the output artifacts, e.g. '_full' -> alignment_full.json, "
                         "so a replication never overwrites the frozen alignment.json")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)

    steps_root = Path(args.steps_root) if args.steps_root else (
        ROOT / "data" / "processed" / "steps")
    if not steps_root.is_absolute():
        steps_root = ROOT / steps_root
    step_path = steps_root / args.corpus / "steps.parquet"
    run_path = steps_root / args.corpus / "runs.parquet"
    raw_dir = ROOT / "data" / "raw" / args.corpus
    print(f"step table: {steps_root}  (output suffix: {args.out_suffix or '<none>'})")

    patch_by_instance: Dict[str, List[Tuple[str, str, bool]]] = {}
    rows: List[Dict[str, object]] = []
    n_run = 0
    for f in sorted(raw_dir.glob("train-*.parquet")):
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(f)
        for batch in pf.iter_batches(batch_size=100):
            for row in batch.to_pylist():
                patch = row["generated_patch"] or ""
                resolved = bool(row["target"])
                added, files = patch_sets(patch)
                traj = row["trajectory"]
                rid = None
                # run ids in the step table are instance::model::trajhash, so match on the
                # first two components and verify by step count
                key = (row["instance_id"], row["model_name"])
                patch_by_instance.setdefault(row["instance_id"], []).append(
                    (row["model_name"], patch, resolved))
                rows.append({
                    "instance_id": row["instance_id"], "model": row["model_name"],
                    "resolved": resolved, "patch_lines": len(patch.splitlines()),
                    "patch_added": len(added), "patch_files": " ".join(sorted(files)),
                    "n_steps": len(traj) if traj is not None else 0,
                    "exit_status": row["exit_status"],
                })
                n_run += 1
                if args.limit and n_run >= args.limit:
                    break
            if args.limit and n_run >= args.limit:
                break
        if args.limit and n_run >= args.limit:
            break
    print(f"read {len(rows)} runs with trajectories")

    # ---- step-level classification -------------------------------------------------
    steps = pd.read_parquet(step_path, columns=["run_id", "task", "model", "reward", "step",
                                                "is_edit", "added_hashes", "added_lines_n",
                                                "targets_str", "file_shown"])
    runs = pd.read_parquet(run_path, columns=["run_id", "task", "model", "reward",
                                              "patch_files", "patch_n_added", "n_steps"])
    runs = runs.drop_duplicates("run_id")
    runs["patch_file_names"] = runs["patch_files"].fillna("").apply(
        lambda s: {Path(x).name for x in str(s).split() if x})
    steps = steps.merge(runs[["run_id", "patch_files", "patch_file_names", "patch_n_added"]],
                        on="run_id", how="inner")
    print(f"steps for {steps.run_id.nunique()} runs whose patch is known")

    per_step: List[Dict[str, object]] = []
    for run_id, g in steps.groupby("run_id", sort=False):
        g = g.sort_values("step")
        patch_files = set(g["patch_file_names"].iloc[0]) if len(g) else set()
        # the final patch's added-line hashes need the raw text, so read once per instance
        iid = str(g["task"].iloc[0])
        model = str(g["model"].iloc[0])
        patch_text = ""
        resolved = bool(g["reward"].iloc[0])
        for m, p, r in patch_by_instance.get(iid, []):
            if m == model and r == resolved:
                patch_text = p
                break
        added_set, _ = patch_sets(patch_text)
        for row in g.itertuples(index=False):
            if not int(row.is_edit):
                continue
            hashes = set(str(row.added_hashes).split()) if row.added_hashes else set()
            shown = str(row.file_shown or "")
            base = Path(shown).name if shown else ""
            touched_target = bool(base) and base in patch_files
            hit = len(hashes & added_set) > 0
            if hit:
                kind = "genuine"
            elif not touched_target:
                kind = "wrong_address"
            else:
                kind = "abandoned"
            per_step.append({
                "run_id": run_id, "task": iid, "model": model, "reward": int(row.reward),
                "step": int(row.step), "kind": kind,
                "n_added": len(hashes), "touched_target": int(touched_target),
                "hit": int(hit),
            })
    pstep = pd.DataFrame(per_step)
    pstep.to_parquet(OUT / f"alignment_steps{args.out_suffix}.parquet", index=False)
    print(f"classified {len(pstep)} edit steps")

    # ---- run-level description ------------------------------------------------------
    runlvl = pstep.groupby(["run_id", "task", "model", "reward"]).agg(
        n_edit=("kind", "size"),
        n_genuine=("hit", "sum"),
        n_on_target=("touched_target", "sum"),
    ).reset_index()
    runlvl["precise"] = runlvl.n_genuine / runlvl.n_edit
    runlvl["on_target"] = runlvl.n_on_target / runlvl.n_edit
    res: Dict[str, object] = {}
    res["kind_shares"] = (pstep["kind"].value_counts(normalize=True).to_dict())
    res["steps"] = int(len(pstep))
    res["runs"] = int(len(runlvl))
    res["pooled"] = {
        "mean_precise": float(runlvl.precise.mean()),
        "mean_on_target": float(runlvl.on_target.mean()),
        "median_precise": float(runlvl.precise.median()),
        "resolved_mean_precise": float(runlvl.loc[runlvl.reward == 1, "precise"].mean()),
        "unresolved_mean_precise": float(runlvl.loc[runlvl.reward == 0, "precise"].mean()),
        "resolved_mean_on_target": float(runlvl.loc[runlvl.reward == 1, "on_target"].mean()),
        "unresolved_mean_on_target": float(runlvl.loc[runlvl.reward == 0, "on_target"].mean()),
    }
    print(f"\nRUN LEVEL: precision (share of edit steps landing in the final patch) "
          f"{res['pooled']['mean_precise']:.3f}; on-target {res['pooled']['mean_on_target']:.3f}")
    print(f"  resolved {res['pooled']['resolved_mean_precise']:.3f} vs "
          f"unresolved {res['pooled']['unresolved_mean_precise']:.3f}")

    # within-instance paired test (the control the first version never ran)
    contested = runlvl.groupby("task")["reward"].nunique()
    sel = contested[contested == 2].index
    sub = runlvl[runlvl.task.isin(sel) & (runlvl.n_edit >= 2)]
    paired = sub.groupby("task").apply(
        lambda g: pd.Series({
            "precise_ok": g.loc[g.reward == 1, "precise"].mean(),
            "precise_no": g.loc[g.reward == 0, "precise"].mean(),
            "ontgt_ok": g.loc[g.reward == 1, "on_target"].mean(),
            "ontgt_no": g.loc[g.reward == 0, "on_target"].mean(),
            "n": len(g),
        }), include_groups=False).dropna()
    res["within_instance"] = {
        "n_instances": int(len(paired)),
        "n_runs": int(len(sub)),
        "precise_ok": float(paired.precise_ok.mean()),
        "precise_no": float(paired.precise_no.mean()),
        "ontgt_ok": float(paired.ontgt_ok.mean()),
        "ontgt_no": float(paired.ontgt_no.mean()),
    }
    if len(paired) > 9:
        res["within_instance"]["wilcoxon_precise_p"] = float(
            stats.wilcoxon(paired.precise_ok, paired.precise_no).pvalue)
        res["within_instance"]["wilcoxon_ontgt_p"] = float(
            stats.wilcoxon(paired.ontgt_ok, paired.ontgt_no).pvalue)
    wi = res["within_instance"]
    print(f"  within instance ({wi['n_instances']} contested instances): "
          f"precision {wi['precise_ok']:.3f} (resolved) vs {wi['precise_no']:.3f} (unresolved) "
          f"p={wi.get('wilcoxon_precise_p', float('nan')):.2e}")
    print(f"                                   on-target {wi['ontgt_ok']:.3f} vs "
          f"{wi['ontgt_no']:.3f} p={wi.get('wilcoxon_ontgt_p', float('nan')):.2e}")

    # concentration: what share of runs carry most of the wasted edits?
    runlvl["n_wasted"] = runlvl.n_edit - runlvl.n_genuine
    tot = runlvl.n_wasted.sum()
    srt = np.sort(runlvl.n_wasted.to_numpy())[::-1]
    res["concentration"] = {
        "total_wasted_edits": int(tot),
        "frac_runs_for_50pct": float(np.searchsorted(np.cumsum(srt), 0.5 * tot) / len(srt)),
        "frac_runs_for_80pct": float(np.searchsorted(np.cumsum(srt), 0.8 * tot) / len(srt)),
        "zero_waste_run_frac": float((runlvl.n_wasted == 0).mean()),
    }
    print(f"  concentration: {res['concentration']['frac_runs_for_50pct']:.0%} of runs carry "
          f"50% of wasted edits; {res['concentration']['zero_waste_run_frac']:.0%} of runs waste none")

    with open(OUT / f"alignment{args.out_suffix}.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    runlvl.to_parquet(OUT / f"alignment_runs{args.out_suffix}.parquet", index=False)
    print(f"\nwrote {OUT / f'alignment{args.out_suffix}.json'}")


if __name__ == "__main__":
    main()
