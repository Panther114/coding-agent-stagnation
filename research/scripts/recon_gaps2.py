"""Last gap-fill: baseline SWE-agent schema, a verbatim SWE-smith observation,
Nemotron-Terminal-Corpus inventory, agent-name distributions."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import fsspec
import pyarrow.parquet as pq
import requests

BASE = "https://huggingface.co"
RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
fs = fsspec.filesystem("https", timeout=90)
S = requests.Session()
S.headers["User-Agent"] = "recon-agent/0.1"


def api(path: str, params: dict | None = None):
    r = S.get(f"{BASE}{path}", params=params, timeout=60)
    return r.json() if r.status_code == 200 else {"_http": r.status_code}


print("### 1. baseline nebius/SWE-agent-trajectories (already held) schema")
try:
    info = api("/api/datasets/nebius/SWE-agent-trajectories", {"full": "true"})
    print(f"   gated={info.get('gated')} license={(info.get('cardData') or {}).get('license')} "
          f"downloads={info.get('downloads')}")
    t = api("/api/datasets/nebius/SWE-agent-trajectories/tree/main", {"recursive": "true"})
    if isinstance(t, list):
        pqf = [f for f in t if f.get("type") == "file" and f["path"].endswith(".parquet")]
        pqf.sort(key=lambda f: f.get("size") or 0)
        print(f"   {len(pqf)} parquet files; smallest: {[(f['path'], f.get('size')) for f in pqf[:3]]}")
        rel = pqf[0]["path"]
        url = f"{BASE}/datasets/nebius/SWE-agent-trajectories/resolve/main/{rel}"
        with fs.open(url, "rb") as fh:
            pf = pq.ParquetFile(fh)
            print(f"   {rel}: rows={pf.metadata.num_rows} cols={pf.schema_arrow.names}")
            b = next(pf.iter_batches(batch_size=1))
            r0 = b.to_pylist()[0]
            for k, v in r0.items():
                sv = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                print(f"     {k}: len={len(sv)} :: {sv[:150]!r}")
            # editor footer check on the messages-ish column
            for col in ("messages", "trajectory", "conversations"):
                if col in pf.schema_arrow.names:
                    b2 = next(pf.iter_batches(batch_size=5, columns=[col]))
                    blob = json.dumps(b2.to_pylist(), ensure_ascii=False)
                    print(f"     [{col}] 'lines total'={blob.count('lines total')} "
                          f"'[File:'={blob.count('[File:')} 'OBSERVATION'={blob.count('OBSERVATION')}")
                    break
except Exception as e:  # noqa: BLE001
    print(f"   !! {type(e).__name__}: {e}")

print("\n### 2. verbatim SWE-smith observation (tool cfg)")
try:
    url = f"{BASE}/datasets/SWE-bench/SWE-smith-trajectories/resolve/main/data/tool-00004-of-00008.parquet"
    with fs.open(url, "rb") as fh:
        pf = pq.ParquetFile(fh)
        b = next(pf.iter_batches(batch_size=1, columns=["messages"]))
        ml = json.loads(b.to_pylist()[0]["messages"])
        for m in ml[:8]:
            c = m.get("content")
            c = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
            print(f"   role={m.get('role')!r} len={len(c)} :: {c[:420]!r}")
except Exception as e:  # noqa: BLE001
    print(f"   !! {type(e).__name__}: {e}")

print("\n### 3. nvidia/Nemotron-Terminal-Corpus inventory")
try:
    t = api("/api/datasets/nvidia/Nemotron-Terminal-Corpus/tree/main", {"recursive": "true"})
    info = api("/api/datasets/nvidia/Nemotron-Terminal-Corpus", {"full": "true"})
    print(f"   gated={info.get('gated')} license={(info.get('cardData') or {}).get('license')} "
          f"downloads={info.get('downloads')} likes={info.get('likes')}")
    files = [f for f in t if f.get("type") == "file"] if isinstance(t, list) else []
    for f in sorted(files, key=lambda x: -(x.get("size") or 0)):
        print(f"     {(f.get('size') or 0)/1048576:8.2f}MB  {f['path']}")
except Exception as e:  # noqa: BLE001
    print(f"   !! {type(e).__name__}: {e}")

print("\n### 4. agent / model distributions where those columns exist")
TARGETS = [
    ("nvidia/Nemotron-Terminal-Corpus", "dataset_adapters/code.parquet", ["agent", "model", "source"]),
    ("mlfoundations-dev/terminal-bench-traces-local", "data/train-00000-of-00001.parquet", ["agent", "model"]),
    ("thoughtworks/agentic-coding-trajectories", "sessions.parquet", ["agent_framework", "recorded_model"]),
]
for repo, rel, cols in TARGETS:
    try:
        url = f"{BASE}/datasets/{repo}/resolve/main/{rel}"
        with fs.open(url, "rb") as fh:
            pf = pq.ParquetFile(fh)
            have = [c for c in cols if c in pf.schema_arrow.names]
            if not have:
                print(f"   {repo}: none of {cols} present (cols={pf.schema_arrow.names})")
                continue
            acc = {c: Counter() for c in have}
            n = 0
            for i in range(pf.metadata.num_row_groups):
                b = pf.read_row_group(i, columns=have)
                for c in have:
                    acc[c].update(b.column(c).to_pylist())
                n += b.num_rows
                if n > 400000:
                    break
            print(f"   {repo} ({n} rows scanned):")
            for c in have:
                print(f"      {c}: {dict(acc[c].most_common(12))}")
    except Exception as e:  # noqa: BLE001
        print(f"   {repo}: !! {type(e).__name__}: {e}")
