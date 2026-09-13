"""Final verification round: editor-footer presence, single-turn vs multi-step, jsonl shapes."""
from __future__ import annotations

import io
import json
import re
from collections import Counter
from pathlib import Path

import fsspec
import pyarrow.parquet as pq
import requests

BASE = "https://huggingface.co"
RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
fs = fsspec.filesystem("https")
S = requests.Session()
S.headers["User-Agent"] = "recon-agent/0.1"


def rows_of(repo: str, rel: str, col: str, n: int = 3):
    url = f"{BASE}/datasets/{repo}/resolve/main/{rel}"
    with fs.open(url, "rb") as f:
        pf = pq.ParquetFile(f)
        for b in pf.iter_batches(batch_size=n, columns=[col]):
            return b.to_pylist()
    return []


print("### A. SWE-smith: is the SWE-agent editor footer present at all?")
for cfg in ("tool", "ticks"):
    rel = f"data/{cfg}-00004-of-00008.parquet"
    for row in rows_of("SWE-bench/SWE-smith-trajectories", rel, "messages", 1):
        ml = json.loads(row["messages"])
        blob = json.dumps(ml, ensure_ascii=False)
        print(f"\n  cfg={cfg}: n_msg={len(ml)}")
        print(f"    'lines total' occurrences : {blob.count('lines total')}")
        print(f"    '[File:' occurrences       : {blob.count('[File:')}")
        print(f"    'OBSERVATION' occurrences  : {blob.count('OBSERVATION')}")
        print(f"    '<output>' occurrences     : {blob.count('<output>')}")
        print(f"    roles: {dict(Counter(m.get('role') for m in ml))}")
        # show one non-assistant message verbatim
        for m in ml:
            if m.get("role") not in ("assistant", "system"):
                c = m.get("content")
                if isinstance(c, list):
                    c = " ".join(json.dumps(x, ensure_ascii=False) for x in c)
                print(f"    first obs role={m.get('role')} content[:600]:")
                print("      " + repr(str(c)[:600]))
                break

print("\n\n### B. SWE-agent-trajectories baseline (held) - does IT have the footer?")
try:
    for row in rows_of("nebius/SWE-agent-trajectories", "data/train-00000-of-00012.parquet", "messages", 1):
        ml = row["messages"]
        ml = json.loads(ml) if isinstance(ml, str) else ml
        blob = json.dumps(ml, ensure_ascii=False)
        print(f"  n_msg={len(ml)} 'lines total'={blob.count('lines total')} '[File:'={blob.count('[File:')}")
except Exception as e:  # noqa: BLE001
    print(f"  !! {type(e).__name__}: {e}")

print("\n\n### C. SWE-Gym/OpenHands-Verifier: does the judge see the full trajectory?")
for row in rows_of("SWE-Gym/OpenHands-Verifier-Trajectories",
                   "data/train.offpolicy-00000-of-00001.parquet", "messages", 1):
    ml = json.loads(row["messages"]) if isinstance(row["messages"], str) else row["messages"]
    print(f"  n_msg={len(ml)} roles={[m.get('role') for m in ml]}")
    for i, m in enumerate(ml):
        c = m.get("content")
        c = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
        print(f"   [{i}] role={m.get('role')} len={len(c)} :: {c[:220]!r}")
    break

print("\n\n### D. jsonl corpora: head bytes only (range request)")
JSONL = [
    ("harithoppil/terminal-bench-2-trajectories", "data/leaderboard_trajectories.jsonl"),
    ("SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-2.8K",
     "DeepSWE-Agent-Kimi-K2-Trajectories-2.8K.jsonl"),
    ("mondk/agentic-coding-traces",
     ".raw_sources/hf_downloads/AletheiaResearch__Kimi-K3-Codex/"
     "rollout-2026-07-19T17-56-55-019f7b86-215e-7c10-b072-46d0e8fd4384.jsonl"),
    ("MaxDevv/real-pi-coding-agent-traces-sessions",
     "deepflame-bot-pi-publish-2026-04-23T12-11-29-619Z_019dba40-9bd3-72d8-885a-91c6bc309c8a.jsonl"),
]
for repo, rel in JSONL:
    url = f"{BASE}/datasets/{repo}/resolve/main/{rel}"
    print(f"\n  == {repo} :: {rel}")
    try:
        with fs.open(url, "rb") as f:
            head = f.read(400_000)
        lines = head.split(b"\n")
        print(f"     got {len(head)} bytes, {len(lines)} lines in head")
        obj = json.loads(lines[0].decode("utf-8", "replace"))
        if isinstance(obj, dict):
            print(f"     keys: {sorted(obj.keys())}")
            for k, v in obj.items():
                sv = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                print(f"       {k}: type={type(v).__name__} len={len(sv)} :: {sv[:160]!r}")
        else:
            print(f"     first obj type={type(obj).__name__}")
    except Exception as e:  # noqa: BLE001
        print(f"     !! {type(e).__name__}: {e}")

print("\n\n### E. nvidia/Nemotron-Terminal-Corpus + Lottolabs result.json shape")
for repo, rel in [("nvidia/Nemotron-Terminal-Corpus", "dataset_adapters/swe.parquet"),
                  ("nvidia/Nemotron-Terminal-Corpus", "dataset_adapters/code.parquet")]:
    try:
        url = f"{BASE}/datasets/{repo}/resolve/main/{rel}"
        with fs.open(url, "rb") as f:
            pf = pq.ParquetFile(f)
            print(f"  {rel}: rows={pf.metadata.num_rows} cols={pf.schema_arrow.names}")
            print(f"     types: {[str(t) for t in pf.schema_arrow.types]}")
            b = next(pf.iter_batches(batch_size=1))
            r0 = b.to_pylist()[0]
            for k, v in r0.items():
                sv = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                print(f"       {k}: len={len(sv)} :: {sv[:200]!r}")
    except Exception as e:  # noqa: BLE001
        print(f"  {rel}: !! {type(e).__name__}: {e}")
