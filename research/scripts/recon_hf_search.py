"""Reconnaissance: search HuggingFace datasets API for LLM coding-agent trajectory corpora.

Read-only: queries metadata endpoints only, downloads no data files.
Writes JSON to research/_cache/recon/hf_search.json
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

BASE = "https://huggingface.co"
OUT = Path(__file__).resolve().parents[1] / "_cache" / "recon"
OUT.mkdir(parents=True, exist_ok=True)

TERMS = [
    "agent trajectories",
    "swe-bench trajectories",
    "swe-rebench",
    "openhands",
    "swe-agent",
    "coding agent",
    "software engineering agent",
    "swe-smith",
    "r2e-gym",
    "swe-gym",
    "nemotron",
    "terminal-bench",
    "agent rollouts",
    "agentic coding",
    "code agent",
    "trajectories",
    "agent trajectory",
    "bash agent",
    "swe trajectory",
    "software agent traces",
    "tool use traces",
]

S = requests.Session()
S.headers["User-Agent"] = "recon-agent/0.1"


def search(term: str, limit: int = 100) -> list[dict]:
    url = f"{BASE}/api/datasets"
    params = {"search": term, "full": "true", "limit": limit, "sort": "downloads", "direction": "-1"}
    for attempt in range(3):
        try:
            r = S.get(url, params=params, timeout=45)
            if r.status_code == 200:
                return r.json()
            print(f"  ! {term}: HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {term}: {type(e).__name__} {e}")
            time.sleep(2 + attempt * 3)
    return []


def main() -> None:
    all_hits: dict[str, list[dict]] = {}
    for t in TERMS:
        res = search(t)
        all_hits[t] = res
        print(f"{t!r}: {len(res)} hits")
        time.sleep(0.4)

    (OUT / "hf_search.json").write_text(json.dumps(all_hits, ensure_ascii=False, indent=1), encoding="utf-8")

    # Build a deduped index keyed by repo id, merging terms + keeping best download count.
    idx: dict[str, dict] = {}
    for term, rows in all_hits.items():
        for d in rows:
            rid = d.get("id")
            if not rid:
                continue
            e = idx.setdefault(rid, {"id": rid, "_terms": [], "downloads": 0, "likes": 0})
            e["_terms"].append(term)
            e["downloads"] = max(e["downloads"], d.get("downloads") or 0)
            e["likes"] = max(e["likes"], d.get("likes") or 0)
            for k in ("lastModified", "createdAt", "private", "gated", "tags", "description", "author"):
                if d.get(k) is not None:
                    e[k] = d.get(k)
    out = sorted(idx.values(), key=lambda x: -x["downloads"])
    (OUT / "hf_index.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nTOTAL unique repo ids: {len(out)}")
    for e in out[:60]:
        print(f"{e['downloads']:>8} {e['likes']:>4}  {e['id']}")


if __name__ == "__main__":
    main()
