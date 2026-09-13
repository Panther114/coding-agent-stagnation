"""Throwaway probe: find real observation strings that carry test output.

Streams the raw nebius corpus and dumps candidate observation substrings so the
parser can be written against actual text rather than imagination.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as pq

RAW = r"D:\Gavania\Academic\Competitions\Agent_Correction\research\data\raw\nebius"

# broad "might be test output" net
HINT = re.compile(
    r"(passed|failed|error|error\)|ok\b|PASSED|FAILED|OK\b|collected \d+|"
    r"no tests ran|ERROR:|FAIL:|test session starts|Ran \d+ test|"
    r"===+ .* in \d+\.\d+s|exit code)",
    re.I,
)


def ai_blocks(text: str):
    return [b.strip() for b in re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text or "", re.S)]


def main() -> int:
    n_files = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    max_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    hits = []
    n_obs = 0
    n_runs = 0
    for fi in range(n_files):
        pf = pq.ParquetFile(f"{RAW}/train-{fi:05d}-of-00012.parquet")
        for batch in pf.iter_batches(batch_size=8, columns=["instance_id", "model_name", "trajectory"]):
            for rec in batch.to_pylist():
                n_runs += 1
                msgs = rec["trajectory"]
                pending = None
                for m in msgs:
                    role = m.get("role")
                    text = m.get("text") or ""
                    if role == "ai":
                        pending = ai_blocks(text)
                    elif role == "user" and pending is not None:
                        n_obs += 1
                        if HINT.search(text):
                            hits.append((rec["instance_id"], "\n".join(pending)[:200], text))
                        pending = None
                if n_runs >= max_runs:
                    break
            if n_runs >= max_runs:
                break
        if n_runs >= max_runs:
            break
    print(f"runs={n_runs} obs={n_obs} hits={len(hits)} ({len(hits)/max(n_obs,1):.3%})")
    with open("docs/_verify_probe_hits.jsonl", "w", encoding="utf-8") as fh:
        for iid, cmd, obs in hits:
            fh.write(json.dumps({"instance_id": iid, "cmd": cmd, "obs": obs}) + "\n")
    # quick shape census
    pats = {
        "pytest_count_summary": re.compile(r"\b(\d+)\s+(passed|failed|error|errors|skipped)\b"),
        "pytest_equals_line": re.compile(r"^=+ .*\b(passed|failed|error|no tests ran)\b.* =+$", re.M),
        "collected": re.compile(r"collected (\d+) items?"),
        "unittest_OK": re.compile(r"^OK(?: \((.*?)\))?$", re.M),
        "unittest_FAILED": re.compile(r"^FAILED \((.*?)\)$", re.M),
        "FAILED_nodeid": re.compile(r"^FAILED\s+(\S+)", re.M),
        "short_summary": re.compile(r"^=+ short test summary info =+$", re.M),
        "ran_n_tests": re.compile(r"^Ran (\d+) tests? in ", re.M),
        "no_tests_ran": re.compile(r"no tests ran", re.I),
    }
    c = Counter()
    for _iid, _cmd, obs in hits:
        for k, p in pats.items():
            if p.search(obs):
                c[k] += 1
    for k in pats:
        print(f"  {k:24s} {c[k]:6d} / {len(hits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
