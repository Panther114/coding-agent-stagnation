"""What exactly does a Terminal-Bench agent send when it edits a file?

The alignment channel needs the text lines an edit introduces.  On the Nebius corpus the
editor prints an OLD/===/NEW block, so extraction is exact; on Terminal-Bench the tools
are heterogeneous (str_replace_editor, Edit, Write, apply_patch, heredocs), so this
prints raw examples per tool so the extractor can be written against reality.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    df = pd.read_parquet(ROOT / "data" / "raw" / "tb2" / "train-00000-of-00002.parquet",
                         columns=["trial_name", "steps", "agent"])
    df = df[df["steps"].astype(str) != "null"]
    examples: dict = defaultdict(list)
    counts = Counter()
    for s, agent in zip(df["steps"].head(12000), df["agent"].head(12000)):
        try:
            arr = json.loads(s)
        except Exception:
            continue
        for rec in arr:
            tools = rec.get("tools")
            if not isinstance(tools, list):
                continue
            for t in tools:
                if not isinstance(t, dict):
                    continue
                fn = str(t.get("fn") or "")
                if fn.lower() in ("str_replace_editor", "edit", "write", "replace",
                                  "multi_edit", "apply_patch", "write_file", "create"):
                    counts[(agent, fn)] += 1
                    if len(examples[(agent, fn)]) < 2:
                        examples[(agent, fn)].append(json.dumps(t)[:700])
    print("edit-tool counts by (agent, tool):")
    for k, v in counts.most_common(20):
        print(f"  {k}: {v}")
    need = {"openhands", "terminus-2", "claude-code", "codex", "mini-swe-agent", "goose"}
    for (agent, fn), exs in examples.items():
        if agent in need:
            print(f"\n=== {agent} / {fn}")
            for e in exs:
                print("   ", e)
    # how many observations carry a line-count footer on this corpus?
    pat = re.compile(r"\((\d+) lines total\)|\[File: ")
    tot = hits = 0
    for s in df["steps"].head(4000):
        try:
            arr = json.loads(s)
        except Exception:
            continue
        for rec in arr:
            obs = rec.get("obs")
            if not obs:
                continue
            tot += 1
            if pat.search(str(obs)):
                hits += 1
    print(f"\nobservations with a file/line footer: {hits}/{tot}")


if __name__ == "__main__":
    main()
