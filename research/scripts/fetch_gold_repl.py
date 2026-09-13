"""Fetch gold patches for a step table's instances, reusing the cached SWE-rebench download.

`fetch_gold_patches.py` resolves ids from the frozen `objective_signals.parquet`. The held-out
replication set (shards 4-7) contains different instances, so their gold patches have to be
resolved too or the replication has almost no usable rows (it found 8).

The upstream parquet is already cached locally, so this is a join, not a download.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GOLD_CACHE = ROOT / "data" / "raw" / "gold"
OUT = ROOT / "results" / "rebuild"


def patch_files(patch: str) -> list:
    import re
    files = set()
    for m in re.finditer(r"^\+\+\+ b/(.+)$", patch or "", re.M):
        files.add(m.group(1).strip())
    for m in re.finditer(r"^diff --git a/(\S+) b/(\S+)", patch or "", re.M):
        files.add(m.group(2).strip())
    return sorted(files)


def main() -> None:
    steps_root = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        ROOT / "data" / "processed" / "steps_repl")
    out_name = sys.argv[2] if len(sys.argv) > 2 else "gold_patches_repl.parquet"
    runs = pd.read_parquet(steps_root / "nebius" / "runs.parquet", columns=["task"])
    ids = set(runs.task.dropna().astype(str))
    print(f"instances in the replication set: {len(ids):,}")

    found: dict = {}
    for repo_dir in GOLD_CACHE.glob("*"):
        if not repo_dir.is_dir():
            continue
        for f in repo_dir.rglob("*.parquet"):
            try:
                df = pd.read_parquet(f)
            except Exception:
                continue
            if "instance_id" not in df.columns:
                continue
            col = next((c for c in ("patch", "gold_patch") if c in df.columns), None)
            if col is None:
                continue
            sub = df[df.instance_id.astype(str).isin(ids)]
            for r in sub.itertuples(index=False):
                iid = str(getattr(r, "instance_id"))
                if iid not in found:
                    found[iid] = str(getattr(r, col) or "")
        print(f"  scanned {repo_dir.name}")

    recs = []
    for iid, patch in found.items():
        fl = patch_files(patch)
        if not fl:
            continue
        recs.append({"instance_id": iid, "n_gold_files": len(fl), "gold_files": fl[:20],
                     "gold_basenames": sorted({Path(x).name for x in fl}),
                     "patch_len": len(patch)})
    out = pd.DataFrame(recs)
    dest = OUT / out_name
    out.to_parquet(dest, index=False)
    summary = {"instances_in_table": len(ids), "instances_with_gold": len(out),
               "coverage": round(len(out) / max(len(ids), 1), 4), "path": str(dest)}
    (OUT / out_name.replace(".parquet", ".json")).write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
