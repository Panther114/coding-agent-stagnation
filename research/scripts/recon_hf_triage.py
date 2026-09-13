"""Triage the HF index: score candidates for coding-agent trajectory relevance."""
from __future__ import annotations

import json
import re
from pathlib import Path

RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
idx = json.loads((RECON / "hf_index.json").read_text(encoding="utf-8"))

TRAJ = re.compile(r"traj|rollout|trace|session|transcript|conversation|steps?\b|interaction", re.I)
AGENT = re.compile(r"agent|agentic|swe|openhands|aider|claude|codex|solver|terminal|bash|shell|debug", re.I)
CODE = re.compile(r"code|coding|swe|software|repo|github|patch|edit|terminal|bash|shell|py|java|js|ts\b", re.I)
NEG = re.compile(
    r"cc-|common-?crawl|pretrain|persona|vlm|vision|image|speech|audio|translat|math|olympiad|"
    r"leaderboard|Korea|Japan|cultural|medical|bio|chem|law|finance-qa|sentiment|classif|"
    r"embedding|reranker|guard|safety-only",
    re.I,
)

rows = []
for e in idx:
    if e.get("private"):
        continue
    rid = e["id"]
    blob = " ".join(
        [rid, str(e.get("description") or "")]
        + [str(t) for t in (e.get("tags") or [])]
    )
    score = 0.0
    if TRAJ.search(blob):
        score += 3
    if AGENT.search(blob):
        score += 2
    if CODE.search(blob):
        score += 1
    # strong explicit signals in the id
    for kw in ("trajector", "rollout", "session", "trace", "openhands", "aider", "claude-code",
               "codex", "swe-rebench", "swe-smith", "r2e", "swe-gym", "mini-swe", "terminal-bench",
               "terminalbench", "agentic", "agent-"):
        if kw in rid.lower():
            score += 2.5
    if NEG.search(rid):
        score -= 4
    # boost by popularity (log-scaled)
    import math
    score += min(2.0, math.log10(max(1, e["downloads"])) * 0.35)
    score += min(1.0, e["likes"] * 0.02)
    rows.append((score, e))

rows.sort(key=lambda x: -x[0])

print(f"{'score':>5} {'dl':>8} {'likes':>5}  repo_id")
print("-" * 110)
for s, e in rows[:120]:
    print(f"{s:5.1f} {e['downloads']:>8} {e['likes']:>5}  {e['id']}")
    d = (e.get("description") or "").strip().replace("\n", " ")
    if d:
        print(f"          desc: {d[:200]}")
    print(f"          terms: {','.join(sorted(set(e['_terms'])))[:160]}")

(RECON / "triage_scored.json").write_text(
    json.dumps([{"score": round(s, 2), **e} for s, e in rows[:200]], ensure_ascii=False, indent=1),
    encoding="utf-8",
)
