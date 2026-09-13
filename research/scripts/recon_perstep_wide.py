"""Final quantitative pass: per-step verdict rates on a wide row sample (~120 rows/dataset).

Reads only the leading batches of one parquet shard per dataset (range requests),
so no shard is downloaded whole.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import fsspec
import pyarrow.parquet as pq

RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
N_ROWS = 120

TARGETS = [
    # (repo, relative parquet path, message column)
    ("nebius/SWE-rebench-openhands-trajectories", "trajectories.parquet", "trajectory"),
    ("nvidia/SWE-Zero-openhands-trajectories", "data/train-00063-of-00064.parquet", "trajectory"),
    ("SWE-Gym/OpenHands-Sampled-Trajectories", "data/train.raw-00000-of-00003.parquet", "messages"),
    ("SWE-Gym/OpenHands-SFT-Trajectories", "data/train.success.oss-00000-of-00001.parquet", "messages"),
    ("SWE-Gym/OpenHands-Verifier-Trajectories", "data/train.offpolicy-00000-of-00001.parquet", "messages"),
    ("Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k", "data/train-00002-of-00047.parquet", "messages"),
    ("whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces", "data/train-00000-of-00002.parquet", "messages"),
    ("JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified", "data/train-00000-of-00001.parquet", "messages"),
    ("SWE-bench/SWE-smith-trajectories", "data/tool-00004-of-00008.parquet", "messages"),
    ("AlienKevin/SWE-smith-rs-minimax-m2.5-trajectories", "data/train-00020-of-00021.parquet", "messages"),
    ("AlienKevin/SWE-smith-rs-gpt-5-mini-trajectories", "data/train-00000-of-00018.parquet", "messages"),
    ("r2e-edits/SWE-smith-trajectories-R2E-v2", "data/train-00000-of-00001.parquet", "messages"),
    ("ubicloud/filtered-R2EGym-SFT-Trajectories", "filtered_R2EGym-SFT-Trajectories_32k.parquet", "messages"),
    ("R2E-Gym/R2EGym-TestingAgent-SFT-Trajectories", "data/train-00000-of-00001.parquet", "messages"),
    ("AlienKevin/SWE-ZERO-12M-trajectories", "data/train-00757.parquet", "messages"),
    ("mlfoundations-dev/terminal-bench-traces-local", "data/train-00000-of-00001.parquet", "conversations"),
    ("hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories", "data/train-00000-of-00001.parquet", "messages"),
    ("thoughtworks/agentic-coding-trajectories", "sessions.parquet", "messages_json"),
    ("agent-data/misc-merged-claude-code-traces-v1", "data/train-00001-of-00011.parquet", "messages_json"),
]

VERDICT = {
    "pytest_summary": re.compile(r"\b\d+\s+(?:passed|failed|error)\b|=\s*\d+ (?:passed|failed)", re.I),
    "testid_verdict": re.compile(r"^\s*(?:PASSED|FAILED|ERROR)\b", re.M),
    "unittest_ran": re.compile(r"^Ran \d+ tests? in|^OK\b|^FAILED \(", re.M),
    "assertion": re.compile(r"AssertionError|^E\s{1,4}\w*Error", re.M),
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "fail_to_pass": re.compile(r"FAIL_TO_PASS|PASS_TO_PASS"),
    "exit_nonzero": re.compile(r"exit[_ ]?code[\"'\s:=]+[1-9]\d*|returncode[\"'\s:=]+[1-9]\d*", re.I),
}
STATE = {
    "editor_lines_total": re.compile(r"\(\d+\s+lines?\s+total\)|\[\s*File:\s*[^\]]*\(\d+\s+lines?\s+total\)"),
    "open_file_view": re.compile(r"\[File:", re.I),
    "dir_listing": re.compile(r"Here's the files? and directories", re.I),
    "git_diff": re.compile(r"^diff --git |^@@ -\d+", re.M),
}
ACT_ROLES = {"assistant", "agent", "ai", "gpt", "model"}
OBS_ROLES = {"tool", "function", "observation", "environment", "user", "system", "ipython"}


def parse(s):
    if isinstance(s, (list, dict)):
        return s
    if not isinstance(s, str):
        return None
    t = s.lstrip()
    if not t or t[0] not in "[{":
        return None
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return None


def steps_of(msgs):
    acts, obs = [], []
    for m in msgs or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or m.get("from") or m.get("sender") or m.get("type") or "").lower()
        parts = []
        for key in ("content", "text", "value", "output", "observation", "tool_result",
                    "tool_calls", "function_call"):
            v = m.get(key)
            if v is None:
                continue
            parts.append(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
        txt = "\n".join(parts)
        if not txt.strip():
            continue
        (acts if role in ACT_ROLES else obs).append((role, txt))
    return acts, obs


def run(repo: str, rel: str, col: str) -> dict:
    url = f"https://huggingface.co/datasets/{repo}/resolve/main/{rel}"
    fs = fsspec.filesystem("https")
    per = {"repo": repo, "path": rel, "col": col, "rows_read": 0, "acts": 0, "obs": 0,
           "obs_verdict": 0, "obs_state": 0, "verdict_kinds": Counter(), "state_kinds": Counter(),
           "rows_with_any_verdict": 0, "steps_per_row": []}
    extra_cols_seen = set()
    with fs.open(url, "rb") as f:
        pf = pq.ParquetFile(f)
        per["shard_rows"] = pf.metadata.num_rows
        want = [col] + [c for c in ("resolved", "exit_status", "agent_framework", "source_dataset", "model")
                        if c in pf.schema_arrow.names]
        for batch in pf.iter_batches(batch_size=40, columns=want):
            d = batch.to_pylist()
            for row in d:
                if per["rows_read"] >= N_ROWS:
                    break
                per["rows_read"] += 1
                ml = parse(row.get(col))
                if isinstance(ml, dict):
                    ml = ml.get("messages") or ml.get("conversations") or ml.get("steps")
                if not isinstance(ml, list):
                    continue
                acts, obs = steps_of(ml)
                per["acts"] += len(acts)
                per["obs"] += len(obs)
                per["steps_per_row"].append(len(acts))
                hit = False
                for _r, t in obs:
                    vk = [n for n, rx in VERDICT.items() if rx.search(t)]
                    sk = [n for n, rx in STATE.items() if rx.search(t)]
                    if vk:
                        per["obs_verdict"] += 1
                        hit = True
                        for n in vk:
                            per["verdict_kinds"][n] += 1
                    if sk:
                        per["obs_state"] += 1
                        for n in sk:
                            per["state_kinds"][n] += 1
                if hit:
                    per["rows_with_any_verdict"] += 1
            if per["rows_read"] >= N_ROWS:
                break
    per["verdict_kinds"] = dict(per["verdict_kinds"])
    per["state_kinds"] = dict(per["state_kinds"])
    if per["steps_per_row"]:
        s = sorted(per["steps_per_row"])
        per["steps_median"] = s[len(s) // 2]
        per["steps_max"] = s[-1]
    # rates
    per["rate_obs_verdict"] = round(per["obs_verdict"] / per["obs"], 4) if per["obs"] else None
    per["rate_rows_verdict"] = round(per["rows_with_any_verdict"] / per["rows_read"], 4) if per["rows_read"] else None
    return per


def main() -> None:
    out = {}
    print(f"{'dataset':<58} {'rows':>4} {'acts':>5} {'obs':>5} {'obsV':>5} {'%obsV':>6} "
          f"{'rowsV':>6} {'%rowsV':>7} {'obsS':>5}  kinds")
    print("-" * 190)
    for repo, rel, col in TARGETS:
        try:
            per = run(repo, rel, col)
        except Exception as e:  # noqa: BLE001
            per = {"repo": repo, "path": rel, "error": f"{type(e).__name__}: {e}"}
        out[f"{repo}::{rel}"] = per
        if per.get("error"):
            print(f"{repo[:56]:<58} !! {per['error']}")
            continue
        ev = ", ".join(f"{k}={v}" for k, v in sorted(per["verdict_kinds"].items(), key=lambda x: -x[1]))
        sv = ", ".join(f"{k}={v}" for k, v in sorted(per["state_kinds"].items(), key=lambda x: -x[1]))
        print(f"{repo[:56]:<58} {per['rows_read']:>4} {per['acts']:>5} {per['obs']:>5} "
              f"{per['obs_verdict']:>5} {str(per['rate_obs_verdict']):>6} "
              f"{per['rows_with_any_verdict']:>6} {str(per['rate_rows_verdict']):>7} "
              f"{per['obs_state']:>5}  {ev}")
        if sv:
            print(f"{'':<58} {'':>4} {'':>5} {'':>5} {'':>5} {'':>6} {'':>6} {'':>7} {'':>5}  STATE: {sv}")
    (RECON / "_perstep_wide.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {RECON / '_perstep_wide.json'}")


if __name__ == "__main__":
    main()
