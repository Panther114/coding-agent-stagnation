"""Throwaway probe #5: capture verbatim messy observation blocks for the evidence doc."""
from __future__ import annotations

import json
import re
import sys

import pyarrow.parquet as pq

RAW = r"D:\Gavania\Academic\Competitions\Agent_Correction\research\data\raw\nebius"

WANT = {
    "pytest_fail_pass": re.compile(r"=+ \d+ failed, \d+ passed in \d"),
    "pytest_param": re.compile(r"FAILED \S+\[[^\]]+\]"),
    "unittest_fail": re.compile(r"^FAILED \((failures?|errors?)=", re.M),
    "unittest_ok_skip": re.compile(r"^OK \(skipped=", re.M),
    "collection_error": re.compile(r"Interrupted: \d+ error", re.I),
    "no_tests_ran": re.compile(r"no tests ran", re.I),
    "warnings_mixed": re.compile(r"=+ warnings summary =+"),
    "timeout": re.compile(r"timed out|Timeout|Killed|took too long", re.I),
    "truncated_summary": re.compile(r"^FAILED \S+ - \w+:\s*\w*\.\.\.$", re.M),
    "collected_error_n": re.compile(r"collected \d+ items? / \d+ error"),
    "pytest_all_pass": re.compile(r"=+ \d+ passed[^\n=]* =+"),
    "deprecation_noise": re.compile(r"DeprecationWarning[\s\S]{0,400}\b\d+ passed\b"),
    "error_line_pytest": re.compile(r"^ERROR\s+\S+\.py::", re.M),
    "empty_obs_cmd": re.compile(r"^(?:\s*)$"),
}


def ai_blocks(text: str):
    return [b.strip() for b in re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text or "", re.S)]


def main() -> int:
    n_files = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    out = {}
    for fi in range(n_files):
        pf = pq.ParquetFile(f"{RAW}/train-{fi:05d}-of-00012.parquet")
        for batch in pf.iter_batches(batch_size=8, columns=["instance_id", "trajectory"]):
            for rec in batch.to_pylist():
                pending = None
                for m in rec["trajectory"]:
                    role, text = m.get("role"), (m.get("text") or "")
                    if role == "ai":
                        pending = ai_blocks(text)
                    elif role == "user" and pending is not None:
                        for k, p in WANT.items():
                            if len(out.get(k, [])) < 4 and p.search(text):
                                out.setdefault(k, []).append(
                                    {"instance_id": rec["instance_id"],
                                     "cmd": "\n".join(pending)[:300], "obs": text[:3000]})
                        pending = None
            if all(len(v) >= 2 for v in out.values()) and len(out) == len(WANT):
                break
    print({k: len(v) for k, v in out.items()})
    with open("docs/_verbatim_samples.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    missing = [k for k in WANT if k not in out]
    print("MISSING:", missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
