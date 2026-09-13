"""Audit: cross-check every row count quoted in RECON_CORPORA.md against saved evidence."""
from __future__ import annotations

import json
import re
from pathlib import Path

RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
DOC = Path(__file__).resolve().parents[1] / "docs" / "RECON_CORPORA.md"

evidence = {}
for src in ("datasets/_all.json", "parquet/_all.json"):
    p = RECON / src
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    for k, v in d.items():
        repo = v.get("repo") or v.get("id") or k.split("::")[0]
        if v.get("num_rows") is not None:
            evidence.setdefault(repo, set()).add(v["num_rows"])
        if v.get("num_rows_total") is not None:
            evidence.setdefault(repo, set()).add(v["num_rows_total"])
for p in (RECON / "datasets").glob("*.json"):
    v = json.loads(p.read_text(encoding="utf-8"))
    if v.get("num_rows_total") is not None:
        evidence.setdefault(v["id"], set()).add(v["num_rows_total"])

# evidence gathered by later scripts (parquet footers for non-sharded/config repos)
for extra in ("_nemotron_r2e.json", "_r2egym_sft.json"):
    p = RECON / extra
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    for k, v in d.items():
        if isinstance(v, dict) and v.get("rows") is not None:
            repo = v.get("repo") or k.split("::")[0]
            evidence.setdefault(repo, set()).add(v["rows"])
        if isinstance(v, dict) and v.get("rows_shard") is not None:
            repo = v.get("repo") or k.split("::")[0]
            evidence.setdefault(repo, set()).add(v["rows_shard"])

text = DOC.read_text(encoding="utf-8")
rows = re.findall(r"(?m)^\| (\d+) \| `([^`]+)` \|([^|]*)\|", text)

print(f"{'#':>3} {'repo':<62} {'quoted':<34} {'evidence'}")
print("-" * 150)
problems = []
for num, repo, cell in rows:
    nums = re.findall(r"\*\*([\d,]+)\*\*", cell)
    quoted = [int(n.replace(",", "")) for n in nums]
    ev = evidence.get(repo, set())
    ok = "?"
    if quoted and ev:
        # each quoted number should appear somewhere in evidence
        missing = [q for q in quoted if q not in ev]
        ok = "OK" if not missing else f"MISMATCH {missing}"
        if missing:
            problems.append((repo, quoted, sorted(ev)))
    elif quoted and not ev:
        ok = "no-evidence"
        problems.append((repo, quoted, "NO EVIDENCE"))
    print(f"{num:>3} {repo:<62} {str(quoted):<34} {sorted(ev) if ev else '-'}  {ok}")

print()
if problems:
    print("!! rows needing attention:")
    for p in problems:
        print("   ", p)
else:
    print("All bolded row counts in the table trace to saved evidence.")
