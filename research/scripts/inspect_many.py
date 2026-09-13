"""Compact multi-trajectory inspector: shows roles, tool calls and observation head.

Usage: python inspect_many.py --limit N [--agents a,b] [--min-steps 30] [--obs-chars 300]
"""
import argparse
import json
import os
import re
import sys

import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TB2 = os.path.join(ROOT, "data", "raw", "tb2", "train-00000-of-00002.parquet")

TOOLTAG = re.compile(r"\[TOOL_CALL\]\s*(.*?)\s*\[/TOOL_CALL\]", re.S)


def rows_with_steps():
    pf = pq.ParquetFile(TB2)
    out = []
    for i in range(pf.metadata.num_row_groups):
        out.extend(
            pf.read_row_group(
                i,
                columns=["task_name", "agent", "model", "reward", "trial_name", "steps", "duration_seconds"],
            ).to_pylist()
        )
    return [r for r in out if r["steps"] and r["steps"] != "null"]


def brief(s, obs_chars=300, msg_chars=200):
    lines = []
    src = s.get("src")
    msg = (s.get("msg") or "").strip()
    tools = s.get("tools") or []
    obs = s.get("obs")
    if len(tools) > 12:
        tools = tools[:3] + [{"fn": f"...({len(tools)} tools)", "cmd": ""}] + tools[-2:]
    head = f"  [{src}]"
    if msg:
        head += " msg=" + re.sub(r"\s+", " ", msg)[:msg_chars]
    lines.append(head)
    for t in tools:
        lines.append(f"     TOOL {t.get('fn')}: {re.sub(chr(10), ' ', str(t.get('cmd')))[:220]}")
    for m in TOOLTAG.findall(msg):
        lines.append(f"     TOOLTAG: {re.sub(chr(10), ' ', m)[:220]}")
    if obs:
        lines.append(f"     OBS({len(obs)}c): {re.sub(chr(10), ' ', obs)[:obs_chars]}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--agents", default=None)
    ap.add_argument("--min-steps", type=int, default=30)
    ap.add_argument("--head", type=int, default=8)
    ap.add_argument("--obs-chars", type=int, default=300)
    ap.add_argument("--stratify-length", action="store_true")
    args = ap.parse_args()

    rows = rows_with_steps()
    if args.agents:
        want = set(args.agents.split(","))
        rows = [r for r in rows if r["agent"] in want]
    rows = [r for r in rows if len(json.loads(r["steps"])) >= args.min_steps]
    rows.sort(key=lambda r: len(json.loads(r["steps"])))
    if args.stratify_length:
        picks = []
        n = len(rows)
        for k in range(args.limit):
            picks.append(rows[int((k + 0.5) / args.limit * n)])
    else:
        picks = rows[: args.limit]

    for r in picks:
        steps = json.loads(r["steps"])
        print("#" * 110)
        print(f"# trial={r['trial_name']} task={r['task_name']} agent={r['agent']} model={r['model']} "
              f"reward={r['reward']} nsteps={len(steps)}")
        print("#" * 110)
        for i, s in enumerate(steps[: args.head]):
            print(f"-- step {i}")
            print(brief(s, args.obs_chars))
        print(f"  ... ({len(steps)} steps total)")
        for i, s in enumerate(steps[-2:], start=len(steps) - 2):
            print(f"-- step {i} (tail)")
            print(brief(s, args.obs_chars))
        print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
