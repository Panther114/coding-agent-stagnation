"""List the smallest parquet shards per candidate (for targeted row-group reads)."""
from __future__ import annotations

import json
from pathlib import Path

RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
d = json.loads((RECON / "datasets" / "_all.json").read_text(encoding="utf-8"))

REPOS = [
    "nebius/SWE-rebench-openhands-trajectories",
    "SWE-Gym/OpenHands-Sampled-Trajectories",
    "SWE-Gym/OpenHands-Verifier-Trajectories",
    "SWE-Gym/OpenHands-SFT-Trajectories",
    "nvidia/SWE-Zero-openhands-trajectories",
    "nvidia/SWE-Hero-openhands-trajectories",
    "OpenHands/CodeScout_Eval_Rollouts",
    "Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k",
    "whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces",
    "SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-2.8K",
    "JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified",
    "SWE-bench/SWE-smith-trajectories",
    "AlienKevin/SWE-smith-rs-minimax-m2.5-trajectories",
    "thoughtworks/agentic-coding-trajectories",
    "sunnydubey1111/agent-trajectory-sentinel",
    "mlfoundations-dev/terminal-bench-traces-local",
    "Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces",
    "mondk/agentic-coding-traces",
    "r2e-edits/SWE-smith-trajectories-R2E-v2",
    "agent-data/misc-merged-claude-code-traces-v1",
    "harithoppil/terminal-bench-2-trajectories",
    "hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories",
    "R2E-Gym/R2EGym-TestingAgent-SFT-Trajectories",
    "ubicloud/filtered-R2EGym-SFT-Trajectories",
    "AlienKevin/SWE-ZERO-12M-trajectories",
    "MaxDevv/real-pi-coding-agent-traces-sessions",
    "0xSero/glm-5.2-nf3-hybrid-terminal-bench-2.1-traces",
]

for repo in REPOS:
    r = d.get(repo)
    if not r:
        print(f"{repo}   -- NOT in verify set")
        continue
    pqs = [f for f in r.get("data_files", []) if (f["path"] or "").lower().endswith(".parquet")]
    pqs.sort(key=lambda f: f["size"] or (1 << 62))
    total = sum(f["size"] or 0 for f in pqs)
    print(f"{repo}   rows={r.get('num_rows_total')}  n_pq={len(pqs)}  total={total/1048576:.1f}MB")
    for f in pqs[:3]:
        print(f"      {f['path']}   {f['size_h']}")
    if len(pqs) > 3:
        print(f"      ... +{len(pqs)-3} more")
