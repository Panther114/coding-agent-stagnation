"""Probe the Nebius SWE-agent trajectories for per-step outcome structure.

Question: does this corpus contain per-step observable *outcomes* (test results,
build results, editor state) that Terminal-Bench's release lacks? If yes it is the
dense-objective-signal corpus the rebuild note asked for.

Writes a summary to stdout; no artifacts.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nebius"

FENCE = re.compile(r"```(?:bash|sh|python)?\n(.*?)```", re.S)


def parse_trajectory(tr):
    """Return list of dicts: {thought, action, obs, n_actions}."""
    steps = []
    cur = None
    for m in tr:
        role = m.get("role")
        text = m.get("text") or ""
        if role == "ai":
            cur = {"thought": text, "obs": None}
            steps.append(cur)
        elif role == "user" and cur is not None:
            cur["obs"] = text
    return steps


def main() -> None:
    path = RAW / "train-00000-of-00012.parquet"
    df = pd.read_parquet(path)
    sample = df.head(800)
    print(f"rows in shard: {len(df)}; probing {len(sample)}")

    n_steps = []
    obs_len = []
    obs_sig = collections.Counter()
    has_editor_state = 0
    has_test_like = 0
    has_exitish = 0
    dup_obs = 0
    total_obs = 0
    runs_with_test_obs = 0

    for tr in sample["trajectory"]:
        if tr is None:
            continue
        ss = parse_trajectory(tr)
        n_steps.append(len(ss))
        seen = set()
        run_test = 0
        for s in ss:
            obs = s["obs"]
            if obs is None:
                continue
            total_obs += 1
            obs_len.append(len(obs))
            h = hash(obs)
            if h in seen:
                dup_obs += 1
            seen.add(h)
            low = obs.lower()
            if "(open file:" in low or "(current directory:" in low:
                has_editor_state += 1
            if re.search(r"\b(passed|failed|error|assert)\b", low):
                has_exitish += 1
            if re.search(r"\d+ (passed|failed)", low) or "test session starts" in low:
                has_test_like += 1
                run_test += 1
            # classify
            sig = "other"
            if "not found" in low or "no such file" in low:
                sig = "not_found"
            elif "traceback" in low:
                sig = "traceback"
            elif re.search(r"\d+ (passed|failed)", low):
                sig = "test_summary"
            elif "syntaxerror" in low or "syntax error" in low:
                sig = "syntax_error"
            obs_sig[sig] += 1
        if run_test:
            runs_with_test_obs += 1

    o = np.array(obs_len)
    print(f"steps/run: mean {np.mean(n_steps):.1f} median {np.median(n_steps):.0f} max {max(n_steps)}")
    print(f"observations: {total_obs}  len mean {o.mean():.0f} med {np.median(o):.0f} "
          f"p90 {np.percentile(o, 90):.0f} max {o.max()}")
    print(f"exact-duplicate consecutive-quality obs: {dup_obs} ({dup_obs / max(total_obs, 1):.1%})")
    print(f"obs containing pytest summary: {has_test_like}")
    print(f"obs containing editor state header: {has_editor_state}")
    print(f"obs containing pass/fail/error/assert word: {has_exitish}")
    print(f"runs with >=1 pytest-summary obs: {runs_with_test_obs}/{len(sample)}")
    print("obs signature counts:", obs_sig.most_common())

    # what does a test-summary observation look like inside a trajectory?
    for tr, tid in zip(sample["trajectory"], sample["instance_id"]):
        if tr is None:
            continue
        for s in parse_trajectory(tr):
            obs = s["obs"] or ""
            if "test session starts" in obs:
                print("\n=== example test-run observation (instance", tid, ") ===")
                print(obs[:1500])
                print("=== agent action that produced it ===")
                print(s["thought"][-800:])
                return
    print("\nno inline pytest run found in the probe sample")


if __name__ == "__main__":
    main()
