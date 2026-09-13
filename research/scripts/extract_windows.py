"""Build the window feature/target matrix for a corpus.

    python scripts/extract_windows.py --corpus tb2 --w 10 --stride 3

Writes ``windows.parquet`` (one row per window: run identity, position, every raw
feature, every stationary feature, every target) and ``runs_summary.parquet``.

Cost: the ~1.4M window computations take a few minutes; ``--limit`` and ``--stride``
exist for smoke tests.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import features as F  # noqa: E402
from agentstall import targets as T  # noqa: E402

# entity extraction for the novelty channel, done here so the step table stays small
_PATH = re.compile(r"(?:^|[\s'\"=(])((?:/|\./|\.\./)[\w.\-/@+]{2,120})")
_FILELIKE = re.compile(r"\b([\w\-/]+\.(?:py|pyx|js|ts|tsx|jsx|go|rs|c|h|cpp|hpp|java|rb|sh|bash|"
                       r"pl|pm|php|lua|sql|yaml|yml|toml|json|ini|cfg|md|txt|html|css|xml|tex|"
                       r"ml|stan|r|jl|hs|ex|exs|erl|scala|kt|swift|m|f|f90|ipynb|dockerfile))\b",
                       re.I)
_SYMBOL = re.compile(r"\b(?:def|class|function|fn|func|struct|impl|interface|trait|type)\s+"
                     r"([A-Za-z_][\w]{2,60})")
_ERR_CLASS = re.compile(r"\b([A-Z][A-Za-z_]{2,40}(?:Error|Exception|Warning|Fault|Failure))\b")
_TEST_ID = re.compile(r"\b((?:tests?|spec)[/\w\-]*\.py::[\w\[\]\-.]+|test_[\w\-]{2,60})")


def entities_for(text: str) -> List[Tuple[str, str, int]]:
    out: List[Tuple[str, str, int]] = []
    if not text:
        return out
    for m in _PATH.finditer(text):
        p = m.group(1).rstrip(".,;:)")
        if len(p) > 2:
            out.append(("file", p, len(p)))
    for m in _FILELIKE.finditer(text):
        out.append(("file", m.group(1), len(m.group(1))))
    for m in _SYMBOL.finditer(text):
        out.append(("symbol", m.group(1), len(m.group(1))))
    for m in _ERR_CLASS.finditer(text):
        out.append(("exc", m.group(1), len(m.group(1))))
    for m in _TEST_ID.finditer(text):
        out.append(("testid", m.group(1), len(m.group(1))))
    return out


def build_entities(df: pd.DataFrame) -> List[List[Tuple[str, str, int]]]:
    """Entity mentions per step, from the target string, the error class and the file shown."""
    ent: List[List[Tuple[str, str, int]]] = []
    tgts = df["targets_str"].astype(str).tolist() if "targets_str" in df.columns else [""] * len(df)
    errcs = df["st_errc"].astype(str).tolist() if "st_errc" in df.columns else [""] * len(df)
    shown = df["file_shown"].astype(str).tolist() if "file_shown" in df.columns else [""] * len(df)
    kinds = df["cmd_family"].astype(str).tolist() if "cmd_family" in df.columns else [""] * len(df)
    for i in range(len(df)):
        ev: List[Tuple[str, str, int]] = []
        for tok in tgts[i].split():
            ev.append(("file", tok, len(tok)))
        for m in _FILELIKE.finditer(tgts[i]):
            ev.append(("file", m.group(1), len(m.group(1))))
        for m in _SYMBOL.finditer(tgts[i]):
            ev.append(("symbol", m.group(1), len(m.group(1))))
        if errcs[i]:
            ev.append(("exc", errcs[i], len(errcs[i])))
        if shown[i]:
            ev.append(("file", shown[i], len(shown[i])))
        if kinds[i] and kinds[i] not in ("nan", "other"):
            ev.append(("cmd", kinds[i], 1))
        ent.append(ev)
    return ent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, choices=["tb2", "nebius"])
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="max runs")
    ap.add_argument("--min-window", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--min-steps", type=int, default=None,
                    help="skip runs shorter than this (default: w)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    src = ROOT / "data" / "processed" / "steps" / args.corpus
    out_dir = Path(args.out) if args.out else (ROOT / "data" / "processed" / "windows" / args.corpus)
    out_dir.mkdir(parents=True, exist_ok=True)
    min_steps = args.min_steps if args.min_steps is not None else args.w

    t0 = time.time()
    steps = pd.read_parquet(src / "steps.parquet")
    # the runs table legitimately carries rows for trials with no usable step trace
    # (a trial whose `steps` field parses to nothing); drop duplicates before indexing
    runs_meta = pd.read_parquet(src / "runs.parquet").drop_duplicates("run_id")
    print(f"{args.corpus}: {len(steps)} steps, {len(runs_meta)} runs", flush=True)

    keep = runs_meta[runs_meta["n_steps"] >= min_steps]
    if args.limit:
        keep = keep.head(args.limit)
    keep_ids = set(keep["run_id"])
    steps = steps[steps["run_id"].isin(keep_ids)]
    step_groups = dict(tuple(steps.groupby("run_id", sort=False)))
    meta_by_id = keep.set_index("run_id").to_dict("index")

    rows: List[Dict[str, float]] = []
    run_rows: List[Dict[str, float]] = []
    t_first = None
    n_done = 0
    for run_id, df in step_groups.items():
        md = meta_by_id.get(run_id)
        if md is None:
            continue
        ent = build_entities(df)
        rv = F.build_run_view(df, ent)
        t_first = t_first if t_first is not None else rv.n - 1
        wins = F.sweep_run(rv, w=args.w, stride=args.stride, min_window=args.min_window)
        if not wins:
            continue
        keys = F.all_feature_keys(wins[0])
        raw = np.array([[win[k] for k in keys] for win in wins], dtype=np.float64)
        lev, fit = F.stationarise(raw, keys)
        obj = T.step_level_objective(rv)
        novel = T.novelty_flags(rv)
        repeated = T.repeated_action_flags(rv)
        for j, win in enumerate(wins):
            t = int(win["_t"])
            row: Dict[str, float] = {
                "run_id": run_id,
                "corpus": rv.corpus,
                "task": rv.task,
                "agent": rv.agent,
                "model": rv.model,
                "reward": rv.reward,
                "n_steps": rv.n,
                "t": t,
                "w": args.w,
                "relpos": win["_relpos"],
                "frac_done": win["_frac_done"],
            }
            for k_i, k in enumerate(keys):
                row[k] = raw[j, k_i]
                row[k + "_s"] = lev[j, k_i]
                row[k + "_o"] = fit[j, k_i]
            row["y_forward_fail"] = 1.0 - float(rv.reward)
            row["y_reward"] = float(rv.reward)
            # retrospective target: describes the same steps the features describe
            row.update(T.window_targets(rv, t, args.w, obj, novel, repeated))
            # predictive target: describes the *next* window (None near the end of a run)
            fut = T.future_targets(rv, t, args.w, obj, novel, repeated)
            if fut:
                for k, v in fut.items():
                    row["f_" + k] = v
                row["y_future_stagnation"] = fut["y_stagnation"]
                row["y_future_loop"] = fut["y_loop"]
                row["y_future_waste"] = fut["y_waste"]
            rows.append(row)
        rr = T.run_level_targets(rv)
        rr.update({"run_id": run_id, "corpus": rv.corpus, "task": rv.task,
                   "agent": rv.agent, "model": rv.model})
        run_rows.append(rr)
        n_done += 1
        if n_done % 2000 == 0:
            print(f"  {n_done} runs, {len(rows)} windows, {time.time() - t0:.0f}s", flush=True)

    wdf = pd.DataFrame(rows)
    rdf = pd.DataFrame(run_rows)
    wdf.to_parquet(out_dir / "windows.parquet", index=False)
    rdf.to_parquet(out_dir / "runs_summary.parquet", index=False)
    cfg = {"corpus": args.corpus, "w": args.w, "stride": args.stride,
           "min_window": args.min_window, "runs": int(len(rdf)), "windows": int(len(wdf)),
           "feature_keys": keys, "label_cols": list(T.TARGET_COLUMNS),
           "seconds": round(time.time() - t0, 1)}
    with open(out_dir / "extract_config.json", "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    print(f"wrote {out_dir}: {len(wdf)} windows over {len(rdf)} runs in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
