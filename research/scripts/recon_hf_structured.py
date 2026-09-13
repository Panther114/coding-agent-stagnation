"""Structured analysis of first-rows JSON: characterise the observation stream per dataset."""
from __future__ import annotations

import json
import re
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "_cache" / "recon" / "raw"

VERDICT = {
    "pytest_summary": re.compile(r"(?:=+\s*)?\d+\s+(?:passed|failed|error)|collected \d+ items", re.I),
    "testid_verdict": re.compile(r"^\s*(?:PASSED|FAILED|ERROR)\s+\S+", re.M),
    "unittest_ok": re.compile(r"^Ran \d+ tests? in|^OK\b|^FAILED \(", re.M),
    "fail_to_pass": re.compile(r"FAIL_TO_PASS|PASS_TO_PASS"),
    "assertion_err": re.compile(r"AssertionError|Traceback \(most recent call last\)"),
    "exit_nonzero": re.compile(r"exit[_ ]?code[\"'\s:=]+[1-9]\d*|returncode[\"'\s:=]+[1-9]\d*", re.I),
    "reward": re.compile(r"\"reward\"|reward[\"'\s:=]+\d"),
}
STATE = {
    "editor_footer": re.compile(r"\[File:\s*\S+\s*\(\d+\s+lines?\s+total\)\]"),
    "lines_total_any": re.compile(r"\(\d+\s+lines?\s+total\)"),
    "open_file_hdr": re.compile(r"\[File:.*?\]|Here's the files? and directories", re.I),
    "git_diff": re.compile(r"^diff --git |^@@ -\d+", re.M),
    "ls_style": re.compile(r"^[dl-][rwx-]{9}\s+\d+", re.M),
}

TARGET_HINT = {
    "swe-rebench-openhands": "OpenHands (SWE-rebench)",
    "SWE-Gym__OpenHands-Sampled": "OpenHands (SWE-Gym)",
    "SWE-Zero-openhands": "OpenHands (SWE-Zero)",
    "mini_swe_agent_plus": "mini-swe-agent-plus",
    "pi-agent": "PI agent",
    "thoughtworks": "multi-framework amalgam",
    "mondk": "Claude Code / Codex amalgam",
    "SWE-bench__SWE-smith-trajectories": "SWE-agent (SWE-smith)",
    "SWE-smith-rs": "SWE-agent (SWE-smith-rs)",
    "JetBrains-Research": "custom (gpt-5.2 teachers)",
    "SWE-Factory": "DeepSWE agent",
    "agent-trajectory-sentinel": "mixed 33 corpora",
    "Lottolabs": "terminal-bench harness",
    "mlfoundations-dev": "terminal-bench harness",
    "harithoppil": "terminal-bench leaderboard",
    "claude-code-traces": "Claude Code",
    "R2EGym-TestingAgent": "R2E testing agent",
    "hanspeterlyngsoer": "terminal-bench pro",
    "SWE-smith-trajectories-R2E-v2": "SWE-agent (R2E edits)",
}


def short(name: str) -> str:
    for k, v in TARGET_HINT.items():
        if k in name:
            return v
    return "?"


def maybe_json(s: str):
    """Parse a string that is itself a serialised message list."""
    t = s.lstrip()
    if not t or t[0] not in "[{":
        return None
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return None


def walk_observations(o, steps: list[dict], depth: int = 0):
    """Collect (role, text) pairs from any nested messages/conversations structure."""
    if depth > 8:
        return
    if isinstance(o, str):
        parsed = maybe_json(o)
        if parsed is not None:
            walk_observations(parsed, steps, depth + 1)
        return
    if isinstance(o, dict):
        role = o.get("role")
        if role and (isinstance(o.get("content"), (str, list))):
            txt = []
            c = o.get("content")
            if isinstance(c, str):
                txt.append(c)
            elif isinstance(c, list):
                for part in c:
                    if isinstance(part, dict):
                        txt.append(json.dumps(part, ensure_ascii=False))
                    elif isinstance(part, str):
                        txt.append(part)
            for extra in ("function_call", "tool_calls", "tool_call_id", "name", "recipient", "tools"):
                if o.get(extra) is not None:
                    txt.append(json.dumps(o[extra], ensure_ascii=False))
            steps.append({"role": str(role), "text": "\n".join(txt)})
        for v in o.values():
            walk_observations(v, steps, depth + 1)
        # leaf fallback: dict with no role and only scalar values = an anonymous step
        if not role and o and all(not isinstance(v, (dict, list)) for v in o.values()):
            steps.append({"role": "_leaf", "text": json.dumps(o, ensure_ascii=False)})
    elif isinstance(o, list):
        for v in o:
            walk_observations(v, steps, depth + 1)


def raw_string_steps(row, min_chars: int = 300) -> list[dict]:
    """Fallback: treat every long string leaf as a step (for log-blob corpora)."""
    out: list[dict] = []

    def rec(o, key="", depth=0):
        if depth > 6:
            return
        if isinstance(o, str):
            if len(o) >= min_chars:
                out.append({"role": key or "_text", "text": o})
        elif isinstance(o, dict):
            for k, v in o.items():
                rec(v, k, depth + 1)
        elif isinstance(o, list):
            for v in o:
                rec(v, key, depth + 1)

    rec(row)
    return out


rows_out = []
for f in sorted(RAW.glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    rows = d.get("rows") or []
    per_ds = {"file": f.name, "scaffold_hint": short(f.name), "n_rows": len(rows),
              "columns": [x["name"] for x in (d.get("features") or [])],
              "n_steps": 0, "roles": {}, "verdict_kinds": {}, "state_kinds": {},
              "verdict_steps": 0, "state_steps": 0}
    for r in rows:
        steps: list[dict] = []
        walk_observations(r.get("row"), steps)
        if not steps:
            steps = raw_string_steps(r.get("row"))
            per_ds["used_raw_fallback"] = True
        # dedupe consecutive identical
        seen = set()
        uniq = []
        for s in steps:
            k = (s["role"], hash(s["text"][:400]))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(s)
        per_ds["n_steps"] += len(uniq)
        for s in uniq:
            per_ds["roles"][s["role"]] = per_ds["roles"].get(s["role"], 0) + 1
            vk = [n for n, rx in VERDICT.items() if rx.search(s["text"])]
            sk = [n for n, rx in STATE.items() if rx.search(s["text"])]
            if vk:
                per_ds["verdict_steps"] += 1
                for n in vk:
                    per_ds["verdict_kinds"][n] = per_ds["verdict_kinds"].get(n, 0) + 1
            if sk:
                per_ds["state_steps"] += 1
                for n in sk:
                    per_ds["state_kinds"][n] = per_ds["state_kinds"].get(n, 0) + 1
    rows_out.append(per_ds)

print(f"{'dataset file':<62} {'steps':>6} {'v-steps':>7} {'s-steps':>7}  verdict kinds")
print("-" * 165)
for p in sorted(rows_out, key=lambda x: -x["verdict_steps"]):
    vk = ", ".join(f"{k}={v}" for k, v in sorted(p["verdict_kinds"].items(), key=lambda x: -x[1]))
    sk = ", ".join(f"{k}={v}" for k, v in sorted(p["state_kinds"].items(), key=lambda x: -x[1]))
    print(f"{p['file'][:60]:<62} {p['n_steps']:>6} {p['verdict_steps']:>7} {p['state_steps']:>7}  {vk}")
    if sk:
        print(f"{'':<62} {'':>6} {'':>7} {'':>7}  STATE: {sk}")
    print(f"{'':<62} {'':>6} {'':>7} {'':>7}  cols={p['columns']}")

(RAW.parent / "_structured_summary.json").write_text(json.dumps(rows_out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwrote _structured_summary.json")
