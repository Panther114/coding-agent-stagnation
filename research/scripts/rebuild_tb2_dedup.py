"""Rebuild the Terminal-Bench 2.0 step tables with the UUID-twin deduplication.

Why this exists
---------------
The TB2 release ships **duplicate trials**: for 4,952 `trial_name` values there are two rows, one
carrying a real `trial_id` and one with an empty one.  `build_step_table.py` keyed runs by
`trial_name`, so both copies were written under the same `run_id`: the table had 34,029 run rows
over 29,103 distinct ids, and 1,073,923 step rows of which 186,786 were `(run_id, step)` repeats.

The fix is the one in `research/src/loaders.py` (commit `106ff4b` on `will/dev`): keep **one row per
trial_name**, preferring the twin that carries a real `trial_id`.  Preference matters — 354 of the
4,926 duplicated pairs disagree on `reward`/`n_steps`, so they are not always byte-identical copies,
and picking the wrong one would silently change the analysis.  Deduplicating by `(run_id, step)`
instead would *merge* those two different attempts, which is why the raw rows are re-read here.

Two passes, because the writer streams: pass 1 decides which physical row is kept per trial_name,
pass 2 writes exactly those rows.

    python scripts/rebuild_tb2_dedup.py --out data/processed/steps_tb2_dedup

Writes `tb2/runs.parquet` and `tb2/steps.parquet` in the output directory and prints the counts so
they can be compared with the frozen table.  Never touches the existing tables.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from build_step_table import BATCH, TableWriter, _rows  # noqa: E402
from agentstall.corpus import build_tb2_steps, parse_eval_logs, patch_shape  # noqa: E402

TB2_GLOB = "data/raw/tb2/*.parquet"


def shards() -> List[Path]:
    return sorted(ROOT.glob(TB2_GLOB))


def choose() -> Tuple[Dict[str, Tuple[int, int, int]], Dict[str, int]]:
    """Pass 1: which physical row is kept for each trial_name."""
    stats = {"raw_rows": 0, "parseable": 0, "duplicate_names": 0, "replaced_for_trial_id": 0,
             "dropped_rows": 0}
    chosen: Dict[str, Tuple[int, int, int]] = {}
    for fi, f in enumerate(shards()):
        pf = pq.ParquetFile(f)
        for g in range(pf.metadata.num_row_groups):
            d = pf.read_row_group(g, columns=["trial_name", "trial_id", "steps"]).to_pydict()
            for i in range(len(d["trial_name"])):
                stats["raw_rows"] += 1
                key = d["trial_name"][i]
                if not build_tb2_steps(d["steps"][i]):
                    continue                       # unparseable rows are skipped, as before
                stats["parseable"] += 1
                has_tid = bool(d["trial_id"][i])
                if key not in chosen:
                    chosen[key] = (fi, g, i)
                    continue
                stats["duplicate_names"] += 1
                if has_tid:
                    chosen[key] = (fi, g, i)       # prefer the twin with a real trial_id
                    stats["replaced_for_trial_id"] += 1
                else:
                    stats["dropped_rows"] += 1
    return chosen, stats


def build(out_dir: Path, chosen: Dict[str, Tuple[int, int, int]]) -> Dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sw, rw = TableWriter(out_dir / "steps.parquet"), TableWriter(out_dir / "runs.parquet")
    t0 = time.time()
    n_run = n_step = 0
    for fi, f in enumerate(shards()):
        pf = pq.ParquetFile(f)
        for g in range(pf.metadata.num_row_groups):
            d = pf.read_row_group(
                g, columns=["task_name", "agent", "model", "reward", "duration_seconds",
                            "input_tokens", "output_tokens", "trial_name", "trial_id", "steps"]
            ).to_pydict()
            for i in range(len(d["trial_name"])):
                key = d["trial_name"][i]
                if chosen.get(key) != (fi, g, i):
                    continue
                steps = build_tb2_steps(d["steps"][i])
                if not steps:
                    continue
                meta = {"run_id": key, "corpus": "tb2", "task": d["task_name"][i],
                        "agent": d["agent"][i], "model": d["model"][i],
                        "reward": int(d["reward"][i])}
                sw.add(_rows(meta, steps))
                rw.add([{
                    **meta,
                    "n_steps": len(steps),
                    "duration_seconds": d["duration_seconds"][i],
                    "input_tokens": d["input_tokens"][i],
                    "output_tokens": d["output_tokens"][i],
                    "trial_id": d["trial_id"][i] or "",
                    "n_edit": sum(1 for s in steps if s.is_edit),
                    "n_test": sum(1 for s in steps if s.is_test),
                    "n_verify_obs": sum(1 for s in steps if s.obs_state.is_verification()),
                    "n_file_measures": sum(1 for s in steps if s.meta.get("file_total") is not None),
                    "finished": int(any(s.is_finish for s in steps)),
                }])
                n_run += 1
                n_step += len(steps)
            if n_run and n_run % 5000 == 0:
                print(f"  {n_run} runs, {n_step} steps, {time.time() - t0:.0f}s", flush=True)
    sw.close()
    rw.close()
    return {"n_runs": n_run, "n_steps": n_step}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed/steps_tb2_dedup")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    print("pass 1: deciding which twin to keep ...", flush=True)
    chosen, stats = choose()
    print(f"  raw rows {stats['raw_rows']:,} | parseable {stats['parseable']:,} | "
          f"distinct trial_name kept {len(chosen):,} | duplicate rows seen {stats['duplicate_names']:,}"
          f" | kept because of a real trial_id {stats['replaced_for_trial_id']:,}"
          f" | dropped {stats['dropped_rows']:,}", flush=True)
    print("pass 2: writing the deduplicated tables ...", flush=True)
    counts = build(out / "tb2", chosen)
    print(f"tb2 deduplicated: {counts['n_runs']:,} runs, {counts['n_steps']:,} steps -> {out / 'tb2'}")
    (out / "dedup_stats.json").write_text(json.dumps({**stats, **counts, "out": str(out)},
                                                     indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
