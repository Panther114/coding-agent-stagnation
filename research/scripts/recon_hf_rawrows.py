"""Save raw first-rows JSON per candidate so message structure can be parsed exactly."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

DSERVER = "https://datasets-server.huggingface.co"
RAW = Path(__file__).resolve().parents[1] / "_cache" / "recon" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ("nebius/SWE-rebench-openhands-trajectories", "default", "train"),
    ("SWE-Gym/OpenHands-Sampled-Trajectories", "default", "train.raw"),
    ("nvidia/SWE-Zero-openhands-trajectories", "default", "train"),
    ("OpenHands/CodeScout_Eval_Rollouts", "codescout_4b/swe_bench_verified", "train"),
    ("Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k", "default", "train"),
    ("whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces", "default", "train"),
    ("thoughtworks/agentic-coding-trajectories", "default", "train"),
    ("mondk/agentic-coding-traces", "default", "train"),
    ("SWE-bench/SWE-smith-trajectories", "default", "tool"),
    ("AlienKevin/SWE-smith-rs-minimax-m2.5-trajectories", "default", "train"),
    ("JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified", "default", "train"),
    ("SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-2.8K", "default", "train"),
    ("sunnydubey1111/agent-trajectory-sentinel", "default", "train"),
    ("Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces", "default", "train"),
    ("mlfoundations-dev/terminal-bench-traces-local", "default", "train"),
    ("harithoppil/terminal-bench-2-trajectories", "all", "train"),
    ("agent-data/misc-merged-claude-code-traces-v1", "default", "train"),
    ("R2E-Gym/R2EGym-TestingAgent-SFT-Trajectories", "default", "train"),
    ("hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories", "default", "train"),
    ("r2e-edits/SWE-smith-trajectories-R2E-v2", "default", "train"),
    ("Intelligent-Internet/swebench-pro-gpt-5-codex-ii-agent-trajectories", "default", "train"),
    ("Kwaipilot/... ", None, None),
]

S = requests.Session()
S.headers["User-Agent"] = "recon-agent/0.1"
ok = []
for rid, cfg, split in TARGETS:
    if cfg is None:
        continue
    out = RAW / f"{rid.replace('/', '__')}__{cfg.replace('/', '_')}__{split.replace('.', '_')}.json"
    if out.exists():
        ok.append(rid)
        print(f"cached {rid}")
        continue
    try:
        r = S.get(f"{DSERVER}/first-rows",
                  params={"dataset": rid, "config": cfg, "split": split, "length": 2}, timeout=90)
    except Exception as e:  # noqa: BLE001
        print(f"!! {rid}: {type(e).__name__} {e}")
        continue
    if r.status_code == 200:
        out.write_text(json.dumps(r.json(), ensure_ascii=False, indent=1), encoding="utf-8")
        ok.append(rid)
        print(f"ok   {rid}  ({len(r.content)//1024}KB)")
    else:
        print(f"!! {rid}: HTTP {r.status_code}")
    time.sleep(0.3)

print(f"\nsaved {len(ok)} raw row files")
