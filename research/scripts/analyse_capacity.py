"""Is the headline AUC capacity-limited, or information-limited? (bounded version)

    python scripts/analyse_capacity.py --corpus nebius --limit 8000

The published AUCs come from a 10-step window sampled every 3 steps.  Window length and
sampling density are free parameters, so this sweeps them and reports the curve.  Two shapes
are possible and they mean different things:

* a **smooth curve with a broad maximum** — the reported setting is on a plateau, and the
  number is a property of the problem;
* a **sharp peak or a cliff** — the number is an artefact of the sampling budget, and the
  honest report must quote the whole curve rather than the point.

The feature-block sweep then runs at the best setting, so a capacity effect cannot be
confused with a feature-selection effect.  ``--limit`` caps the number of runs because stride
1 on the full corpus produces ~630k windows; a run-level cap keeps the cells comparable
because every cell sees the same runs.

Writes ``results/rebuild/capacity.json``.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import evaluate as E  # noqa: E402
from agentstall.features import FEATURE_GROUPS  # noqa: E402

OUT = ROOT / "results" / "rebuild"
TAGS = ROOT / "data" / "processed" / "windows"


def ensure(corpus: str, w: int, stride: int, limit: int | None) -> Path:
    tag = f"_cap_{corpus}_w{w}_s{stride}" + (f"_n{limit}" if limit else "")
    out = TAGS / tag
    if not (out / "windows.parquet").exists():
        cmd = [sys.executable, str(ROOT / "scripts" / "extract_windows.py"),
               "--corpus", corpus, "--w", str(w), "--stride", str(stride), "--out", str(out)]
        if limit:
            cmd += ["--limit", str(limit)]
        print(f"    extracting {tag} ...", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-800:], r.stderr[-800:])
            raise SystemExit(f"extraction failed for {tag}")
    return out


def score(df: pd.DataFrame, cols: List[str], folds: int) -> Dict[str, float]:
    primary = "y_future_stagnation" if "y_future_stagnation" in df.columns else "y_stagnation"
    df = df[df[primary].notna()]
    y = df[primary].to_numpy(dtype=float)
    f = E.fit_logistic_cv(df, cols, y_col=primary, n_folds=folds)
    return {"auc": E.safe_auc(y, f["oof"]), "ap": E.safe_ap(y, f["oof"]),
            "cv_auc": f["auc_mean"], "n_windows": int(len(df)),
            "n_runs": int(df.run_id.nunique())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="nebius")
    ap.add_argument("--limit", type=int, default=8000)
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    res: Dict[str, object] = {"corpus": args.corpus, "limit": args.limit,
                              "w_sweep": [], "stride_sweep": [], "feature_sweep": []}
    keys_all = [k for grp in FEATURE_GROUPS.values() for k in grp]

    # ---- window length at fixed stride -------------------------------------------
    for w in (3, 5, 8, 10, 15, 20):
        d = ensure(args.corpus, w, 3, args.limit)
        df = pd.read_parquet(d / "windows.parquet")
        cols = [c for c in df.columns if c in keys_all]
        r = score(df, cols, args.folds)
        r["w"] = w
        res["w_sweep"].append(r)
        print(f"  w={w:<3} runs={r['n_runs']:>5} win={r['n_windows']:>7}  AUC {r['auc']:.4f}", flush=True)

    # ---- stride at fixed window ---------------------------------------------------
    for stride in (1, 2, 3, 6):
        d = ensure(args.corpus, 10, stride, args.limit)
        df = pd.read_parquet(d / "windows.parquet")
        cols = [c for c in df.columns if c in keys_all]
        r = score(df, cols, args.folds)
        r["stride"] = stride
        res["stride_sweep"].append(r)
        print(f"  stride={stride} runs={r['n_runs']:>5} win={r['n_windows']:>7}  AUC {r['auc']:.4f}", flush=True)

    # ---- feature blocks at the densest setting, same runs -------------------------
    d = ensure(args.corpus, 10, 1, args.limit)
    df = pd.read_parquet(d / "windows.parquet")
    for gname, keys in FEATURE_GROUPS.items():
        cols = [c for c in df.columns if c in keys]
        if len(cols) < 2:
            continue
        for suffix, form in (("", "raw"), ("_s", "level-free"), ("_o", "drift-free")):
            cs = [c + suffix for c in cols if (c + suffix) in df.columns]
            if len(cs) != len(cols):
                continue
            r = score(df, cs, args.folds)
            res["feature_sweep"].append({"group": gname, "form": form, **r})
            print(f"  {gname:<6} {form:<11} AUC {r['auc']:.4f}", flush=True)
    for suffix, form in (("", "raw"), ("_s", "level-free"), ("_o", "drift-free")):
        cs = [c + suffix for c in df.columns if c in keys_all and (c + suffix) in df.columns]
        if cs:
            r = score(df, cs, args.folds)
            res["feature_sweep"].append({"group": "ALL", "form": form, **r})
            print(f"  ALL    {form:<11} AUC {r['auc']:.4f}", flush=True)

    with open(OUT / "capacity.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    ws = res["w_sweep"]
    ss = res["stride_sweep"]
    fs = res["feature_sweep"]
    print("\nbest w=" + str(max(ws, key=lambda x: x["auc"])["w"]) +
          " | best stride=" + str(max(ss, key=lambda x: x["auc"])["stride"]) +
          " | best block=" + max(fs, key=lambda x: x["auc"])["group"] + "/" +
          max(fs, key=lambda x: x["auc"])["form"])
    print(f"wrote {OUT / 'capacity.json'}")


if __name__ == "__main__":
    main()
