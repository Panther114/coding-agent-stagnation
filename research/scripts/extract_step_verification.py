"""Extract per-step test-outcome verification records from the nebius SWE-agent corpus.

Reads the **raw** trajectory parquet (``data/raw/nebius/train-*.parquet``) because the
observation text that :mod:`agentstall.verify` needs is not carried by
``data/processed/steps/*/steps.parquet`` -- that table only holds derived features.

Corpus choice
-------------
``data/processed/steps_full/nebius/`` was still being written while this ran (it was
empty), so the run universe is the RAW corpus, and the published
``data/processed/steps/nebius/{runs,steps}.parquet`` tables are used only to verify
that ``run_id`` reproduces exactly (it does, 3000/3000 on file 0).

Resumability and memory
-----------------------
One part file per raw shard in ``--work/``; a part is reused when it is already
complete, so re-running after an interruption skips finished shards.  Each part is
written as streaming row groups through :class:`pyarrow.parquet.ParquetWriter`, so the
process never holds more than one run's rows plus a small flush buffer.

Outputs
-------
``results/rebuild/step_verification.parquet`` -- one row per (run, step).
``results/rebuild/step_verification.json``    -- coverage report and outcome counts.
``docs/VERIFY_PARSER_EVIDENCE.md``            -- literal examples the patterns came from.

Usage::

    python scripts/extract_step_verification.py
    python scripts/extract_step_verification.py --limit 8000      # smoke test
    python scripts/extract_step_verification.py --fresh           # ignore part files
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from agentstall.verify import (  # noqa: E402
    EXIT_SIGNALS,
    EXIT_UNKNOWN,
    RunVerificationTracker,
    StepVerification,
)

RAW_GLOB = "data/raw/nebius/train-*.parquet"
OUT_PARQUET = "results/rebuild/step_verification.parquet"
OUT_JSON = "results/rebuild/step_verification.json"
WORK_DIR = "results/rebuild/_step_verification_parts"
PUBLISHED_RUNS = "data/processed/steps/nebius/runs.parquet"

BATCH = 32
FLUSH_ROWS = 20_000

# --------------------------------------------------------------------------------------
# step segmentation -- mirrors scripts/build_step_table.py::build_nebius_steps exactly,
# so that ``step`` indices line up with the published steps.parquet
# --------------------------------------------------------------------------------------

_AI_CMD_FENCE = re.compile(r"```(?:bash|sh)?\s*\n(.*?)```", re.S)


def observation_texts(traj: Any) -> List[str]:
    """Observations in step order: each ai turn, then the user turn that follows it.

    An ai turn with no following user turn closes the previous step with an empty
    observation -- identical to the published builder, which is what keeps step
    indices aligned.
    """
    if isinstance(traj, list):
        msgs = [m for m in traj if isinstance(m, dict)]
    else:
        msgs = []
    out: List[str] = []
    pending = False
    for m in msgs:
        role = m.get("role")
        text = m.get("text") or ""
        if role == "ai":
            if pending:
                out.append("")
            blocks = [b.strip() for b in _AI_CMD_FENCE.findall(text)]
            pending = True
        elif role == "user" and pending:
            out.append(text)
            pending = False
    if pending:
        out.append("")
    return out


def traj_key(traj: Any) -> str:
    """Blake2b-48 of the canonical-JSON trajectory -- the published run_id suffix."""
    try:
        blob = json.dumps(traj, default=str, sort_keys=True)
    except Exception:
        blob = str(traj)
    return hashlib.blake2b(blob.encode("utf-8", "ignore"), digest_size=6).hexdigest()


# --------------------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------------------

FIELDS: Tuple[Tuple[str, pa.DataType], ...] = (
    ("run_id", pa.string()),
    ("task", pa.string()),
    ("model", pa.string()),
    ("step", pa.int32()),
    ("n_steps", pa.int32()),
    ("n_tests_passed", pa.int32()),
    ("n_tests_failed", pa.int32()),
    ("n_tests_errored", pa.int32()),
    ("n_tests_skipped", pa.int32()),
    ("n_collected", pa.int32()),
    ("has_failure", pa.bool_()),
    ("has_pass", pa.bool_()),
    ("test_exit_signal", pa.string()),
    ("has_test_obs", pa.bool_()),
    ("new_failure_ids", pa.list_(pa.string())),
    ("prev_failure_ids", pa.list_(pa.string())),
    ("failure_ids", pa.list_(pa.string())),
    ("n_new_failures", pa.int32()),
    ("n_failing_ids", pa.int32()),
    ("raw_matches", pa.list_(pa.string())),
    ("verify_source", pa.string()),
    ("has_test_evidence", pa.bool_()),
    ("has_progress", pa.bool_()),
    ("truncated_obs", pa.bool_()),
    ("reward", pa.int8()),
    ("ev_ran", pa.int8()),
    ("ev_pass", pa.int32()),
    ("ev_fail", pa.int32()),
    ("ev_error", pa.int32()),
    ("exit_status", pa.string()),
)
SCHEMA = pa.schema([pa.field(n, t) for n, t in FIELDS])
ROW_KEY = [n for n, _ in FIELDS]


def _rec_to_row(rec: StepVerification, meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_id": meta["run_id"],
        "task": meta["task"],
        "model": meta["model"],
        "step": rec.step,
        "n_steps": meta["n_steps"],
        "n_tests_passed": rec.n_tests_passed,
        "n_tests_failed": rec.n_tests_failed,
        "n_tests_errored": rec.n_tests_errored,
        "n_tests_skipped": rec.n_tests_skipped,
        "n_collected": rec.n_collected,
        "has_failure": rec.has_failure,
        "has_pass": rec.has_pass,
        "test_exit_signal": rec.test_exit_signal,
        "has_test_obs": rec.has_test_obs,
        "new_failure_ids": rec.new_failure_ids,
        "prev_failure_ids": rec.prev_failure_ids,
        "failure_ids": rec.failure_ids,
        "n_new_failures": len(rec.new_failure_ids),
        "n_failing_ids": len(rec.failure_ids),
        "raw_matches": rec.raw_matches,
        "verify_source": rec.source,
        "has_test_evidence": rec.has_test_evidence,
        "has_progress": rec.has_progress,
        "truncated_obs": rec.truncated,
        "reward": meta["reward"],
        "ev_ran": meta["ev_ran"],
        "ev_pass": meta["ev_pass"],
        "ev_fail": meta["ev_fail"],
        "ev_error": meta["ev_error"],
        "exit_status": meta["exit_status"],
    }


# --------------------------------------------------------------------------------------
# streaming
# --------------------------------------------------------------------------------------


class PartWriter:
    """Append rows to one part parquet in bounded-size row groups."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.writer = pq.ParquetWriter(path, SCHEMA, compression="zstd")
        self.buf: List[Dict[str, Any]] = []

    def add(self, rows: Sequence[Dict[str, Any]]) -> None:
        self.buf.extend(rows)
        if len(self.buf) >= FLUSH_ROWS:
            self._flush()

    def _flush(self) -> None:
        if not self.buf:
            return
        cols = {n: [r[n] for r in self.buf] for n in ROW_KEY}
        self.writer.write_table(pa.Table.from_pydict(cols, schema=SCHEMA))
        self.buf = []

    def close(self) -> None:
        self._flush()
        self.writer.close()


def load_published_universe(path: Path) -> Tuple[Optional[set], Optional[set]]:
    """Return (run_ids, (task, model) keys) for the published study universe.

    The raw corpus holds 80,036 trajectories, all with distinct run_ids, while
    ``data/processed/steps/nebius/runs.parquet`` lists 26,679 -- the study's own
    filtered universe.  Reporting coverage against the wrong denominator would
    overstate or understate it, so the restriction is explicit and the two counts are
    both reported.

    A ``(task, model)`` key set is returned alongside because the trajectory hash is
    expensive; it lets most out-of-scope rows be skipped without hashing at all.
    """
    if not path.exists():
        return None, None
    try:
        import pandas as pd
        pub = pd.read_parquet(path, columns=["run_id", "task", "model"])
    except Exception as exc:                                   # pragma: no cover
        print(f"WARNING: could not read {path}: {exc}", flush=True)
        return None, None
    keys = set(zip(pub["task"], pub["model"]))
    return set(pub["run_id"]), keys


def iter_runs(paths: Sequence[Path], limit: Optional[int],
              universe: Optional[set] = None,
              universe_keys: Optional[set] = None) -> Iterator[Dict[str, Any]]:
    """Stream raw rows as run dicts, restricted to the published universe when given."""
    n_out = 0
    for path in paths:
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=BATCH, columns=[
                "instance_id", "model_name", "trajectory", "target", "exit_status", "eval_logs"]):
            for row in batch.to_pylist():
                traj = row["trajectory"]
                if not traj:
                    continue
                task, model = row["instance_id"], row["model_name"]
                if universe_keys is not None and (task, model) not in universe_keys:
                    continue
                rid = "{}::{}::{}".format(task, model, traj_key(traj))
                if universe is not None and rid not in universe:
                    continue
                yield {**row, "run_id": rid}
                n_out += 1
                if limit and n_out >= limit:
                    return


def count_runs(paths: Sequence[Path], limit: Optional[int] = None,
               universe: Optional[set] = None,
               universe_keys: Optional[set] = None) -> int:
    """Exact size of the run universe, needed for an honest denominator."""
    return sum(1 for _ in iter_runs(paths, limit, universe, universe_keys))


def process(args: argparse.Namespace) -> Dict[str, Any]:
    raw_paths = sorted(ROOT.glob(RAW_GLOB))
    if not raw_paths:
        raise SystemExit(f"no raw shards matched {RAW_GLOB}")
    work = ROOT / args.work
    work.mkdir(parents=True, exist_ok=True)

    universe = universe_keys = None
    if args.restrict_published:
        universe, universe_keys = load_published_universe(ROOT / PUBLISHED_RUNS)
        if universe:
            print(f"restricting to the published universe: {len(universe):,} run_ids "
                  f"({len(universe_keys):,} distinct task::model pairs)", flush=True)

    n_step_rows = 0
    n_shards_processed = 0
    runs_with_any_test_obs = 0
    runs_seen = 0
    step_outcome = Counter()
    model_runs: Counter = Counter()
    model_runs_cov: Counter = Counter()
    model_steps: Counter = Counter()
    model_steps_cov: Counter = Counter()
    src_counter = Counter()
    n_truncated = 0
    n_progress_only = 0
    n_new_failure_events = 0
    t0 = time.time()

    for shard_i, path in enumerate(raw_paths):
        part = work / f"part-{shard_i:02d}.parquet"
        done = work / f"part-{shard_i:02d}.done"
        # A --limit run stops mid-shard, so its part file is not resumable evidence.
        reuse = part.exists() and done.exists() and not args.fresh
        if reuse:
            print(f"[{shard_i:02d}] {path.name}: reused", flush=True)
            continue
        if part.exists():
            part.unlink()
        if done.exists() and args.fresh:
            done.unlink()
        started = time.time()
        writer = PartWriter(part)

        def emit(run_id: str, meta: Dict[str, Any], recs: List[StepVerification]) -> None:
            nonlocal n_step_rows, runs_with_any_test_obs, n_truncated
            nonlocal n_progress_only, n_new_failure_events
            writer.add([_rec_to_row(r, {**meta, "run_id": run_id}) for r in recs])
            n_step_rows += len(recs)
            if any(r.has_test_obs for r in recs):
                runs_with_any_test_obs += 1
            for r in recs:
                step_outcome[r.test_exit_signal] += 1
                src_counter[r.source] += 1
                model_steps[meta["model"]] += 1
                if r.has_test_obs:
                    model_steps_cov[meta["model"]] += 1
                n_truncated += int(r.truncated)
                n_progress_only += int(r.has_progress and not r.has_test_obs)
                n_new_failure_events += int(bool(r.new_failure_ids))

        for row in iter_runs([path], None, universe, universe_keys):
            traj = row["trajectory"]
            task, model = row["instance_id"], row["model_name"]
            rid = row["run_id"]
            obs_list = observation_texts(traj)
            if not obs_list:
                continue
            runs_seen += 1
            model_runs[model] += 1
            ev = parse_eval_logs(row.get("eval_logs") or "")
            meta = {
                "task": task,
                "model": model,
                "n_steps": len(obs_list),
                "reward": int(bool(row["target"])),
                "ev_ran": ev["ran"],
                "ev_pass": ev["n_pass"],
                "ev_fail": ev["n_fail"],
                "ev_error": ev["n_error"],
                "exit_status": row["exit_status"] or "",
            }
            tracker = RunVerificationTracker()
            recs = [tracker.add(i, o) for i, o in enumerate(obs_list)]
            emit(rid, meta, recs)
            if any(r.has_test_obs for r in recs):
                model_runs_cov[model] += 1
            if args.limit and runs_seen >= args.limit:
                break
        writer.close()
        n_shards_processed += 1
        done.write_text(json.dumps({"runs": runs_seen, "steps": n_step_rows,
                                    "shard": path.name, "limited": bool(args.limit)}),
                        encoding="utf-8")
        print(f"[{shard_i:02d}] {path.name}: runs={runs_seen:,} steps={n_step_rows:,} "
              f"({time.time()-started:.0f}s, total {time.time()-t0:.0f}s)", flush=True)
        if args.limit and runs_seen >= args.limit:
            print("limit reached", flush=True)
            break

    status = {
        "n_steps": n_step_rows,
        "n_runs": runs_seen,
        "runs_with_any_test_obs": runs_with_any_test_obs,
        "outcome_counts": dict(step_outcome),
        "model_runs": dict(model_runs),
        "model_runs_cov": dict(model_runs_cov),
        "model_steps": dict(model_steps),
        "model_steps_cov": dict(model_steps_cov),
        "source_counts": dict(src_counter),
        "n_truncated_obs": n_truncated,
        "n_progress_only_obs": n_progress_only,
        "n_new_failure_events": n_new_failure_events,
        "total_runs_denominator": sum(model_runs.values()),
        "restricted_to_published_universe": bool(universe),
        "published_universe_size": len(universe) if universe else None,
        "n_shards_processed": n_shards_processed,
    }
    (work / "_partial.json").write_text(json.dumps(status, indent=1), encoding="utf-8")
    print("partial:", json.dumps({k: v for k, v in status.items()
                                  if k in ("n_steps", "n_runs", "outcome_counts")}, indent=1),
          flush=True)
    return status


_EVAL_ERR = re.compile(r"(\d+)\s+errors?\b", re.I)
_EVAL_FAIL = re.compile(r"(\d+)\s+failed\b", re.I)
_EVAL_PASS = re.compile(r"(\d+)\s+passed\b", re.I)


def parse_eval_logs(logs: str) -> Dict[str, Any]:
    """The *final* evaluator verdict, same reading as the published runs table.

    Present so that per-step verification can be compared against the evaluator's
    ground truth without a second pass over the raw corpus.
    """
    if not logs:
        return {"ran": 0, "n_pass": -1, "n_fail": -1, "n_error": -1}
    m_pass, m_fail, m_err = _EVAL_PASS.search(logs), _EVAL_FAIL.search(logs), _EVAL_ERR.search(logs)
    ran = 1 if (m_pass or m_fail or m_err) else 0
    return {
        "ran": ran,
        "n_pass": int(m_pass.group(1)) if m_pass else -1,
        "n_fail": int(m_fail.group(1)) if m_fail else -1,
        "n_error": int(m_err.group(1)) if m_err else -1,
    }


# --------------------------------------------------------------------------------------
# assembly + report
# --------------------------------------------------------------------------------------


def assemble(args: argparse.Namespace) -> Dict[str, Any]:
    work = ROOT / args.work
    parts = sorted(work.glob("part-*.parquet"))
    if not parts:
        raise SystemExit("no part files; run the extraction first")
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    # The published runs table gives the authoritative step count per run *and* lets us
    # check that our step segmentation matches it.  If it disagrees, coverage numbers
    # here are meaningless, so it is reported rather than assumed.
    published_steps: Dict[str, int] = {}
    published_ok = False
    pub_path = ROOT / PUBLISHED_RUNS
    if pub_path.exists():
        try:
            import pandas as pd
            pub = pd.read_parquet(pub_path, columns=["run_id", "n_steps"])
            published_steps = dict(zip(pub["run_id"], pub["n_steps"]))
            published_ok = True
        except Exception as exc:                                  # pragma: no cover
            print(f"WARNING: could not read {pub_path}: {exc}", flush=True)

    writer = pq.ParquetWriter(out, SCHEMA, compression="zstd")
    n_rows = 0
    agg = Counter()
    model_steps: Counter = Counter()
    model_steps_cov: Counter = Counter()
    model_runs: Counter = Counter()
    model_runs_cov: Counter = Counter()
    model_outcome: Dict[str, Counter] = defaultdict(Counter)
    run_max_step: Dict[str, int] = {}
    run_seen_steps: Counter = Counter()
    run_has_obs: Dict[str, bool] = {}
    run_model: Dict[str, str] = {}
    src = Counter()
    n_trunc = n_prog = n_newfail = 0
    n_fail_ids = 0
    for p in parts:
        pf = pq.ParquetFile(p)
        for batch in pf.iter_batches(batch_size=FLUSH_ROWS):
            writer.write_table(pa.Table.from_batches([batch], schema=SCHEMA))
            d = batch.to_pydict()
            n = len(d["run_id"])
            n_rows += n
            for i in range(n):
                rid = d["run_id"][i]
                sig = d["test_exit_signal"][i]
                mdl = d["model"][i]
                agg[sig] += 1
                model_steps[mdl] += 1
                model_outcome[mdl][sig] += 1
                if d["has_test_obs"][i]:
                    model_steps_cov[mdl] += 1
                src[d["verify_source"][i]] += 1
                n_trunc += int(d["truncated_obs"][i] or 0)
                n_prog += int((d["has_progress"][i] and not d["has_test_obs"][i]) or 0)
                n_newfail += int((d["n_new_failures"][i] or 0) > 0)
                n_fail_ids += int(d["n_failing_ids"][i] or 0)
                seen = run_seen_steps[rid] + 1
                run_seen_steps[rid] = seen
                run_max_step[rid] = max(run_max_step.get(rid, -1), int(d["step"][i]))
                run_has_obs[rid] = run_has_obs.get(rid, False) or bool(d["has_test_obs"][i])
                run_model[rid] = mdl
    writer.close()

    # step coverage uses the published run's full length, so a run whose tail never
    # produced an observation is not silently treated as fully covered
    n_runs = len(run_seen_steps)
    for rid, mdl in run_model.items():
        model_runs[mdl] += 1
        if run_has_obs.get(rid):
            model_runs_cov[mdl] += 1
    n_runs_with_obs = sum(1 for v in run_has_obs.values() if v)
    # step denominator: the published n_steps where the run exists there, else our own
    denom_steps = 0
    n_matched_pub = 0
    n_step_mismatch = 0
    for rid in run_seen_steps:
        if published_ok and rid in published_steps:
            denom_steps += int(published_steps[rid])
            n_matched_pub += 1
            if int(published_steps[rid]) != run_max_step[rid] + 1:
                n_step_mismatch += 1
        else:
            denom_steps += run_max_step[rid] + 1
    covered_steps = sum(v for k, v in agg.items() if k != EXIT_UNKNOWN)

    summary = {
        "n_steps": n_rows,
        "n_runs": n_runs,
        "coverage_step_frac": (covered_steps / denom_steps) if denom_steps else 0.0,
        "coverage_run_frac": (n_runs_with_obs / n_runs) if n_runs else 0.0,
        "outcome_counts": {k: agg.get(k, 0) for k in EXIT_SIGNALS},
        "n_runs_with_any_test_obs": n_runs_with_obs,
        "per_model": {
            mdl: {
                "n_runs": model_runs[mdl],
                "n_runs_with_any_test_obs": model_runs_cov[mdl],
                "coverage_run_frac": (model_runs_cov[mdl] / model_runs[mdl]) if model_runs[mdl] else 0.0,
                "n_steps": model_steps[mdl],
                "n_steps_with_test_obs": model_steps_cov[mdl],
                "coverage_step_frac": (model_steps_cov[mdl] / model_steps[mdl]) if model_steps[mdl] else 0.0,
                "outcome_counts": {k: model_outcome[mdl].get(k, 0) for k in EXIT_SIGNALS},
            }
            for mdl in sorted(model_steps)
        },
        "denominator_notes": {
            "steps_denominator": denom_steps,
            "steps_denominator_source": (
                "published runs.parquet n_steps where the run_id matches, else the "
                "parsed step count from the raw corpus"),
            "runs_denominator": n_runs,
            "runs_denominator_source": "distinct run_ids parsed from the raw corpus",
            "n_runs_matched_in_published_table": n_matched_pub,
            "n_runs_with_disagreeing_step_count": n_step_mismatch,
            "steps_with_observation": (
                "every parsed step produces a row; an ai turn with no following user "
                "turn contributes an empty observation and parses to `unknown`"),
        },
        "source_counts": dict(src),
        "n_truncated_observations": n_trunc,
        "n_progress_only_observations": n_prog,
        "n_steps_with_new_failure_ids": n_newfail,
        "n_failing_id_mentions": n_fail_ids,
        "corpus": "data/raw/nebius (steps_full/nebius was empty while this ran)",
    }
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", default=RAW_GLOB)
    ap.add_argument("--work", default=WORK_DIR)
    ap.add_argument("--out", default=OUT_PARQUET)
    ap.add_argument("--json", default=OUT_JSON)
    ap.add_argument("--limit", type=int, default=None, help="stop after N runs (smoke test)")
    ap.add_argument("--fresh", action="store_true", help="ignore existing part files")
    ap.add_argument("--assemble-only", action="store_true")
    ap.add_argument("--restrict-published", action="store_true", default=True,
                    help="restrict to the run_ids present in the published runs table (default)")
    ap.add_argument("--no-restrict-published", dest="restrict_published", action="store_false",
                    help="process every raw trajectory (80,036 runs), not just the study's 26,679")
    args = ap.parse_args(argv)

    if not args.assemble_only:
        status = process(args)
    else:
        status = {}
    summary = assemble(args)
    (ROOT / args.json).write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1)[:4000], flush=True)
    print(f"\nwrote {args.out} and {args.json}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
