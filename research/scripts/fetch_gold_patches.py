"""Find gold patches for our instance ids, so the target can be defined independently.

The confound being tested: ``on_target`` in the frozen study is computed against **the run's own
final patch** (``patch_files`` comes from that run), so a run that edits one file and patches that
one file scores 1.0 whether or not it fixed anything.  "Failed runs localise better" could
therefore be a statement about *patch breadth* rather than about localisation.

The fix is a target that does not depend on the run's own output: the **gold patch** of the
instance.  This script locates gold patches for as many of our 1,213 instance ids as possible and
records exactly which dataset each came from, so the subsequent analysis can be honest about
coverage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "rebuild"
CACHE = ROOT / "data" / "raw" / "gold"
CACHE.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    ("princeton-nlp/SWE-bench", None),
    ("princeton-nlp/SWE-bench_Verified", None),
    ("princeton-nlp/SWE-bench_Lite", None),
    ("nebius/SWE-rebench", None),
]

# columns that might hold the ground-truth patch, in order of preference
PATCH_COLS = ["patch", "gold_patch", "model_patch"]


def our_ids() -> set:
    d = pd.read_parquet(RES / "objective_signals.parquet", columns=["instance_id"])
    return set(d.instance_id.dropna().astype(str))


def list_parquet(repo: str):
    from huggingface_hub import list_repo_files

    try:
        files = list_repo_files(repo, repo_type="dataset")
    except Exception as e:
        print(f"  [{repo}] cannot list: {type(e).__name__}: {str(e)[:120]}")
        return []
    return [f for f in files if f.endswith(".parquet")]


def harvest(repo: str, files, ids: set) -> tuple:
    """Download parquet shards, return (id -> {patch, repo, base_commit}) for ids we need."""
    from huggingface_hub import hf_hub_download

    found: dict = {}
    for f in files:
        try:
            p = hf_hub_download(repo_id=repo, filename=f, repo_type="dataset",
                                local_dir=str(CACHE / repo.replace("/", "__")))
            df = pd.read_parquet(p)
        except Exception as e:
            print(f"    skip {f}: {type(e).__name__}: {str(e)[:100]}")
            continue
        if "instance_id" not in df.columns:
            print(f"    {f}: no instance_id column ({list(df.columns)[:6]}...)")
            continue
        col = next((c for c in PATCH_COLS if c in df.columns), None)
        if col is None:
            print(f"    {f}: no patch-like column among {PATCH_COLS}; has {list(df.columns)[:10]}")
            continue
        sub = df[df.instance_id.astype(str).isin(ids)]
        for r in sub.itertuples(index=False):
            iid = str(getattr(r, "instance_id"))
            if iid not in found:
                found[iid] = {"patch": str(getattr(r, col) or ""), "source": f"{repo}:{col}"}
        print(f"    {f}: {len(df):,} rows -> {len(sub):,} of ours")
    return found


def main() -> None:
    ids = our_ids()
    print(f"our instance ids: {len(ids):,}")

    all_found: dict = {}
    per_source: dict = {}
    for repo, _ in CANDIDATES:
        files = list_parquet(repo)
        if not files:
            continue
        print(f"  {repo}: {len(files)} parquet files")
        got = harvest(repo, files, ids)
        new = {k: v for k, v in got.items() if k not in all_found}
        all_found.update(new)
        per_source[repo] = len(new)
        print(f"  -> {repo}: +{len(new)} ids (total {len(all_found)})")

    # extract the gold file basenames from each patch
    import re

    def patch_files(patch: str):
        files = set()
        for m in re.finditer(r"^\+\+\+ b/(.+)$", patch or "", re.M):
            files.add(m.group(1).strip())
        for m in re.finditer(r"^diff --git a/(\S+) b/(\S+)", patch or "", re.M):
            files.add(m.group(2).strip())
        return sorted(files)

    records = []
    for iid, v in all_found.items():
        files = patch_files(v["patch"])
        records.append({"instance_id": iid, "source": v["source"],
                        "n_gold_files": len(files),
                        "gold_files": files[:20],
                        "gold_basenames": sorted({Path(f).name for f in files}),
                        "patch_len": len(v["patch"])})

    gold = pd.DataFrame(records)
    gold.to_parquet(RES / "gold_patches.parquet", index=False)

    summary = {
        "our_ids": len(ids),
        "ids_with_gold": len(all_found),
        "coverage": round(len(all_found) / max(len(ids), 1), 4),
        "per_source": per_source,
        "n_with_empty_patch": int((gold.n_gold_files == 0).sum()) if len(gold) else 0,
        "gold_file_count_distribution": (
            gold.n_gold_files.value_counts().sort_index().to_dict() if len(gold) else {}),
        "note": ("gold_files come from the dataset's own patch field and do NOT depend on any "
                 "agent run, so they can serve as an independent target"),
    }
    (RES / "gold_patches.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))
    if len(all_found) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
