"""Print raw SWE-agent edit turns so the line extractor can be written against reality."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    d = pd.read_parquet(ROOT / "data" / "raw" / "nebius" / "train-00000-of-00012.parquet",
                        columns=["instance_id", "trajectory"])
    shown = 0
    for i in range(400):
        tr = d["trajectory"][i]
        if tr is None:
            continue
        tr = list(tr)
        for j, m in enumerate(tr):
            if m.get("role") != "ai":
                continue
            t = m.get("text") or ""
            if "create" in t or "str_replace" in t or "insert" in t:
                print("=" * 78)
                print(f"instance {d['instance_id'][i]} step {j} len={len(t)}")
                print(t[:1500])
                if j + 1 < len(tr) and tr[j + 1].get("role") == "user":
                    print("--- OBS:", (tr[j + 1].get("text") or "")[:300])
                shown += 1
                break
        if shown >= 4:
            break
    print(f"\nshown {shown}")


if __name__ == "__main__":
    main()
