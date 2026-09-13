"""Route A probes: is "the next edit is wasted" unpredictable because of the *label*, or
because of the *observables*?

    python scripts/analyse_routeA.py --k 8

The rebuild's sharpest negative is that whether an edit's lines survive into the final patch
is essentially unpredictable from the preceding window (AUC 0.574 against a 0.546 position
baseline, on 23,847 labelled steps).  That number has two possible explanations, and they
imply opposite papers:

* the **observables** do not contain the information (the monitor is fine, the problem is
  hard), or
* the **label** is too noisy for the information to show (the problem may be fine, the
  measurement is not).

Three probes separate them.

``A1`` stronger label
    An edit is "wasted" if *none* of its added lines survive.  A weaker requirement is that
    *few* survive, or that the lines it deleted survive, or that the file's net size moved in
    the final direction.  Four variants, same features, same folds.  If they all sit near
    chance, the observables are the limit.

``A2`` label from the grader, not the agent
    Replace the agent's own patch with the **test patch's file set** -- the files the issue's
    own PR touched, which is what the benchmark grades on.  That is an externally-defined
    target rather than one the agent produced, so it cannot be circular with the actions.

``A3`` Bayes ceiling
    Fit the same features **plus future information** (the rest of the run's statistics) and
    measure the AUC.  The gap between that and the online model bounds how much of the
    failure is instrumentation rather than design: a large gap means a better observable
    could help, a gap of ~0 means the ceiling is already reached.

Writes ``results/rebuild/routeA.json``.
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
from agentstall.features import FEATURE_GROUPS  # noqa: E402

OUT = ROOT / "results" / "rebuild"
_ADDED = re.compile(r"^\+(?!\+\+)(.*)$", re.M)
_REMOVED = re.compile(r"^-(?!--)(.*)$", re.M)
_DIFF_FILE = re.compile(r"^diff --git a/(\S+)", re.M)


def lh(s: str) -> str:
    return hashlib.blake2b(s.strip().encode("utf-8", "ignore"), digest_size=6).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet")
    runs = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "runs.parquet") \
        .drop_duplicates("run_id")
    if args.limit:
        keep = set(runs.run_id.head(args.limit))
        steps = steps[steps.run_id.isin(keep)]
        runs = runs[runs.run_id.isin(keep)]

    # ---- per-run patches: the agent's own, and the grader's test-patch file set --------
    own_add: Dict[str, Set[str]] = {}
    own_rem: Dict[str, Set[str]] = {}
    own_files: Dict[str, Set[str]] = {}
    grader_files: Dict[str, Set[str]] = {}
    import pyarrow.parquet as pq
    key_by_run = {str(r.run_id): (str(r.task), str(r.model), int(r.reward), int(r.n_steps))
                  for r in runs.itertuples()}
    wanted = set(key_by_run.values())
    for f in sorted((ROOT / "data" / "raw" / "nebius").glob("train-*.parquet")):
        for batch in pq.ParquetFile(f).iter_batches(batch_size=100):
            for row in batch.to_pylist():
                traj = row["trajectory"]
                k = (row["instance_id"], row["model_name"], int(bool(row["target"])),
                     len(traj) if traj is not None else 0)
                if k not in wanted:
                    continue
                patch = row["generated_patch"] or ""
                own_add[repr(k)] = {lh(m.group(1)) for m in _ADDED.finditer(patch)
                                    if len(m.group(1).strip()) >= 3}
                own_rem[repr(k)] = {lh(m.group(1)) for m in _REMOVED.finditer(patch)
                                    if len(m.group(1).strip()) >= 3}
                own_files[repr(k)] = {Path(x).name for x in _DIFF_FILE.findall(patch)}
                logs = row["eval_logs"] or ""
                # the evaluator applies the test patch; those are the files the PR touched
                gra = set(re.findall(r"Checking patch (\S+)\.\.\.", logs))
                gra |= set(re.findall(r"git apply .*?/(\S+)\.patch", logs))
                grader_files[repr(k)] = {Path(x).name for x in gra}
    print(f"patch index: {len(key_by_run)} runs; grader file sets non-empty for "
          f"{sum(1 for v in grader_files.values() if v)} runs")

    # ---- build the step-level dataset once, with all four labels ----------------------
    rows: List[Dict[str, object]] = []
    n = 0
    for run_id, g in steps.groupby("run_id", sort=False):
        g = g.sort_values("step")
        md = key_by_run.get(str(run_id))
        if md is None:
            continue
        task, model, reward, n_steps_run = md
        k = repr(md)
        rv = F.build_run_view(g, None)
        rv.meta["novel_step_count"] = F.prefix_novel_counts(rv)
        obj = T.step_level_objective(rv)
        add_set = own_add.get(k, set())
        rem_set = own_rem.get(k, set())
        pf = own_files.get(k, set())
        gf = grader_files.get(k, set())
        prefix: Set[str] = set()
        rv.meta["_pref_i"] = 0
        for t in range(rv.n - 1):
            lo = max(0, t - args.k + 1)
            while rv.meta["_pref_i"] < lo:
                i = rv.meta["_pref_i"]
                for kind, val, _c in rv.ent_text[i]:
                    prefix.add(kind + "|" + val)
                rv.meta["_pref_i"] = i + 1
            if t - lo + 1 < 3:
                continue
            ti = t + 1
            if not rv.is_edit[ti]:
                continue
            hashes = set(str(g.iloc[ti].get("added_hashes", "")).split())
            if not hashes:
                continue
            shown = str(rv.file_shown[ti] or "")
            base = Path(shown).name if shown else ""
            surv = len(hashes & add_set) / len(hashes)
            row: Dict[str, object] = {
                "run_id": run_id, "task": task, "model": model, "reward": int(reward),
                "t": t, "n_steps": rv.n, "relpos": t / max(1, t + 1),
                "n_hashes": len(hashes),
                # A1 label variants
                "y_none_survive": 0.0 if (hashes & add_set) else 1.0,
                "y_most_wasted": 1.0 if surv < 0.5 else 0.0,
                "y_file_survive": 0.0 if base in pf else 1.0,
                "y_edit_moved": np.nan,
                # A2 label: the grader's file set instead of the agent's patch
                "y_grader_miss": (0.0 if base in gf else 1.0) if gf else np.nan,
            }
            d = obj["ws_delta"][ti]
            row["y_edit_moved"] = (0.0 if (not np.isnan(d) and d != 0) else 1.0) if not np.isnan(d) else np.nan
            for kk, vv in F.window_features(rv, t, args.k, prefix).items():
                row[kk] = vv
            rows.append(row)
        n += 1
        if n % 4000 == 0:
            print(f"  {n} runs, {len(rows)} candidate steps", flush=True)
    df = pd.DataFrame(rows)
    cols = [c for c in df.columns
            if c in [x for grp in FEATURE_GROUPS.values() for x in grp]
            and not c.startswith(("y_", "f_"))]
    print(f"built {len(df)} labelled steps over {df.run_id.nunique()} runs, "
          f"{len(cols)} features")

    res: Dict[str, object] = {"n_steps": int(len(df)), "k": args.k, "n_features": len(cols),
                              "labels": {}, "a3_ceiling": {},
                              "feature_dict": cols}
    for lab in ("y_none_survive", "y_most_wasted", "y_file_survive", "y_edit_moved",
                "y_grader_miss"):
        if lab not in df.columns:
            continue
        sub = df[df[lab].notna()]
        if len(sub) < 500:
            res["labels"][lab] = {"n": int(len(sub)), "note": "too few labelled steps"}
            continue
        y = sub[lab].to_numpy(dtype=float)
        f = E.fit_logistic_cv(sub, cols, y_col=lab, n_folds=5)
        fw = E.fit_logistic_cv(sub, cols, y_col=lab, n_folds=5, within_task=True)
        res["labels"][lab] = {
            "n": int(len(sub)), "base_rate": float(y.mean()),
            "auc": E.safe_auc(y, f["oof"]),
            "auc_within_task": E.safe_auc(y, fw["oof"]),
            "ap": E.safe_ap(y, f["oof"]),
            "position_auc": E.safe_auc(y, sub["relpos"].to_numpy(dtype=float)),
        }
        c = res["labels"][lab]
        print(f"  {lab:<18} n={c['n']:>6} base {c['base_rate']:.3f}  AUC {c['auc']:.3f}  "
              f"within-task {c['auc_within_task']:.3f}  position {c['position_auc']:.3f}")

    # ---- A3: the ceiling with future information -------------------------------------
    base_lab = "y_none_survive"
    sub = df[df[base_lab].notna()].copy()
    if len(sub) > 500:
        # future-aware features: the run's total statistics and the remaining-step count,
        # neither of which an online monitor may use
        sub["_total_steps"] = sub["n_steps"].astype(float)
        sub["_remaining"] = sub["n_steps"].astype(float) - sub["t"].astype(float)
        sub["_reward"] = sub["reward"].astype(float)
        online = E.fit_logistic_cv(sub, cols, y_col=base_lab, n_folds=5)
        future = E.fit_logistic_cv(sub, cols + ["_total_steps", "_remaining", "_reward"],
                                   y_col=base_lab, n_folds=5)
        no_label = E.fit_logistic_cv(sub, cols + ["_total_steps", "_remaining"],
                                     y_col=base_lab, n_folds=5)
        y = sub[base_lab].to_numpy(dtype=float)
        res["a3_ceiling"] = {
            "online_auc": E.safe_auc(y, online["oof"]),
            "future_aware_auc_no_outcome": E.safe_auc(y, no_label["oof"]),
            "future_aware_auc_with_outcome": E.safe_auc(y, future["oof"]),
            "gap_remaining_only": (E.safe_auc(y, no_label["oof"]) - E.safe_auc(y, online["oof"])),
            "note": ("the with-outcome variant is a reference upper bound, not a usable "
                     "monitor: it is allowed to see the run's reward"),
        }
        a = res["a3_ceiling"]
        print(f"\nA3 ceiling: online {a['online_auc']:.3f}; with the run's remaining length "
              f"{a['future_aware_auc_no_outcome']:.3f} (gap "
              f"{a['gap_remaining_only']:+.3f}); with the outcome {a['future_aware_auc_with_outcome']:.3f}")

    with open(OUT / "routeA.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    df.to_parquet(OUT / "routeA_steps.parquet", index=False)
    print(f"\nwrote {OUT / 'routeA.json'}")


if __name__ == "__main__":
    main()
