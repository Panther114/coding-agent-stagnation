"""Probe first rows of candidates for per-step test outcomes / workspace-state signals.

Uses datasets-server /first-rows (a handful of rows, metadata-sized). For each
dataset we classify whether observations contain:
  * per-step test results      -> pytest/unittest verdicts inside step observations
  * SWE-agent editor footer    -> "[File: /abs/path (N lines total)]"
  * per-step reward / score
  * workspace state (diffs, file views)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

DSERVER = "https://datasets-server.huggingface.co"
OUT = Path(__file__).resolve().parents[1] / "_cache" / "recon" / "probe"
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ("nebius/SWE-rebench-openhands-trajectories", "default", "train"),
    ("SWE-Gym/OpenHands-Sampled-Trajectories", "default", "train.raw"),
    ("SWE-Gym/OpenHands-SFT-Trajectories", "default", "train.success.oss"),
    ("SWE-Gym/OpenHands-Verifier-Trajectories", "default", "train.mixture"),
    ("nvidia/SWE-Hero-openhands-trajectories", "default", "train"),
    ("nvidia/SWE-Zero-openhands-trajectories", "default", "train"),
    ("OpenHands/CodeScout_Eval_Rollouts", "codescout_4b/swe_bench_verified", "train"),
    ("Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k", "default", "train"),
    ("whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces", "default", "train"),
    ("agent-data/misc-merged-claude-code-traces-v1", "default", "train"),
    ("thoughtworks/agentic-coding-trajectories", "default", "train"),
    ("mondk/agentic-coding-traces", "default", "train"),
    ("SWE-bench/SWE-smith-trajectories", "default", "tool"),
    ("AlienKevin/SWE-smith-rs-minimax-m2.5-trajectories", "default", "train"),
    ("AlienKevin/SWE-ZERO-12M-trajectories", "default", "train"),
    ("R2E-Gym/R2EGym-TestingAgent-SFT-Trajectories", "default", "train"),
    ("ubicloud/filtered-R2EGym-SFT-Trajectories", "default", "train"),
    ("Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces", "default", "train"),
    ("mlfoundations-dev/terminal-bench-traces-local", "default", "train"),
    ("harithoppil/terminal-bench-2-trajectories", "all", "train"),
    ("JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified", "default", "train"),
    ("SWE-Factory/DeepSWE-Agent-Kimi-K2-Trajectories-2.8K", "default", "train"),
    ("sunnydubey1111/agent-trajectory-sentinel", "default", "train"),
    ("r2e-edits/SWE-smith-trajectories-R2E-v2", "default", "train"),
    ("hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories", "default", "train"),
]

S = requests.Session()
S.headers["User-Agent"] = "recon-agent/0.1"

# ---- signal detectors -------------------------------------------------------
SIGNALS = {
    "editor_footer": re.compile(r"\[File:\s*/\S+\s*\(\d+\s+lines?\s+total\)\]"),
    "pytest_verdict": re.compile(r"\b\d+\s+(?:passed|failed|error)", re.I),
    "pass_fail_word": re.compile(r"\b(PASSED|FAILED|ERROR)\b"),
    "fail_to_pass": re.compile(r"FAIL_TO_PASS|PASS_TO_PASS"),
    "test_cmd": re.compile(r"\b(pytest|unittest|tox|npm test|go test|cargo test|mvn test|gradle test|jest|rspec)\b", re.I),
    "reward_field": re.compile(r"\breward\b", re.I),
    "diff_hunk": re.compile(r"^@@ -\d+|diff --git|\+\+\+ b/", re.M),
    "git_status": re.compile(r"\bgit (diff|status|apply|checkout)\b"),
    "exit_code": re.compile(r"\bexit code\b|\bexit_status\b|returncode", re.I),
    "lines_total": re.compile(r"\d+\s+lines?\s+total"),
    "test_result_tag": re.compile(r"<test_result>|test_result|tests_status|test_output"),
    "resolved_flag": re.compile(r"\bresolved\b"),
    "step_index": re.compile(r'"step"\s*:|\bstep_index\b|\bstep_id\b'),
}

TIMEOUT = 60


def flatten(o, acc: list[str], depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(o, str):
        acc.append(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            acc.append(str(k))
            flatten(v, acc, depth + 1)
    elif isinstance(o, (list, tuple)):
        for v in o:
            flatten(v, acc, depth + 1)
    elif o is not None:
        acc.append(str(o))


def probe(rid: str, cfg: str, split: str) -> dict:
    rec: dict = {"id": rid, "config": cfg, "split": split}
    url = f"{DSERVER}/first-rows"
    try:
        r = S.get(url, params={"dataset": rid, "config": cfg, "split": split, "length": 3}, timeout=TIMEOUT)
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        return rec
    if r.status_code != 200:
        rec["http"] = r.status_code
        rec["error_body"] = r.text[:300]
        return rec
    d = r.json()
    rows = d.get("rows") or []
    rec["n_rows"] = len(rows)
    rec["columns"] = d.get("features") and [f["name"] for f in d["features"]]
    acc: list[str] = []
    for row in rows:
        flatten(row.get("row"), acc)
    blob = "\n".join(acc)
    rec["blob_chars"] = len(blob)
    rec["signals"] = {name: len(rx.findall(blob)) for name, rx in SIGNALS.items()}
    rec["signals"] = {k: v for k, v in rec["signals"].items() if v}
    # keep a bounded excerpt for human/card verification
    rec["excerpt"] = blob[:6000]
    (OUT / f"{rid.replace('/', '__')}__{split.replace('.', '_')}.txt").write_text(blob[:200000], encoding="utf-8")
    return rec


def main() -> None:
    results = {}
    for rid, cfg, split in TARGETS:
        print(f"== {rid} [{cfg}/{split}]", flush=True)
        try:
            rec = probe(rid, cfg, split)
        except Exception as e:  # noqa: BLE001
            rec = {"id": rid, "error": f"{type(e).__name__}: {e}"}
        results[f"{rid}::{cfg}::{split}"] = rec
        if rec.get("error"):
            print(f"   !! {rec['error']}")
        else:
            print(f"   chars={rec.get('blob_chars')} signals={rec.get('signals')}")
        time.sleep(0.2)
    (OUT / "_probe_all.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT / '_probe_all.json'}")


if __name__ == "__main__":
    main()
