"""Decisive per-step analysis on REAL parquet samples.

For each corpus: parse the message list, separate assistant actions from
observations, and count observations carrying an executed-test verdict or a
workspace-state marker. Also computes per-corpus failure-class / framework
distributions where those columns exist.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import fsspec
import pyarrow.parquet as pq

RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"
RAW = RECON / "parquet"

VERDICT = {
    "pytest_summary": re.compile(r"\b\d+\s+(?:passed|failed|error)\b|=\s*\d+ (?:passed|failed)", re.I),
    "testid_verdict": re.compile(r"^\s*(?:PASSED|FAILED|ERROR)\b", re.M),
    "unittest_ran": re.compile(r"^Ran \d+ tests? in|^OK\b|^FAILED \(", re.M),
    "assertion": re.compile(r"AssertionError|^E\s+\w*Error", re.M),
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "fail_to_pass": re.compile(r"FAIL_TO_PASS|PASS_TO_PASS"),
    "exit_nonzero": re.compile(r"exit[_ ]?code[\"'\s:=]+[1-9]\d*|returncode[\"'\s:=]+[1-9]\d*", re.I),
}
STATE = {
    "editor_footer": re.compile(r"\[File:\s*\S+?\(?\s*\d*\s*lines?\s*total\)?\]|\(\d+\s+lines?\s+total\)"),
    "open_file_view": re.compile(r"\[File:|OBSERVATION:\s*Here's the files? and directories", re.I),
    "dir_listing": re.compile(r"Here's the files? and directories|^\s*[dl-][rwx-]{9}\s+\d+", re.M),
    "git_diff": re.compile(r"^diff --git |^@@ -\d+", re.M),
    "code_block_in_obs": re.compile(r"```"),
}

SCAFFOLD = {
    "nebius/SWE-rebench-openhands-trajectories": "OpenHands (SWE-rebench tasks)",
    "nvidia/SWE-Zero-openhands-trajectories": "OpenHands (SWE-rebench tasks)",
    "SWE-Gym/OpenHands-Sampled-Trajectories": "OpenHands (SWE-Gym tasks)",
    "SWE-Gym/OpenHands-Verifier-Trajectories": "OpenHands + LLM judge",
    "OpenHands/CodeScout_Eval_Rollouts": "OpenHands/CodeScout (localisation)",
    "Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k": "mini-swe-agent-plus",
    "AlienKevin/SWE-ZERO-12M-trajectories": "mini-swe-agent-1",
    "JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified": "mini-swe-agent (custom)",
    "whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces": "PI agent harness",
    "SWE-bench/SWE-smith-trajectories": "SWE-agent (SWE-smith)",
    "AlienKevin/SWE-smith-rs-minimax-m2.5-trajectories": "SWE-agent (SWE-smith-rs)",
    "r2e-edits/SWE-smith-trajectories-R2E-v2": "R2E agent",
    "R2E-Gym/R2EGym-TestingAgent-SFT-Trajectories": "R2E-Gym testing agent",
    "ubicloud/filtered-R2EGym-SFT-Trajectories": "R2E-Gym agent",
    "thoughtworks/agentic-coding-trajectories": "multi (see framework counts)",
    "agent-data/misc-merged-claude-code-traces-v1": "Claude Code",
    "sunnydubey1111/agent-trajectory-sentinel": "33 mixed corpora",
    "mlfoundations-dev/terminal-bench-traces-local": "Terminus",
    "hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories": "OpenHands (terminal-bench-pro)",
}


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


OBS_ROLES = {"tool", "function", "observation", "environment", "user", "ipython", "system"}
ACT_ROLES = {"assistant", "agent", "ai"}


def split_steps(msgs):
    """Return list of (obs_text,) for observation messages."""
    obs, acts = [], []
    for m in msgs or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or m.get("from") or m.get("sender") or "").lower()
        parts = []
        for key in ("content", "text", "value", "output", "observation", "tool_result", "function_call"):
            v = m.get(key)
            if v is None:
                continue
            if isinstance(v, str):
                parts.append(v)
            else:
                parts.append(json.dumps(v, ensure_ascii=False))
        txt = "\n".join(parts)
        if not txt.strip():
            continue
        if role in ACT_ROLES:
            acts.append({"role": role, "text": txt})
        else:
            obs.append({"role": role, "text": txt})
    return acts, obs


def analyse(name: str, msgs, per: dict):
    """msgs = list of message lists for one dataset."""
    for ml in msgs:
        acts, obs = split_steps(ml)
        per["n_acts"] += len(acts)
        per["n_obs"] += len(obs)
        for o in obs:
            t = o["text"]
            vk = [n for n, rx in VERDICT.items() if rx.search(t)]
            sk = [n for n, rx in STATE.items() if rx.search(t)]
            if vk:
                per["obs_with_verdict"] += 1
                for n in vk:
                    per["verdict_kinds"][n] += 1
            if sk:
                per["obs_with_state"] += 1
                for n in sk:
                    per["state_kinds"][n] += 1


def load_samples(repo: str) -> list:
    f = next(RAW.glob(f"{repo.replace('/', '__')}*.samples.json"), None)
    if not f:
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    out = []
    for row in data:
        for key in ("messages", "trajectory", "conversations", "chat_messages", "steps"):
            v = row.get(key)
            if v is None:
                continue
            p = parse(v)
            if isinstance(p, dict) and "messages" in p:
                p = p["messages"]
            if isinstance(p, list) and p and isinstance(p[0], dict):
                out.append(p)
                break
    return out


def main() -> None:
    results = {}
    print(f"{'dataset':<60} {'acts':>5} {'obs':>5} {'obs+verdict':>11} {'obs+state':>10}  verdict kinds")
    print("-" * 160)
    for repo in SCAFFOLD:
        msgs = load_samples(repo)
        per = {k: 0 for k in ("n_acts", "n_obs", "obs_with_verdict", "obs_with_state")}
        per["verdict_kinds"] = Counter()
        per["state_kinds"] = Counter()
        if msgs:
            analyse(repo, msgs, per)
        per["verdict_kinds"] = dict(per["verdict_kinds"])
        per["state_kinds"] = dict(per["state_kinds"])
        per["scaffold"] = SCAFFOLD[repo]
        per["n_rows_sampled"] = len(msgs)
        results[repo] = per
        vk = ", ".join(f"{k}={v}" for k, v in sorted(per["verdict_kinds"].items(), key=lambda x: -x[1]))
        sk = ", ".join(f"{k}={v}" for k, v in sorted(per["state_kinds"].items(), key=lambda x: -x[1]))
        print(f"{repo[:58]:<60} {per['n_acts']:>5} {per['n_obs']:>5} {per['obs_with_verdict']:>11} "
              f"{per['obs_with_state']:>10}  {vk}")
        if sk:
            print(f"{'':<60} {'':>5} {'':>5} {'':>11} {'':>10}  STATE: {sk}")

    # ---- column-only distributions on small parquets ----
    extra = {}
    try:
        fs = fsspec.filesystem("https")
        url = "https://huggingface.co/datasets/sunnydubey1111/agent-trajectory-sentinel/resolve/main/data/episodes.parquet"
        with fs.open(url, "rb") as f:
            t = pq.ParquetFile(f).read(columns=["corpus", "failure_class", "n_steps"])
        extra["sentinel_corpus_counts"] = dict(Counter(t.column("corpus").to_pylist()).most_common())
        extra["sentinel_failure_class_counts"] = dict(Counter(
            str(x) for x in t.column("failure_class").to_pylist()).most_common())
    except Exception as e:  # noqa: BLE001
        extra["sentinel_error"] = f"{type(e).__name__}: {e}"
    try:
        fs = fsspec.filesystem("https")
        url = "https://huggingface.co/datasets/thoughtworks/agentic-coding-trajectories/resolve/main/sessions.parquet"
        with fs.open(url, "rb") as f:
            pf = pq.ParquetFile(f)
            af, sr = [], []
            for i in range(pf.metadata.num_row_groups):
                tb = pf.read_row_group(i, columns=["agent_framework", "source_dataset"])
                af += tb.column("agent_framework").to_pylist()
                sr += tb.column("source_dataset").to_pylist()
        extra["thoughtworks_agent_framework"] = dict(Counter(af).most_common())
        extra["thoughtworks_source_dataset"] = dict(Counter(sr).most_common())
    except Exception as e:  # noqa: BLE001
        extra["thoughtworks_error"] = f"{type(e).__name__}: {e}"

    (RECON / "_perstep_real.json").write_text(
        json.dumps({"per_corpus": results, "extra": extra}, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n=== extra distributions ===")
    for k, v in extra.items():
        if isinstance(v, dict):
            print(f"{k}: {json.dumps(v, ensure_ascii=False)[:900]}")
        else:
            print(f"{k}: {v}")
    print(f"\nwrote {RECON / '_perstep_real.json'}")


if __name__ == "__main__":
    main()
