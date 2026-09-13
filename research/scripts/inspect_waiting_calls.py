"""Inspect real BashOutput / TaskOutput / wait calls so the measurement is built on what is there.

Before quantifying "wasted polling turns" we need to know what these calls actually look like:
what arguments they carry, whether they name the process they poll (so polls can be clustered per
process and the avoidable (k-1) turns computed), how large the observation they return is (the
token cost), and how many turns a single polled process consumes.

Guessing here would produce a number that cannot be defended, so this reads actual rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"

POLL = ("bashoutput", "bash_output", "taskoutput", "task_output", "wait")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = ROOT / "data" / "processed" / "steps_tb2_full" / "tb2" / "steps.parquet"
    import pyarrow.parquet as pq
    cols = pq.ParquetFile(str(p)).schema_arrow.names
    want = [c for c in ("run_id", "task", "model", "step", "n_steps", "verb", "tool",
                        "targets_str", "obs_chars", "text_chars", "is_run", "is_edit",
                        "reward", "obs_lines") if c in cols]
    print("columns:", want)
    df = pd.read_parquet(p, columns=want)
    print(f"rows: {len(df):,}")

    tool = df["tool"].astype(str)
    is_poll = tool.str.lower().isin(POLL) | tool.str.lower().str.contains(
        r"bash_?output|task_?output", regex=True, na=False)
    print(f"\npoll steps: {int(is_poll.sum()):,} of {len(df):,} "
          f"({is_poll.mean():.4%})")
    print("\ntool breakdown:")
    print(tool[is_poll].value_counts().head(12).to_string())

    sub = df[is_poll].copy()
    print("\n=== 15 real poll calls ===")
    for r in sub.head(15).itertuples(index=False):
        t = str(getattr(r, "targets_str", ""))[:150].replace("\n", " ")
        print(f"  run={str(r.run_id)[:34]:34s} step={getattr(r,'step',None):>4} "
              f"tool={str(r.tool):14s} obs_chars={getattr(r,'obs_chars',None)} "
              f"txt={getattr(r,'text_chars',None)} | {t}")

    # per-run clustering: how many poll turns does one run spend?
    g = sub.groupby("run_id").size()
    print(f"\n=== polls per run (runs with >=1 poll: {len(g):,}) ===")
    print(f"  mean {g.mean():.2f}  median {g.median():.0f}  p90 {g.quantile(0.9):.0f}  "
          f"max {g.max()}")
    print("  distribution:", g.value_counts().sort_index().head(12).to_dict())

    # cost of a poll turn vs an ordinary turn
    allobs = pd.to_numeric(df["obs_chars"], errors="coerce").fillna(0)
    alltxt = pd.to_numeric(df["text_chars"], errors="coerce").fillna(0)
    pollobs = pd.to_numeric(sub["obs_chars"], errors="coerce").fillna(0)
    polltxt = pd.to_numeric(sub["text_chars"], errors="coerce").fillna(0)
    print(f"\n=== size of a poll turn vs an ordinary turn ===")
    print(f"  poll    : obs {pollobs.mean():,.0f} chars, txt {polltxt.mean():,.0f} chars")
    print(f"  ordinary: obs {allobs.mean():,.0f} chars, txt {alltxt.mean():,.0f} chars")
    print(f"  poll obs as share of run step: "
          f"{pollobs.sum()/max(allobs.sum(),1):.4%}")

    # do polling runs differ in outcome?
    df["_poll"] = is_poll
    per_run = df.groupby("run_id").agg(polls=("_poll", "sum"),
                                       n_steps=("step", "max"),
                                       reward=("reward", "first"))
    per_run["any_poll"] = per_run.polls > 0
    print("\n=== outcome by polling ===")
    print(per_run.groupby("any_poll").agg(
        runs=("reward", "size"), solve_rate=("reward", "mean"),
        mean_polls=("polls", "mean"), mean_steps=("n_steps", "mean")).round(4).to_string())

    out = {
        "n_steps": int(len(df)),
        "n_runs": int(df.run_id.nunique()),
        "poll_steps": int(is_poll.sum()),
        "poll_share_of_steps": float(is_poll.mean()),
        "tool_breakdown": tool[is_poll].value_counts().head(12).to_dict(),
        "polls_per_run": {"n_runs_with_polls": int(len(g)), "mean": float(g.mean()),
                          "median": float(g.median()), "p90": float(g.quantile(0.9)),
                          "max": int(g.max())},
        "poll_obs_chars_mean": float(pollobs.mean()),
        "ordinary_obs_chars_mean": float(allobs.mean()),
        "samples": [{"run_id": str(r.run_id), "step": int(getattr(r, "step", 0)),
                     "tool": str(r.tool), "targets": str(getattr(r, "targets_str", ""))[:300],
                     "obs_chars": int(getattr(r, "obs_chars", 0) or 0)}
                    for r in sub.head(40).itertuples(index=False)],
    }
    (OUT / "waiting_inspect.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"\nwrote {OUT / 'waiting_inspect.json'}")


if __name__ == "__main__":
    main()
