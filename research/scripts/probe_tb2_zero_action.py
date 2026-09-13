"""Why do ~2,500 Terminal-Bench trials parse to zero agent actions?"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    pf = pq.ParquetFile(ROOT / "data" / "raw" / "tb2" / "train-00000-of-00002.parquet")
    empty = 0
    total = 0
    shapes = Counter()
    shown = 0
    src_sets = Counter()
    for batch in pf.iter_batches(batch_size=200):
        d = batch.to_pydict()
        for i in range(len(d["trial_name"])):
            total += 1
            raw = d["steps"][i]
            if isinstance(raw, str) and raw in ("null", "None", ""):
                shapes["literal_null"] += 1
                continue
            try:
                arr = json.loads(raw) if isinstance(raw, str) else list(raw)
            except Exception:
                shapes["unparseable"] += 1
                continue
            if not arr:
                shapes["empty_list"] += 1
                continue
            srcs = tuple(sorted({str(r.get("src")) for r in arr if isinstance(r, dict)}))
            src_sets[srcs] += 1
            has_tools = any(isinstance(r, dict) and r.get("tools") for r in arr)
            if not has_tools:
                empty += 1
                shapes["no_tool_records"] += 1
                if shown < 2:
                    shown += 1
                    print("=" * 80)
                    print(f"trial {d['trial_name'][i]} agent={d.get('agent', ['?'] * (i + 1))[i]} "
                          f"n_records={len(arr)} srcs={srcs}")
                    for j, r in enumerate(arr[:6]):
                        print(f"  [{j}] src={r.get('src')} tools={r.get('tools')!r} "
                              f"msg={(str(r.get('msg'))[:150])!r}")
        if total > 6000:
            break
    print(f"\nscanned {total} trials; zero-action trials {empty}")
    print("shape counts:", shapes.most_common())
    print("src-set counts:", src_sets.most_common(6))


if __name__ == "__main__":
    main()
