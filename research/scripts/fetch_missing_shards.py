"""Fetch the remaining shards through the HuggingFace mirror.

The machine cannot reach ``huggingface.co`` but *can* reach ``hf-mirror.com`` (verified: HTTP 200
in ~200 ms), so the "no network" conclusion the watcher drew was a false negative that cost the
whole blocked-work list.  ``huggingface_hub`` honours ``HF_ENDPOINT``, so pointing it at the
mirror is enough.

Shards are downloaded one at a time to ``data/raw/<corpus>/`` so an interrupted run keeps whatever
finished, then each is verified by opening it with PyArrow and reporting its row count - a
truncated file is caught here rather than by a parser three steps later.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

REPOS = {
    "nebius": ("nebius/SWE-agent-trajectories", 12),
    "tb2": ("yoonholee/terminalbench-trajectories", 2),
}


def verify(path: Path) -> dict:
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    return {"bytes": path.stat().st_size, "rows": pf.metadata.num_rows,
            "cols": len(pf.schema_arrow.names)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="all", choices=["all", *REPOS])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from huggingface_hub import hf_hub_download

    ledger = {"endpoint": os.environ["HF_ENDPOINT"], "started": time.strftime("%F %T"),
              "shards": [], "skipped": [], "failed": []}

    targets = REPOS if args.corpus == "all" else {args.corpus: REPOS[args.corpus]}
    for corpus, (repo, n) in targets.items():
        out = RAW / corpus
        out.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            name = f"train-{i:05d}-of-{n:05d}.parquet"
            dest = out / name
            if dest.exists() and dest.stat().st_size > 1_000_000:
                try:
                    info = verify(dest)
                    print(f"  [have] {corpus}/{name}  {info['bytes']:,} B  "
                          f"{info['rows']:,} rows", flush=True)
                    ledger["skipped"].append({"corpus": corpus, "shard": name, **info})
                    continue
                except Exception as e:
                    print(f"  [redownload] {corpus}/{name} unreadable: {e}", flush=True)
            if args.dry_run:
                print(f"  [need] {corpus}/{name}", flush=True)
                continue
            t0 = time.time()
            try:
                got = hf_hub_download(repo_id=repo, filename=f"data/{name}",
                                      repo_type="dataset", local_dir=str(out.parent / "_hub"),
                                      endpoint=os.environ["HF_ENDPOINT"])
                src = Path(got)
                if dest.exists():
                    dest.unlink()
                src.replace(dest)
                info = verify(dest)
                info.update({"corpus": corpus, "shard": name, "seconds": round(time.time() - t0, 1)})
                ledger["shards"].append(info)
                print(f"  [ok]   {corpus}/{name}  {info['bytes']:,} B  {info['rows']:,} rows  "
                      f"{info['seconds']}s", flush=True)
            except Exception as e:
                msg = f"{type(e).__name__}: {str(e)[:200]}"
                ledger["failed"].append({"corpus": corpus, "shard": name, "error": msg})
                print(f"  [FAIL] {corpus}/{name}  {msg}", flush=True)

    ledger["finished"] = time.strftime("%F %T")
    (ROOT / "data" / "raw" / "download_ledger.json").write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\ndownloaded {len(ledger['shards'])}, already had {len(ledger['skipped'])}, "
          f"failed {len(ledger['failed'])}")
    total = sum(s["rows"] for s in ledger["shards"] + ledger["skipped"])
    print(f"rows now present across touched shards: {total:,}")
    if ledger["failed"]:
        print("FAILED SHARDS:")
        for f in ledger["failed"]:
            print(f"  - {f['corpus']}/{f['shard']}: {f['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
