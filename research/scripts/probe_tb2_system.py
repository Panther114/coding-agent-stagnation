"""What is in the TB2 `system`-src records that the v1 loader ignored?

The v1 loader only kept src in {agent, user}. If system records carry tool results,
that is extra observable state per step. This prints a few examples and counts.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "raw" / "tb2" / "train-00000-of-00002.parquet"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    df = pd.read_parquet(P, columns=["trial_name", "reward", "steps"])
    df = df[df["steps"].astype(str) != "null"]
    src_counts = collections.Counter()
    sys_examples = []
    sys_off = {}
    for steps_json in df["steps"].head(1500):
        try:
            arr = json.loads(steps_json)
        except Exception:
            continue
        for i, rec in enumerate(arr):
            if not isinstance(rec, dict):
                continue
            src_counts[rec.get("src")] += 1
            if rec.get("src") == "system" and len(sys_examples) < 6:
                sys_examples.append((i, rec))
                sys_off[i] = rec
    print("src counts over 1500 trials:", src_counts.most_common())
    print("system record offsets seen:", sorted(sys_off)[:20], "... total", len(sys_off))
    for i, rec in sys_examples:
        print(f"\n=== system record at index {i} ===")
        for k, v in rec.items():
            s = str(v)
            print(f"  {k}: len={len(s)} :: {s[:500]!r}")
    # how often is there an agent record with tools != null
    with_tools = 0
    with_obs = 0
    tot_agent = 0
    for steps_json in df["steps"].head(1500):
        try:
            arr = json.loads(steps_json)
        except Exception:
            continue
        for rec in arr:
            if rec.get("src") == "agent":
                tot_agent += 1
                if rec.get("tools"):
                    with_tools += 1
                if rec.get("obs"):
                    with_obs += 1
    print(f"\nagent records: {tot_agent} with tools {with_tools} with obs {with_obs}")


if __name__ == "__main__":
    main()
