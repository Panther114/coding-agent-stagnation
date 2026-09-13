"""Read real Parquet row groups over HTTP (footer + first row group only).

Ground truth for row counts, schema and — crucially — untruncated observation
content, without downloading whole shards.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fsspec
import pyarrow.parquet as pq

RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
OUT = RECON / "parquet"
OUT.mkdir(parents=True, exist_ok=True)

# repo -> data file paths chosen to be small/representative
PICKS_FILE = RECON / "parquet_picks.json"
PICKS = json.loads(PICKS_FILE.read_text(encoding="utf-8")) if PICKS_FILE.exists() else {}

allrec = json.loads((RECON / "datasets" / "_all.json").read_text(encoding="utf-8"))


def smallest_parquet(repo: str, n: int = 1) -> list[str]:
    rec = allrec.get(repo) or {}
    pq_files = [f for f in (rec.get("data_files") or []) if f["path"].lower().endswith(".parquet")]
    pq_files.sort(key=lambda f: f["size"] or 1 << 62)
    return [f["path"] for f in pq_files[:n]]


def probe(repo: str, rel: str, sample_rows: int = 2) -> dict:
    url = f"https://huggingface.co/datasets/{repo}/resolve/main/{rel}"
    fs = fsspec.filesystem("https")
    rec: dict = {"repo": repo, "path": rel, "url": url}
    with fs.open(url, "rb") as f:
        pf = pq.ParquetFile(f)
        rec["num_rows"] = pf.metadata.num_rows
        rec["num_row_groups"] = pf.metadata.num_row_groups
        rec["num_columns"] = pf.metadata.num_columns
        rec["schema"] = pf.schema_arrow.names
        rec["schema_types"] = {k: str(v) for k, v in zip(pf.schema_arrow.names, pf.schema_arrow.types)}
        rec["row_group0_rows"] = pf.metadata.row_group(0).num_rows
        tbl = pf.read_row_group(0)
        rows = tbl.slice(0, sample_rows).to_pylist()
        rec["samples"] = rows
    return rec


def main() -> None:
    targets = PICKS
    if not targets:
        print("pass JSON {repo: [paths...]}")
        return
    results = {}
    for repo, paths in targets.items():
        for rel in paths:
            print(f"== {repo} :: {rel}", flush=True)
            try:
                rec = probe(repo, rel)
            except Exception as e:  # noqa: BLE001
                rec = {"repo": repo, "path": rel, "error": f"{type(e).__name__}: {e}"}
            results[f"{repo}::{rel}"] = rec
            if rec.get("error"):
                print(f"   !! {rec['error']}")
            else:
                print(f"   rows={rec['num_rows']} rgs={rec['num_row_groups']} "
                      f"rg0={rec['row_group0_rows']} cols={rec['schema']}")
                for i, s in enumerate(rec["samples"]):
                    for k, v in s.items():
                        sv = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                        print(f"   [{i}].{k}: len={len(sv)} :: {sv[:180]!r}")
            name = f"{repo.replace('/', '__')}__{rel.replace('/', '_')}.json"
            (OUT / name).write_text(json.dumps(rec, ensure_ascii=False, indent=1)[:0] or "", encoding="utf-8")
            # write samples separately (could be big)
            (OUT / name).write_text(
                json.dumps({k: v for k, v in rec.items() if k != "samples"}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            if rec.get("samples"):
                (OUT / (name.replace(".json", ".samples.json"))).write_text(
                    json.dumps(rec["samples"], ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "_all.json").write_text(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "samples"}
                                               for k, v in results.items()}, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
