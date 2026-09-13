"""Build the unified per-step tables from both corpora.

    python scripts/build_step_table.py --corpus tb2
    python scripts/build_step_table.py --corpus nebius
    python scripts/build_step_table.py --corpus all --limit 300      # smoke test

Writes ``runs.parquet`` (one row per trial) and ``steps.parquet`` (one row per step).

Both files are written with a single streaming ``ParquetWriter`` each, so the tables are
built in one pass and an interrupted run leaves a *valid but partial* file, never a
corrupt one.  The first version of this script read the runs file back on every flush and
re-concatenated it, which both lost rows and corrupted the file when killed; that is
fixed here.  A rerun into the same directory resumes, skipping run ids already present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall.corpus import (  # noqa: E402
    build_nebius_steps,
    build_tb2_steps,
    ner_entities,
    parse_eval_logs,
    patch_shape,
)

TB2_GLOB = "data/raw/tb2/*.parquet"
NEBIUS_GLOB = "data/raw/nebius/train-*.parquet"
BATCH = 120
FLUSH_ROWS = 250_000


def _ent_counts(text: str) -> Dict[str, int]:
    c = {"ent_path": 0, "ent_file": 0, "ent_symbol": 0, "ent_exc": 0, "ent_testid": 0}
    for kind, _v in ner_entities(text):
        key = "ent_" + kind
        if key in c:
            c[key] += 1
    return c


def _rows(run_meta: Dict[str, Any], steps, obs_sig: List[str] = ()) -> List[Dict[str, Any]]:
    rows = []
    n = len(steps)
    for s in steps:
        obs = s.obs or ""
        ents = _ent_counts(obs[:4000] + "\n" + " ".join(s.cmds)[:2000] + "\n" + (s.text or "")[:600])
        rows.append({
            **run_meta,
            "step": s.index,
            "n_steps": n,
            "verb": s.verb,
            "tool": (s.tool or "")[:40],
            "n_cmds": len(s.cmds),
            "sig": s.sig,
            "cmd_family": (s.cmds[0].strip().split()[0][:20] if s.cmds and s.cmds[0].strip()
                           else (s.tool or "")[:20]),
            "text_chars": len(s.text or ""),
            "obs_chars": len(obs),
            "targets_str": " ".join(dict.fromkeys(s.targets))[:400],
            "edit_lines": s.edit_lines,
            "is_edit": 1 if s.is_edit else 0,
            "is_test": 1 if s.is_test else 0,
            "is_finish": 1 if s.is_finish else 0,
            "is_read": 1 if s.verb == "read" else 0,
            "is_search": 1 if s.verb == "search" else 0,
            "is_run": 1 if s.verb == "run" else 0,
            "is_list": 1 if s.verb == "list" else 0,
            "st_test": 1 if s.obs_state.test_ran else 0,
            "st_passed": s.obs_state.n_passed if s.obs_state.n_passed is not None else -1,
            "st_failed": s.obs_state.n_failed if s.obs_state.n_failed is not None else -1,
            "st_error": s.obs_state.n_error if s.obs_state.n_error is not None else -1,
            "st_exit": s.obs_state.exit_code if s.obs_state.exit_code is not None else -999,
            "st_build": (1 if s.obs_state.build_ok is True else
                         (0 if s.obs_state.build_ok is False else -1)),
            "st_tb": 1 if s.obs_state.traceback else 0,
            "st_syntax": 1 if s.obs_state.syntax_error else 0,
            "st_notfound": 1 if s.obs_state.not_found else 0,
            "st_timeout": 1 if s.obs_state.timed_out else 0,
            "st_perm": 1 if s.obs_state.permission else 0,
            "st_net": 1 if s.obs_state.network else 0,
            "st_assert": 1 if s.obs_state.assert_fail else 0,
            "st_errc": (s.obs_state.error_class or "")[:40],
            "st_sig": s.obs_state.signature()[:120],
            "obs_has_output": 1 if s.obs_state.has_output else 0,
            "obs_lines": obs.count("\n"),
            "file_shown": s.meta.get("file_shown") or "",
            "file_total": int(s.meta["file_total"]) if s.meta.get("file_total") is not None else -1,
            "file_first": int(s.meta["file_first"]) if s.meta.get("file_first") is not None else -1,
            # hashes of the text lines this step introduced: lets a later stage ask
            # whether what the agent wrote is what the solution needed, with no judge
            "added_lines_n": len(s.meta.get("added_lines") or []),
            "added_hashes": " ".join(
                hashlib.blake2b(ln.encode("utf-8", "ignore"), digest_size=6).hexdigest()
                for ln in (s.meta.get("added_lines") or [])[:80]),
            **ents,
        })
    return rows


class TableWriter:
    """Streaming parquet writer that keeps one open file handle.

    Rows are converted with ``pa.Table.from_pylist`` rather than through a pandas
    DataFrame.  ``pd.DataFrame(list_of_dicts)`` builds each column from the *keys
    present in the first row*, so any row carrying an extra field is silently dropped --
    that was quietly losing ~14% of the trial table (694 buffered rows became 598).
    ``from_pylist`` takes the union of keys and never drops a row.
    """

    def __init__(self, path: Path):
        self.path = path
        self._w: Optional[pq.ParquetWriter] = None
        self._schema: Optional[pa.Schema] = None
        self._buf: List[Dict[str, Any]] = []
        self.n_written = 0

    def add(self, rows: List[Dict[str, Any]]) -> None:
        self._buf.extend(rows)
        if len(self._buf) >= FLUSH_ROWS:
            self.flush()

    def flush(self) -> None:
        if not self._buf:
            return
        table = pa.Table.from_pylist(self._buf)
        if self._w is None:
            # Opening a ParquetWriter on an existing path truncates it from byte 0.  When
            # a batch introduces the first non-null value in a column, the schema changes
            # and a *new* writer is needed; without this seek the file would be rewritten
            # from the start and every earlier row would vanish (379 buffered runs became
            # 319).  Even a zero-length file has an 8-byte header we must get past.
            mode = "ab"
            start = os.path.getsize(self.path) if self.path.exists() else 0
            if start == 0:
                mode = "wb"
            handle = open(self.path, mode)
            if start:
                handle.seek(start)
            self._w = pq.ParquetWriter(handle, table.schema, compression="zstd")
            self._schema = table.schema
        elif table.schema != self._schema:
            table = table.cast(self._schema)
        self._w.write_table(table)
        self.n_written += table.num_rows
        self._buf = []

    def close(self) -> None:
        self.flush()
        if self._w is not None:
            self._w.close()
            self._w = None


def _resume_ids(path: Path) -> set:
    if not path.exists():
        return set()
    try:
        return set(pd.read_parquet(path, columns=["run_id"])["run_id"].unique())
    except Exception:
        print(f"  warning: {path} unreadable, starting fresh")
        return set()


def _prepare(out_dir: Path, fresh: bool) -> tuple:
    """Return (step_path, run_path, done_ids).

    Resume is table-level, not row-level: a run id already present in ``steps.parquet`` is
    skipped. That is wrong when the *parser* has changed, because the existing rows were
    produced by the old parser and are silently retained -- a rebuild after a parser fix
    reported "+0 runs" and kept 2,487 trials that the new parser could read. ``--fresh``
    deletes both tables first; use it whenever the parsing code changes.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    step_path, run_path = out_dir / "steps.parquet", out_dir / "runs.parquet"
    if fresh:
        for p in (step_path, run_path):
            if p.exists():
                p.unlink()
                print(f"  --fresh: removed {p.name}")
    done = _resume_ids(step_path)
    if done:
        print(f"resume: {len(done)} runs already built (use --fresh to re-parse everything)")
    return step_path, run_path, done


def _traj_key(traj: Any) -> str:
    try:
        blob = json.dumps(traj, default=str, sort_keys=True)
    except Exception:
        blob = str(traj)
    return hashlib.blake2b(blob.encode("utf-8", "ignore"), digest_size=6).hexdigest()


def build_tb2(limit: Optional[int], out_dir: Path, fresh: bool = False) -> None:
    step_path, run_path, done = _prepare(out_dir, fresh)
    sw, rw = TableWriter(step_path), TableWriter(run_path)
    t0 = time.time()
    n_run = n_step = 0
    for f in sorted(ROOT.glob(TB2_GLOB)):
        pf = pq.ParquetFile(f)
        for batch in pf.iter_batches(batch_size=BATCH):
            d = batch.to_pydict()
            m = len(d["trial_name"])
            for i in range(m):
                rid = d["trial_name"][i]
                if rid in done:
                    continue
                steps = build_tb2_steps(d["steps"][i])
                if not steps:
                    continue
                meta = {"run_id": rid, "corpus": "tb2", "task": d["task_name"][i],
                        "agent": d["agent"][i], "model": d["model"][i],
                        "reward": int(d["reward"][i])}
                sw.add(_rows(meta, steps))
                rw.add([{
                    **meta,
                    "n_steps": len(steps),
                    "duration_seconds": d["duration_seconds"][i],
                    "input_tokens": d["input_tokens"][i],
                    "output_tokens": d["output_tokens"][i],
                    "cost_cents": d["cost_cents"][i],
                    "n_edit": sum(1 for s in steps if s.is_edit),
                    "n_test": sum(1 for s in steps if s.is_test),
                    "n_verify_obs": sum(1 for s in steps if s.obs_state.is_verification()),
                    "n_file_measures": sum(1 for s in steps if s.meta.get("file_total") is not None),
                    "finished": int(any(s.is_finish for s in steps)),
                }])
                n_run += 1
                n_step += len(steps)
            if limit and n_run >= limit:
                break
            if n_run and n_run % 5000 == 0:
                print(f"  {n_run} runs, {n_step} steps, {time.time() - t0:.0f}s", flush=True)
        if limit and n_run >= limit:
            break
    sw.close()
    rw.close()
    print(f"tb2: +{n_run} runs, +{n_step} steps -> {out_dir}")


def build_nebius(limit: Optional[int], out_dir: Path, fresh: bool = False,
                 shards: Optional[List[int]] = None) -> None:
    """``shards`` restricts which shard indices are parsed.

    This exists so the *unseen* shards can be built on their own as a clean replication set:
    the frozen study used shards 0-3, so building 4-11 and analysing that table separately is a
    held-out test rather than a merge, and it never touches the frozen table.
    """
    step_path, run_path, done = _prepare(out_dir, fresh)
    sw, rw = TableWriter(step_path), TableWriter(run_path)
    t0 = time.time()
    n_run = n_step = 0
    files = sorted(ROOT.glob(NEBIUS_GLOB))
    if shards:
        keep = set(shards)
        files = [f for f in files
                 if any(f"train-{i:05d}-of-" in f.name for i in keep)]
        print(f"shard filter {sorted(keep)} -> {len(files)} file(s)", flush=True)
    for f in files:
        print(f"reading {f.name}", flush=True)
        pf = pq.ParquetFile(f)
        for batch in pf.iter_batches(batch_size=BATCH):
            for row in batch.to_pylist():
                traj = row["trajectory"]
                if traj is None:
                    continue
                rid = f"{row['instance_id']}::{row['model_name']}::{_traj_key(traj)}"
                if rid in done:
                    continue
                steps = build_nebius_steps(traj)
                if not steps:
                    continue
                ev = parse_eval_logs(row["eval_logs"] or "")
                shape = patch_shape(row["generated_patch"] or "")
                meta = {"run_id": rid, "corpus": "nebius", "task": row["instance_id"],
                        "agent": "swe-agent", "model": row["model_name"],
                        "reward": int(bool(row["target"]))}
                sw.add(_rows(meta, steps))
                rw.add([{
                    **meta,
                    "n_steps": len(steps),
                    "exit_status": row["exit_status"],
                    "ev_ran": int(ev["ran"]),
                    "ev_pass": ev["n_pass"] if ev["n_pass"] is not None else -1,
                    "ev_fail": ev["n_fail"] if ev["n_fail"] is not None else -1,
                    "ev_error": ev["n_error"] if ev["n_error"] is not None else -1,
                    "patch_files": " ".join(sorted(set(shape["files"])))[:600],
                    "patch_n_files": shape["n_files"],
                    "patch_n_added": shape["n_added"],
                    "patch_n_removed": shape["n_removed"],
                    "patch_lines": shape["lines"],
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
            if limit and n_run >= limit:
                break
        if limit and n_run >= limit:
            break
    sw.close()
    rw.close()
    print(f"nebius: +{n_run} runs, +{n_step} steps -> {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="all", choices=["tb2", "nebius", "all"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--fresh", action="store_true",
                    help="delete existing tables first; required after a parser change")
    ap.add_argument("--shards", type=int, nargs="*", default=None,
                    help="restrict the Nebius build to these shard indices, e.g. --shards 4 5 6 7. "
                         "Used to build the shards the frozen study never saw as a clean "
                         "held-out replication set.")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    base = ROOT / "data" / "processed" / "steps"
    root_out = Path(args.out) if args.out else None
    if args.corpus in ("tb2", "all"):
        build_tb2(args.limit, (root_out / "tb2") if root_out else (base / "tb2"), args.fresh)
    if args.corpus in ("nebius", "all"):
        build_nebius(args.limit, (root_out / "nebius") if root_out else (base / "nebius"),
                     args.fresh, args.shards)


if __name__ == "__main__":
    main()
