"""Retry the few remaining checks with backoff (HF was rate-limiting)."""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import fsspec
import pyarrow.parquet as pq
import requests

BASE = "https://huggingface.co"
RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
S = requests.Session()
S.headers["User-Agent"] = "recon-agent/0.1"


def get(path: str, params=None, tries=6):
    for i in range(tries):
        try:
            r = S.get(f"{BASE}{path}", params=params, timeout=90)
            if r.status_code == 200:
                return r.json()
            print(f"    HTTP {r.status_code} (try {i+1})")
        except Exception as e:  # noqa: BLE001
            print(f"    {type(e).__name__} (try {i+1})")
        time.sleep(8 * (i + 1))
    return None


def openq(repo: str, rel: str, tries=6):
    url = f"{BASE}/datasets/{repo}/resolve/main/{rel}"
    for i in range(tries):
        try:
            fh = fsspec.open(url, "rb", timeout=120).open()
            return pq.ParquetFile(fh), fh
        except Exception as e:  # noqa: BLE001
            print(f"    open {type(e).__name__} (try {i+1})")
            time.sleep(8 * (i + 1))
    return None, None


print("### A. baseline nebius/SWE-agent-trajectories")
info = get("/api/datasets/nebius/SWE-agent-trajectories", {"full": "true"})
if info:
    print(f"   gated={info.get('gated')} license={(info.get('cardData') or {}).get('license')} "
          f"downloads={info.get('downloads')} likes={info.get('likes')}")
    t = get("/api/datasets/nebius/SWE-agent-trajectories/tree/main", {"recursive": "true"})
    if isinstance(t, list):
        pqf = sorted([f for f in t if f.get("type") == "file" and f["path"].endswith(".parquet")],
                     key=lambda f: f.get("size") or 0)
        print(f"   {len(pqf)} parquet; smallest={pqf[0]['path']} ({(pqf[0].get('size') or 0)/1048576:.1f}MB)")
        pf, fh = openq("nebius/SWE-agent-trajectories", pqf[0]["path"])
        if pf:
            print(f"   rows={pf.metadata.num_rows} cols={pf.schema_arrow.names}")
            col = "messages" if "messages" in pf.schema_arrow.names else pf.schema_arrow.names[-1]
            b = next(pf.iter_batches(batch_size=3, columns=[col]))
            blob = json.dumps(b.to_pylist(), ensure_ascii=False)
            print(f"   [{col}] 'lines total'={blob.count('lines total')} '[File:'={blob.count('[File:')} "
                  f"'OBSERVATION'={blob.count('OBSERVATION')}")
            fh.close()

print("\n### B. verbatim SWE-smith observation")
pf, fh = openq("SWE-bench/SWE-smith-trajectories", "data/tool-00004-of-00008.parquet")
if pf:
    b = next(pf.iter_batches(batch_size=1, columns=["messages"]))
    ml = json.loads(b.to_pylist()[0]["messages"])
    for m in ml[:7]:
        c = m.get("content")
        c = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
        print(f"   role={m.get('role')!r} len={len(c)}")
        print(f"     {c[:700]!r}")
    fh.close()

print("\n### C. Nemotron-Terminal-Corpus inventory")
t = get("/api/datasets/nvidia/Nemotron-Terminal-Corpus/tree/main", {"recursive": "true"})
info = get("/api/datasets/nvidia/Nemotron-Terminal-Corpus", {"full": "true"})
if info:
    print(f"   gated={info.get('gated')} license={(info.get('cardData') or {}).get('license')} "
          f"downloads={info.get('downloads')} likes={info.get('likes')}")
if isinstance(t, list):
    for f in sorted([x for x in t if x.get("type") == "file"], key=lambda x: -(x.get("size") or 0)):
        print(f"     {(f.get('size') or 0)/1048576:9.2f}MB  {f['path']}")

print("\n### D. agent / model distributions")
for repo, rel, cols in [
    ("nvidia/Nemotron-Terminal-Corpus", "dataset_adapters/code.parquet", ["agent", "model", "source"]),
    ("nvidia/Nemotron-Terminal-Corpus", "dataset_adapters/swe.parquet", ["agent", "model"]),
    ("mlfoundations-dev/terminal-bench-traces-local", "data/train-00000-of-00001.parquet", ["agent", "model"]),
]:
    print(f"   -- {repo} :: {rel}")
    pf, fh = openq(repo, rel)
    if not pf:
        continue
    have = [c for c in cols if c in pf.schema_arrow.names]
    print(f"      rows={pf.metadata.num_rows} cols={pf.schema_arrow.names}")
    acc = {c: Counter() for c in have}
    n = 0
    for i in range(min(pf.metadata.num_row_groups, 6)):
        b = pf.read_row_group(i, columns=have)
        for c in have:
            acc[c].update(b.column(c).to_pylist())
        n += b.num_rows
    print(f"      scanned {n}:")
    for c in have:
        print(f"        {c}: {dict(acc[c].most_common(10))}")
    fh.close()
