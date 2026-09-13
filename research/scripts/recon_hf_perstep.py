"""Deep per-step analysis: does each candidate's OBSERVATION stream carry test verdicts?

For every candidate, fetch a few rows, split each into steps (assistant action ->
next observation), and count how many observations contain an *executed test
verdict* or *workspace state* marker. This distinguishes "final score only"
datasets from genuinely per-step-verified ones.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "_cache" / "recon" / "probe"
data = json.loads((PROBE / "_probe_all.json").read_text(encoding="utf-8"))

# Test VERDICT evidence inside an observation (must look like real executed output)
VERDICT = [
    ("pytest_summary", re.compile(r"\b\d+\s+passed(?:,|\s)|={2,}\s*\d+\s+(?:passed|failed)|collected \d+ items", re.I)),
    ("short_test_summary", re.compile(r"^\s*(?:PASSED|FAILED|ERROR)\s+\S+", re.M)),
    ("unittest_summary", re.compile(r"^(?:OK|FAILED)\s*(?:\(|$).*?(?:ran \d+ test|\d+ test)", re.M)),
    ("test_verdict_word", re.compile(r"\b(?:tests?|cases?)\s+(?:passed|failed)|(?:passed|failed|failing)\s+tests?\b", re.I)),
    ("exit_code_nonzero", re.compile(r"(?:exit[_ ]code|returncode|code[=: ])\s*[:=]?\s*[1-9]\d*", re.I)),
    ("traceback", re.compile(r"Traceback \(most recent call last\)|AssertionError|FAIL_TO_PASS")),
]
STATE = [
    ("editor_lines_footer", re.compile(r"\[File:\s*\S+\s*\(\d+\s+lines? total\)\]")),
    ("any_lines_total", re.compile(r"\(\d+\s+lines?\s+total\)|\d+\s+lines?\s+total")),
    ("open_file_view", re.compile(r"\[File:.*lines? (?:total|omitted)\]|Here's the files? and directories")),
    ("diff_git", re.compile(r"^diff --git |^@@ -\d+,\d+ \+\d+,\d+ @@", re.M)),
    ("dir_listing", re.compile(r"Here's the (?:files|directories)[^\n]*", re.I)),
]


def parse_messages(blob: str) -> list[dict]:
    """Best-effort: recover the message list from a dumped probe blob by regex."""
    return []


print(f"{'dataset':<62} {'steps':>6} {'verdict_obs':>11} {'state_obs':>10}  top_verdict_kinds")
print("-" * 150)

summary = {}
for key, rec in data.items():
    if rec.get("error") or not rec.get("excerpt"):
        rid = rec.get("id", key)
        summary[key] = {"error": rec.get("error") or "no excerpt"}
        print(f"{rid:<62} {'-':>6} {'-':>11} {'-':>10}  {rec.get('error') or 'no excerpt'}")
        continue

    blob = (PROBE / f"{rec['id'].replace('/', '__')}__{rec['split'].replace('.', '_')}.txt").read_text(
        encoding="utf-8", errors="replace")

    # Split heuristically into "observation chunks": each occurrence of a tool
    # result / observation marker starts a new chunk.
    chunks = re.split(
        r'(?="role"\s*:\s*"(?:tool|user)"|Observation:|<output>|<result>|\n\s*>{2,}|OBSERVATION)',
        blob,
    )
    chunks = [c for c in chunks if len(c) > 40]
    n_steps = max(1, len(chunks))

    v_hits = {name: 0 for name, _ in VERDICT}
    s_hits = {name: 0 for name, _ in STATE}
    v_obs = s_obs = 0
    for c in chunks:
        vk = [n for n, rx in VERDICT if rx.search(c)]
        sk = [n for n, rx in STATE if rx.search(c)]
        if vk:
            v_obs += 1
            for n in vk:
                v_hits[n] += 1
        if sk:
            s_obs += 1
            for n in sk:
                s_hits[n] += 1

    topv = ", ".join(f"{k}={v}" for k, v in sorted(v_hits.items(), key=lambda x: -x[1]) if v)
    tops = ", ".join(f"{k}={v}" for k, v in sorted(s_hits.items(), key=lambda x: -x[1]) if v)
    summary[key] = {
        "chunks": n_steps, "verdict_chunks": v_obs, "state_chunks": s_obs,
        "verdict_kinds": {k: v for k, v in v_hits.items() if v},
        "state_kinds": {k: v for k, v in s_hits.items() if v},
    }
    print(f"{rec['id']:<62} {n_steps:>6} {v_obs:>11} {s_obs:>10}  {topv}")
    if tops:
        print(f"{'':<62} {'':>6} {'':>11} {'':>10}  STATE: {tops}")

(PROBE / "_perstep_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\nwrote {PROBE / '_perstep_summary.json'}")
