"""Can a runtime tell, *before* an edit, whether that edit will turn out to be wasted?

This is the cleanest online formulation of the study's question, and it is not circular:

  * **Features** come from steps ``[t-K, t-1]``: the trajectory strictly before the edit.
  * **Target** is a mechanical property of what happened at step ``t`` and later -- the
    workspace either moved, or the edit was a no-op, or the lines the agent wrote never
    survived into the final patch.

Nothing in the feature window is used to compute the label, so an AUC here is real
predictability rather than a restatement of the window's own contents.  Three labels are
scored:

``nochange``   step t changed the file's total line count (editable steps only)
``noop``       step t was an edit whose file size did not move
``wasted``     step t was an edit whose introduced lines are absent from the final patch
               (only computable for the corpus whose patches are on disk: Nebius)

Writes ``results/rebuild/step_task.json``.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402
from agentstall import features as F  # noqa: E402
from agentstall import targets as T  # noqa: E402

OUT = ROOT / "results" / "rebuild"

_ADDED = re.compile(r"^\+(?!\+\+)(.*)$", re.M)
_DIFF_FILE = re.compile(r"^diff --git a/(\S+)", re.M)


def line_hash(s: str) -> str:
    return hashlib.blake2b(s.strip().encode("utf-8", "ignore"), digest_size=6).hexdigest()


def patch_sets(patch: str) -> Tuple[Set[str], Set[str]]:
    if not patch:
        return set(), set()
    lines = {line_hash(m.group(1)) for m in _ADDED.finditer(patch) if len(m.group(1).strip()) >= 3}
    files = {Path(f).name for f in _DIFF_FILE.findall(patch)}
    return lines, files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="nebius", choices=["nebius"])
    ap.add_argument("--k", type=int, default=8, help="feature window length before the edit")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)

    step_path = ROOT / "data" / "processed" / "steps" / args.corpus / "steps.parquet"
    run_path = ROOT / "data" / "processed" / "steps" / args.corpus / "runs.parquet"
    steps = pd.read_parquet(step_path)
    runs = pd.read_parquet(run_path).drop_duplicates("run_id")
    if args.limit:
        keep = set(runs["run_id"].head(args.limit))
        steps = steps[steps.run_id.isin(keep)]
        runs = runs[runs.run_id.isin(keep)]

    patch_by_key: Dict[Tuple[str, str, bool, int], Tuple[Set[str], Set[str]]] = {}
    import pyarrow.parquet as pq
    for f in sorted((ROOT / "data" / "raw" / args.corpus).glob("train-*.parquet")):
        for batch in pq.ParquetFile(f).iter_batches(batch_size=100):
            for row in batch.to_pylist():
                traj = row["trajectory"]
                patch_by_key[(row["instance_id"], row["model_name"], bool(row["target"]),
                              len(traj) if traj is not None else 0)] = patch_sets(row["generated_patch"] or "")
    print(f"patch index: {len(patch_by_key)} entries")

    feat_cols_all = None
    rows: List[Dict[str, object]] = []
    n_runs = 0
    for run_id, g in steps.groupby("run_id", sort=False):
        md = runs[runs.run_id == run_id]
        if not len(md):
            continue
        md = md.iloc[0]
        ent = None
        rv = F.build_run_view(g, ent)
        rv.meta["novel_step_count"] = F.prefix_novel_counts(rv)
        obj = T.step_level_objective(rv)
        # mechanical labels
        labs = []
        for i in range(rv.n):
            d = obj["ws_delta"][i]
            labs.append({
                "nochange": (0.0 if d == 0 else 1.0) if not np.isnan(d) else np.nan,
                "noop": (1.0 if (rv.is_edit[i] and not np.isnan(d) and d == 0) else
                         (0.0 if (rv.is_edit[i] and not np.isnan(d)) else np.nan)),
            })
        # wasted-edit label from the final patch
        psets = patch_by_key.get((str(md["task"]), str(md["model"]), bool(int(md["reward"])), rv.n))
        added_set = psets[0] if psets else set()
        # build a feature window ending just before each edit
        prefix: Set[str] = set()
        rv.meta["_pref_i"] = 0
        wins: Dict[int, Dict[str, float]] = {}
        for t in range(rv.n):
            lo = max(0, t - args.k + 1)
            while rv.meta["_pref_i"] < lo:
                i = rv.meta["_pref_i"]
                for kind, val, _c in rv.ent_text[i]:
                    prefix.add(kind + "|" + val)
                rv.meta["_pref_i"] = i + 1
            if t - lo + 1 >= 3:
                wins[t] = F.window_features(rv, t, args.k, prefix)
        for t, wf in wins.items():
            ti = t + 1
            if ti >= rv.n:
                continue
            row: Dict[str, object] = {
                "run_id": run_id, "task": str(md["task"]), "model": str(md["model"]),
                "reward": int(md["reward"]), "t": t, "n_steps": rv.n,
                "relpos": t / max(1, rv.n - 1),
                "is_edit_next": float(rv.is_edit[ti]),
                "y_nochange": labs[ti]["nochange"],
                "y_noop": labs[ti]["noop"],
            }
            for k, v in wf.items():
                row[k] = v
            # wasted-edit label: only when the next step is an edit whose lines are known
            hashes = set()
            if rv.is_edit[ti]:
                addl = g.iloc[ti].get("added_hashes") if "added_hashes" in g.columns else ""
                hashes = set(str(addl).split()) if addl else set()
            if rv.is_edit[ti] and hashes and added_set:
                row["y_wasted"] = 0.0 if (hashes & added_set) else 1.0
            else:
                row["y_wasted"] = np.nan
            rows.append(row)
        n_runs += 1
        if n_runs % 2000 == 0:
            print(f"  {n_runs} runs, {len(rows)} candidate steps", flush=True)
    df = pd.DataFrame(rows)
    print(f"built {len(df)} step targets over {df.run_id.nunique()} runs")
    df.to_parquet(OUT / "step_task.parquet", index=False)

    groups = {k: [c for c in v if c in df.columns] for k, v in F.FEATURE_GROUPS.items()}
    res: Dict[str, object] = {"n_steps": int(len(df)), "k": args.k,
                              "base_rates": {}, "monitors": []}
    for lab in ("y_nochange", "y_noop", "y_wasted"):
        v = df[lab].dropna()
        res["base_rates"][lab] = {"n": int(len(v)), "mean": float(v.mean())}
    print("base rates:", json.dumps(res["base_rates"], indent=None))

    for lab in ("y_nochange", "y_noop", "y_wasted"):
        sub = df[df[lab].notna()]
        if len(sub) < 500:
            continue
        y = sub[lab].to_numpy(dtype=float)
        for gname, cols in groups.items():
            if not cols:
                continue
            f = E.fit_logistic_cv(sub, cols, y_col=lab, n_folds=5)
            if np.isnan(f["auc_mean"]):
                continue
            res["monitors"].append({"label": lab, "monitor": gname + "_raw",
                                    "auc": E.safe_auc(y, f["oof"]), "ap": E.safe_ap(y, f["oof"]),
                                    "cv_auc": f["auc_mean"]})
            s_cols = [c + "_s" for c in cols if c + "_s" in sub.columns]
            if len(s_cols) == len(cols):
                f2 = E.fit_logistic_cv(sub, s_cols, y_col=lab, n_folds=5)
                res["monitors"].append({"label": lab, "monitor": gname + "_stat",
                                        "auc": E.safe_auc(y, f2["oof"]),
                                        "ap": E.safe_ap(y, f2["oof"]), "cv_auc": f2["auc_mean"]})
        # trivial controls
        for cname, cvals in (("position", sub["relpos"].to_numpy(dtype=float)),
                             ("reward_only", 1.0 - sub["reward"].to_numpy(dtype=float))):
            res["monitors"].append({"label": lab, "monitor": cname,
                                    "auc": E.safe_auc(y, cvals), "ap": E.safe_ap(y, cvals),
                                    "cv_auc": float("nan")})
        print(f"\nlabel {lab}:")
        for m in sorted([m for m in res["monitors"] if m["label"] == lab],
                        key=lambda m: -(m["auc"] if m["auc"] == m["auc"] else 0))[:8]:
            print(f"   {m['monitor']:<16} AUC {m['auc']:.3f}  AP {m['ap']:.3f}")

    with open(OUT / "step_task.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'step_task.json'}")


if __name__ == "__main__":
    main()
