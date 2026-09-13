"""Feasibility probe: can we see agent WAITING / POLLING at scale in the corpora we hold?

Motivation.  A collaborator working on a runtime plugin reports that agents burn turns on
`bash_wait`-style polling -- calling a wait/poll tool and doing nothing meaningful, checking a
progress bar they could have either blocked on or ended the turn for -- and that they fail to batch
tool calls they could have batched, which multiplies cache reads.  Their evidence comes from one
live environment.  If the behaviour is real it should be visible in the 114k logged runs we hold
across five scaffolds, and quantifying it at that scale is something a single-environment test
cannot do.

This script answers only the feasibility question: is the signal present, in which scaffolds, and
at what rate?  It is deliberately cheap -- it reads one or two columns per table -- because the
machine currently has little free memory (see the session's machine guidance: check headroom
before anything GB-scale).

Signals it looks for, per step:
  tool_wait      the tool name itself is a wait/poll primitive (wait, bash_output, task_output,
                 bashoutput, taskoutput, poll, ...)
  cmd_sleep      a shell command that sleeps (sleep N, sleep 0.5, timeout ... sleep)
  cmd_poll       a shell command that polls (watch, until/while loop with a test, `tail -f`,
                 repeated `cat` of a log, `pgrep`/`ps` checks in a retry loop)
  cmd_progress   reading a progress artefact (progress bar / percent / ETA / checking a log tail)
and, as a turn-level proxy:
  repeat_run     the same command signature issued consecutively, which is what polling looks like
                 once the wait call is a plain bash command

Nothing here is a conclusion; it is a measurement of whether the phenomenon is visible.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "results" / "rebuild"

WAIT_TOOLS = re.compile(
    r"(^|[_\-])(wait|bashoutput|bash_output|taskoutput|task_output|poll|sleep|monitor|"
    r"get_output|getoutput)([_\-]|$)", re.I)
SLEEP_CMD = re.compile(r"(^|[;&|]\s*)sleep\s+\d", re.I)
POLL_CMD = re.compile(
    r"\b(watch\s|until\s|while\s+.*(do|;)\s*(sleep|true)|tail\s+-f\b|"
    r"for\s+.*(seq|range).*(sleep|curl|cat)|pgrep\b|ps\s+aux|"
    r"curl\s+.*--retry|nc\s+-z|nvidia-smi\s+-l)", re.I)
PROGRESS_CMD = re.compile(
    r"(\bprogress\b|\bETA\b|\bpercent\b|\btqdm\b|\\r|"
    r"tail\s+-\d*\s*\S*\.?(log|out|err)\b|grep\s+-c\b.*(done|complete))", re.I)

# tables to probe: (label, steps path, scaffold)
TABLES = [
    ("swe_agent_A_shards0_3", ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet"),
    ("swe_agent_B_shards4_7", ROOT / "data" / "processed" / "steps_repl" / "nebius" / "steps.parquet"),
    ("tb2", ROOT / "data" / "processed" / "steps_tb2_dedup" / "tb2" / "steps.parquet"),
]


def columns_of(path: Path) -> List[str]:
    import pyarrow.parquet as pq
    return pq.ParquetFile(str(path)).schema_arrow.names


def probe_one(label: str, path: Path, limit_rows: Optional[int] = None) -> Dict[str, object]:
    """Cheap per-step scan of one table."""
    if not path.exists():
        return {"table": label, "error": "missing", "path": str(path)}
    import pyarrow.parquet as pq
    cols = columns_of(path)
    want = [c for c in ("run_id", "task", "model", "step", "n_steps", "verb", "tool", "cmd_family",
                        "sig", "targets_str", "reward", "is_run", "is_edit", "is_test") if c in cols]
    pf = pq.ParquetFile(str(path))
    chunks = []
    n_read = 0
    for batch in pf.iter_batches(batch_size=200_000, columns=want):
        d = batch.to_pandas()
        chunks.append(d)
        n_read += len(d)
        if limit_rows and n_read >= limit_rows:
            break
    df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    del chunks
    n = len(df)
    res: Dict[str, object] = {"table": label, "path": str(path), "n_steps": int(n),
                              "n_runs": int(df["run_id"].nunique()) if n else 0}
    if not n:
        return res

    tool = df["tool"].astype(str) if "tool" in df else pd.Series([""] * n)
    verb = df["verb"].astype(str) if "verb" in df else pd.Series([""] * n)
    txt = df["targets_str"].astype(str) if "targets_str" in df else pd.Series([""] * n)
    sig = df["sig"].astype(str) if "sig" in df else pd.Series([""] * n)

    m_wait = tool.str.contains(WAIT_TOOLS, na=False).to_numpy()
    m_sleep = txt.str.contains(SLEEP_CMD, na=False).to_numpy()
    m_poll = txt.str.contains(POLL_CMD, na=False).to_numpy()
    m_prog = txt.str.contains(PROGRESS_CMD, na=False).to_numpy()

    res["tool_wait_steps"] = int(m_wait.sum())
    res["sleep_steps"] = int(m_sleep.sum())
    res["poll_steps"] = int(m_poll.sum())
    res["progress_steps"] = int(m_prog.sum())
    res["any_wait_signal_steps"] = int((m_wait | m_sleep | m_poll | m_prog).sum())
    res["any_wait_signal_frac"] = round(float((m_wait | m_sleep | m_poll | m_prog).mean()), 5)

    # turn-level polling proxy: consecutive identical signatures inside a run
    run = df["run_id"].astype(str).to_numpy()
    same_prev = np.zeros(n, dtype=bool)
    if n > 1:
        same_run = run[1:] == run[:-1]
        same_sig = (sig.to_numpy()[1:] == sig.to_numpy()[:-1]) & (sig.to_numpy()[1:] != "")
        same_prev[1:] = same_run & same_sig
    res["consecutive_repeat_steps"] = int(same_prev.sum())
    res["consecutive_repeat_frac"] = round(float(same_prev.mean()), 5)

    # the tools that dominate waiting, if any
    if m_wait.sum():
        res["wait_tool_top"] = tool[m_wait].value_counts().head(8).to_dict()
    # verb mix, for orientation
    res["verb_mix"] = verb.value_counts(normalize=True).round(4).head(10).to_dict()
    # top tools overall, so we can see what the corpus actually calls
    res["tool_top"] = tool.value_counts().head(12).to_dict()
    return res


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out: Dict[str, object] = {"purpose": "feasibility probe for waiting/polling behaviour at scale",
                              "tables": {}}
    for label, path in TABLES:
        print(f"probing {label} ...", flush=True)
        r = probe_one(label, path)
        out["tables"][label] = r
        if "error" in r:
            print(f"  {r['error']}: {r['path']}")
            continue
        print(f"  steps={r['n_steps']:,} runs={r['n_runs']:,} | "
              f"wait_tool={r['tool_wait_steps']:,} sleep={r['sleep_steps']:,} "
              f"poll={r['poll_steps']:,} prog={r['progress_steps']:,} "
              f"| ANY={r['any_wait_signal_steps']:,} ({r['any_wait_signal_frac']:.3%}) "
              f"| consec_repeat={r['consecutive_repeat_frac']:.3%}")
        if r.get("wait_tool_top"):
            print(f"    wait tools: {r['wait_tool_top']}")
        print(f"    top tools: {list(r['tool_top'].items())[:8]}")

    (OUT / "waiting_probe.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"\nwrote {OUT / 'waiting_probe.json'}")


if __name__ == "__main__":
    main()
