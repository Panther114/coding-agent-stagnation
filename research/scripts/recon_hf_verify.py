"""Verify candidate HF datasets: file tree, row counts, schema, licence, gating.

Metadata-only: uses the HF datasets-server /info + /first-rows endpoints and the
repo tree API. Downloads NO data shards. Writes JSON per candidate.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

BASE = "https://huggingface.co"
DSERVER = "https://datasets-server.huggingface.co"
OUT = Path(__file__).resolve().parents[1] / "_cache" / "recon" / "datasets"
OUT.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    # --- OpenHands / non-SWE-agent scaffolds ---
    "nebius/SWE-rebench-openhands-trajectories",
    "SWE-Gym/OpenHands-SFT-Trajectories",
    "SWE-Gym/OpenHands-Sampled-Trajectories",
    "SWE-Gym/OpenHands-Verifier-Trajectories",
    "nvidia/SWE-Hero-openhands-trajectories",
    "nvidia/SWE-Zero-openhands-trajectories",
    "OpenHands/CodeScout_Eval_Rollouts",
    # --- mini-swe-agent / other harnesses ---
    "Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k",
    "whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces",
    "Intelligent-Internet/swebench-pro-gpt-5-codex-ii-agent-trajectories",
    "MaxDevv/real-pi-coding-agent-traces-sessions",
    "agent-data/misc-merged-claude-code-traces-v1",
    "mondk/agentic-coding-traces",
    "thoughtworks/agentic-coding-trajectories",
    # --- SWE-smith family (SWE-agent scaffold but strong schema) ---
    "SWE-bench/SWE-smith-trajectories",
    "AlienKevin/SWE-smith-rs-minimax-m2.5-trajectories",
    "AlienKevin/SWE-smith-rs-gpt-5-mini-trajectories",
    "r2e-edits/SWE-smith-trajectories-R2E-v2",
    "ricdomolm/SWE-smith-trajectories-harbor",
    # --- R2E-Gym / SWE-Gym ---
    "R2E-Gym/R2EGym-TestingAgent-SFT-Trajectories",
    "ubicloud/filtered-R2EGym-SFT-Trajectories",
    "SWE-Gym/SWE-Gym-Raw",
    "AlienKevin/SWE-ZERO-12M-trajectories",
    # --- Terminal-bench traces (per-step verifier output) ---
    "Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces",
    "0xSero/glm-5.2-nf3-hybrid-terminal-bench-2.1-traces",
    "mlfoundations-dev/terminal-bench-traces-local",
    "hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories",
    "harithoppil/terminal-bench-2-trajectories",
    "DCAgent2/terminal_bench_2",
    # --- JetBrains / misc SWE-bench trajectories ---
    "JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified",
    "SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-2.8K",
    "SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-Rejection-Sampling",
    "AxT-dev/swe-agent-lm-32b-r2e-gym-trajectories",
    # --- step-level telemetry / monitors (directly on-topic) ---
    "sunnydubey1111/agent-trajectory-sentinel",
    "agent-eto/eto-sft-trajectory",
    "kosiasuzu/agenticml-agent-trajectory-dataset",
    # --- Claude Code driven harnesses ---
    "AgentNativeResearchLab/arc-agi3-ls20-agent-trajectories",
    "agent-distillation/Qwen2.5-32B-Instruct_agent_trajectories_2k",
]

S = requests.Session()
S.headers["User-Agent"] = "recon-agent/0.1"


def get_json(url: str, params: dict | None = None, timeout: int = 45):
    for attempt in range(3):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (404, 401, 403):
                return {"_http": r.status_code}
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                return {"_error": f"{type(e).__name__}: {e}"}
            time.sleep(2 + attempt * 3)
    return {"_error": "exhausted"}


def get_text(url: str, timeout: int = 45) -> str | None:
    try:
        r = S.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception:  # noqa: BLE001
        return None
    return None


def human(n) -> str:
    if n is None:
        return "?"
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{u}" if u == "B" else f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}TB"


def verify(rid: str) -> dict:
    rec: dict = {"id": rid}
    # 1) repo metadata (gating, licence, download counts, siblings)
    info = get_json(f"{BASE}/api/datasets/{rid}", {"full": "true"})
    rec["http_info"] = info.get("_http") or info.get("_error")
    if "_http" in info or "_error" in info:
        rec["verified"] = False
        return rec
    rec["verified"] = True
    rec["gated"] = info.get("gated")
    rec["private"] = info.get("private")
    rec["downloads"] = info.get("downloads")
    rec["likes"] = info.get("likes")
    rec["lastModified"] = info.get("lastModified")
    rec["license"] = (info.get("cardData") or {}).get("license")
    rec["tags"] = [t for t in (info.get("tags") or []) if not t.startswith("region:")]

    # 2) file tree with sizes
    tree = get_json(f"{BASE}/api/datasets/{rid}/tree/main", {"recursive": "true"})
    files = []
    if isinstance(tree, list):
        for f in tree:
            if f.get("type") == "file":
                files.append({"path": f.get("path"), "size": f.get("size"), "size_h": human(f.get("size"))})
    rec["files"] = files
    rec["n_files"] = len(files)
    rec["data_files"] = [f for f in files if re.search(r"\.(parquet|jsonl?|arrow|csv|zip|tar|gz)$", f["path"] or "", re.I)]
    rec["total_data_bytes"] = sum(f["size"] or 0 for f in rec["data_files"])

    # 3) datasets-server: splits + row counts + feature schema
    ds = get_json(f"{DSERVER}/info", {"dataset": rid})
    # datasets-server has two shapes: legacy {dataset_info:{cfg:{split:{features:[...]}}}}
    # and current {dataset_info:{cfg:{features:{..}, splits:{split:{num_examples:..}}}}}
    if isinstance(ds, dict) and isinstance(ds.get("dataset_info"), dict):
        di = ds["dataset_info"]
        schemas: dict[str, dict] = {}
        splits_out: dict[str, dict] = {}
        total = 0
        for cfg, meta in di.items():
            if not isinstance(meta, dict):
                continue
            feats = meta.get("features")
            fmap: dict[str, str] = {}
            if isinstance(feats, dict):
                fmap = {k: str(v) for k, v in feats.items()}
            elif isinstance(feats, list):
                for f in feats:
                    if isinstance(f, dict) and "name" in f:
                        fmap[f["name"]] = str(f.get("type"))
            sp_meta = meta.get("splits") or {}
            if isinstance(sp_meta, dict):
                for sp, sm in sp_meta.items():
                    if isinstance(sm, dict):
                        splits_out[f"{cfg}/{sp}"] = {
                            "num_examples": sm.get("num_examples"),
                            "num_bytes": sm.get("num_bytes"),
                        }
                        total += sm.get("num_examples") or 0
                    if fmap:
                        schemas[f"{cfg}/{sp}"] = fmap
            elif fmap:
                schemas[cfg] = fmap
        rec["num_rows_total"] = total or None
        rec["splits"] = splits_out
        rec["schemas"] = {k: sorted(v.keys()) for k, v in schemas.items()}
        rec["schema_detail"] = schemas
        rec["ds_failed"] = ds.get("failed")
        rec["ds_pending"] = ds.get("pending")
        rec["ds_partial"] = ds.get("partial")
    else:
        rec["ds_server"] = (ds.get("_http") or ds.get("_error") or "no-dataset_info") if isinstance(ds, dict) else "bad-response"

    # 4) README / card
    md = get_text(f"{BASE}/datasets/{rid}/raw/main/README.md")
    rec["readme_chars"] = len(md) if md else 0
    if md:
        (OUT / f"{rid.replace('/', '__')}.README.md").write_text(md, encoding="utf-8")
    return rec


def main() -> None:
    only = sys.argv[1:] or CANDIDATES
    results = {}
    for rid in only:
        print(f"== {rid}", flush=True)
        try:
            rec = verify(rid)
        except Exception as e:  # noqa: BLE001
            rec = {"id": rid, "verified": False, "error": f"{type(e).__name__}: {e}"}
        results[rid] = rec
        if rec.get("verified"):
            print(f"   rows={rec.get('num_rows_total')} files={rec.get('n_files')} "
                  f"data={human(rec.get('total_data_bytes'))} lic={rec.get('license')} gated={rec.get('gated')}")
            print(f"   cols={rec.get('schemas')}")
        else:
            print(f"   !! unavailable: {rec.get('http_info') or rec.get('error')}")
        (OUT / f"{rid.replace('/', '__')}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(0.3)

    (OUT / "_all.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT / '_all.json'}")


if __name__ == "__main__":
    main()
