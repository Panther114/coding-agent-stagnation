"""Two diagnostics: why did the runs table lose rows, and what do TB2 editor observations
look like (needed for objective workspace state on the Terminal-Bench corpus)?"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    d = pd.read_parquet(ROOT / "data/processed/steps/tb2/steps.parquet",
                        columns=["run_id", "tool", "obs_chars", "obs_lines", "st_test"])
    r = pd.read_parquet(ROOT / "data/processed/steps/tb2/runs.parquet")
    print("step-table runs:", d.run_id.nunique(), " runs-table rows:", len(r),
          " unique:", r.run_id.nunique(), " duplicated:", int(r.duplicated("run_id").sum()))

    sub = d[d.tool == "str_replace_editor"]
    print("\nstr_replace_editor steps:", len(sub), " mean obs_chars",
          float(sub.obs_chars.mean()) if len(sub) else 0)

    df = pd.read_parquet(ROOT / "data/raw/tb2/train-00000-of-00002.parquet",
                         columns=["trial_name", "steps", "agent"])
    df = df[df["steps"].astype(str) != "null"]
    shown = 0
    obs_shapes = {}
    for s, agent in zip(df["steps"].head(6000), df["agent"].head(6000)):
        try:
            arr = json.loads(s)
        except Exception:
            continue
        for rec in arr:
            t = rec.get("tools")
            if isinstance(t, list) and t and isinstance(t[0], dict) and t[0].get("fn") == "str_replace_editor":
                obs = str(rec.get("obs") or "")
                key = agent
                obs_shapes.setdefault(key, []).append(obs[:200])
                if shown < 4:
                    print("\n=== agent", agent, "cmd:", json.dumps(t[0])[:220])
                    print("OBS:", obs[:500])
                    shown += 1
    print("\nagents with str_replace_editor observations:", list(obs_shapes))
    # does any TB2 observation carry a line-count footer at all?
    pat = re.compile(r"\((\d+) lines total\)|\[File:\s*([^\]]+)\]|lines \d+-\d+|Line \d+")
    hits = 0
    seen = 0
    for s in df["steps"].head(800):
        try:
            arr = json.loads(s)
        except Exception:
            continue
        for rec in arr:
            obs = rec.get("obs") or ""
            seen += 1
            if pat.search(str(obs)):
                hits += 1
    print(f"observations with any line/file marker: {hits}/{seen}")


if __name__ == "__main__":
    main()
