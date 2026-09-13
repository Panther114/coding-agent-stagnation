"""Exploratory pass over the Terminal-Bench 2 trajectory corpus.

Writes results/exploratory/tb2_overview.json and prints a report.

Usage: python explore_tb2.py
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_rows(path, columns):
    pf = pq.ParquetFile(path)
    rows = []
    for i in range(pf.metadata.num_row_groups):
        rows.extend(pf.read_row_group(i, columns=columns).to_pylist())
    return rows


def main():
    path = os.path.join(ROOT, "data", "raw", "tb2", "train-00000-of-00002.parquet")
    rows = load_rows(
        path,
        ["task_name", "agent", "model", "reward", "duration_seconds", "input_tokens",
         "output_tokens", "cache_tokens", "cost_cents", "trial_name", "started_at", "steps"],
    )
    with_steps = [r for r in rows if r["steps"] and r["steps"] != "null"]
    print(f"rows={len(rows)} with_steps={len(with_steps)}")

    out = {"n_rows": len(rows), "n_with_steps": len(with_steps)}
    out["agents"] = Counter(r["agent"] for r in with_steps).most_common()
    out["models"] = Counter(r["model"] for r in with_steps).most_common()
    out["tasks"] = Counter(r["task_name"] for r in with_steps).most_common()
    out["reward"] = Counter(r["reward"] for r in with_steps).most_common()

    nsteps = []
    srcs = Counter()
    tool_fns = Counter()
    lead_user_msgs = Counter()
    first_roles = Counter()
    ntools_per_step = Counter()
    tasks_with_taskstmt = 0
    has_obs = 0
    total_steps = 0
    for r in with_steps:
        try:
            steps = json.loads(r["steps"])
        except json.JSONDecodeError:
            continue
        nsteps.append(len(steps))
        total_steps += len(steps)
        roles = [s.get("src") for s in steps]
        if roles:
            first_roles[roles[0]] += 1
        # task statement candidates: user messages that look like a task spec
        for s in steps[:6]:
            if s.get("src") == "user" and isinstance(s.get("msg"), str) and len(s["msg"]) > 200:
                lead_user_msgs["long_user_msg"] += 1
                tasks_with_taskstmt += 1
                break
        else:
            lead_user_msgs["no_long_user_msg"] += 1
        for s in steps:
            srcs[s.get("src")] += 1
            if s.get("obs"):
                has_obs += 1
            tools = s.get("tools") or []
            ntools_per_step[len(tools)] += 1
            for t in tools:
                if isinstance(t, dict):
                    tool_fns[t.get("fn")] += 1
    import statistics

    out["nsteps"] = {
        "mean": statistics.mean(nsteps),
        "median": statistics.median(nsteps),
        "p90": sorted(nsteps)[int(0.9 * len(nsteps))],
        "p99": sorted(nsteps)[int(0.99 * len(nsteps))],
        "max": max(nsteps),
        "total": total_steps,
    }
    out["roles"] = srcs.most_common()
    out["first_roles"] = first_roles.most_common()
    out["tool_fns_top"] = tool_fns.most_common(60)
    out["tools_per_step"] = sorted(ntools_per_step.items())
    out["lead_user_msg"] = lead_user_msgs.most_common()
    out["steps_with_obs"] = has_obs
    os.makedirs(os.path.join(ROOT, "results", "exploratory"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "exploratory", "tb2_overview.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2)[:6000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
