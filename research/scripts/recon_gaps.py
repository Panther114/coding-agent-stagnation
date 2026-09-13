"""Fill remaining gaps: ticks/xml configs (editor footer), non-parquet repos, misc schemas."""
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
S = requests.Session()
S.headers["User-Agent"] = "recon-agent/0.1"


def tree(repo: str) -> list[dict]:
    r = S.get(f"{BASE}/api/datasets/{repo}/tree/main", params={"recursive": "true"}, timeout=60)
    if r.status_code != 200:
        return []
    return [{"path": f["path"], "size": f.get("size")} for f in r.json() if f.get("type") == "file"]


print("### 1. File inventories for non-parquet repos")
for repo in [
    "SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-2.8K",
    "Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces",
    "mondk/agentic-coding-traces",
    "harithoppil/terminal-bench-2-trajectories",
    "MaxDevv/real-pi-coding-agent-traces-sessions",
    "0xSero/glm-5.2-nf3-hybrid-terminal-bench-2.1-traces",
    "SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-Rejection-Sampling",
    "AlienKevin/SWE-smith-rs-gpt-5-mini-trajectories",
    "sunnydubey1111/agent-trajectory-sentinel",
    "nvidia/Nemotron-Terminal-Corpus",
]:
    fs = tree(repo)
    exts = Counter(Path(f["path"]).suffix for f in fs)
    total = sum(f["size"] or 0 for f in fs)
    print(f"\n{repo}: {len(fs)} files, {total/1048576:.1f}MB, exts={dict(exts)}")
    for f in sorted(fs, key=lambda x: -(x["size"] or 0))[:5]:
        print(f"    {(f['size'] or 0)/1048576:8.2f}MB  {f['path']}")

print("\n\n### 2. SWE-smith ticks / xml configs -> editor footer check")
EDITOR_FOOTER = re.compile(r"\[\s*File:\s*[^\]]*?\(\s*\d+\s+lines?\s+total\s*\)")
VERDICT = {
    "pytest_summary": re.compile(r"\b\d+\s+(?:passed|failed|error)\b|=\s*\d+ (?:passed|failed)", re.I),
    "testid_verdict": re.compile(r"^\s*(?:PASSED|FAILED|ERROR)\b", re.M),
    "assertion": re.compile(r"AssertionError|^E\s{1,4}\w*Error", re.M),
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "exit_nonzero": re.compile(r"exit[_ ]?code[\"'\s:=]+[1-9]\d*|returncode[\"'\s:=]+[1-9]\d*", re.I),
}


def parse(s):
    if isinstance(s, (list, dict)):
        return s
    if not isinstance(s, str) or not s.lstrip()[:1] in "[{":
        return None
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return None


def scan(repo: str, rel: str, col: str, n: int = 60) -> dict:
    url = f"{BASE}/datasets/{repo}/resolve/main/{rel}"
    fs = fsspec.filesystem("https")
    per = {"repo": repo, "path": rel, "rows": 0, "editor_footer": 0, "obs": 0,
           "obsV": 0, "kinds": Counter()}
    with fs.open(url, "rb") as f:
        pf = pq.ParquetFile(f)
        per["shard_rows"] = pf.metadata.num_rows
        per["cols"] = pf.schema_arrow.names
        for batch in pf.iter_batches(batch_size=40, columns=[col]):
            for row in batch.to_pylist():
                if per["rows"] >= n:
                    break
                per["rows"] += 1
                ml = parse(row.get(col))
                if not isinstance(ml, list):
                    continue
                for m in ml:
                    if not isinstance(m, dict):
                        continue
                    role = str(m.get("role") or "").lower()
                    if role in ("assistant", "agent", "ai"):
                        continue
                    txt = m.get("content")
                    txt = txt if isinstance(txt, str) else json.dumps(txt, ensure_ascii=False)
                    per["obs"] += 1
                    if EDITOR_FOOTER.search(txt or ""):
                        per["editor_footer"] += 1
                    for k, rx in VERDICT.items():
                        if rx.search(txt or ""):
                            per["kinds"][k] += 1
                if any(rx.search(json.dumps(ml, ensure_ascii=False)) for rx in VERDICT.values()):
                    per["obsV"] += 1
            if per["rows"] >= n:
                break
    per["kinds"] = dict(per["kinds"])
    return per


for cfg in ("ticks", "xml", "tool"):
    for idx in ("00001", "00004"):
        rel = f"data/{cfg}-{idx}-of-00008.parquet"
        try:
            r = scan("SWE-bench/SWE-smith-trajectories", rel, "messages", 60)
            print(f"{rel}: rows={r['rows']} obs={r['obs']} editor_footer={r['editor_footer']} "
                  f"rowsWithVerdict={r['obsV']} kinds={r['kinds']}")
        except Exception as e:  # noqa: BLE001
            print(f"{rel}: !! {type(e).__name__}: {e}")

print("\n### 3. SWE-smith-rs gpt-5-mini correct shards")
fs = tree("AlienKevin/SWE-smith-rs-gpt-5-mini-trajectories")
for f in sorted(fs, key=lambda x: x["path"])[:6]:
    print(f"    {(f['size'] or 0)/1048576:6.2f}MB  {f['path']}")
