"""Throwaway probe #3: wider census + context indicators + truncated test lines."""
from __future__ import annotations

import re
import sys
from collections import Counter

import pyarrow.parquet as pq

RAW = r"D:\Gavania\Academic\Competitions\Agent_Correction\research\data\raw\nebius"

IND = {
    "pytest_session": re.compile(r"=+ test session starts =+"),
    "pytest_short": re.compile(r"=+ short test summary info =+"),
    "pytest_final": re.compile(r"^=+ [^\n=]*(passed|failed|error|no tests ran|skipped|deselected)[^\n=]* in \d+[\d.]*s[^\n=]* =+$", re.M),
    "pytest_final_nonl": re.compile(r"[^\n]*\b\d+ (passed|failed|error)\b[^\n]* in \d+[\d.]*s", re.I),
    "collected_n": re.compile(r"collected \d+ items?", re.I),
    "collected_err": re.compile(r"collected \d+ items? / \d+ errors?"),
    "errors_header": re.compile(r"=+ ERRORS =+"),
    "interrupted_collect": re.compile(r"Interrupted: \d+ error(s)? during collection"),
    "no_tests_ran": re.compile(r"no tests ran", re.I),
    "unittest_ran": re.compile(r"^Ran \d+ tests? in ", re.M),
    "unittest_ok": re.compile(r"^OK( \(.*\))?$", re.M),
    "unittest_failed": re.compile(r"^FAILED \(.*\)$", re.M),
    "truncated_F": re.compile(r"^FAILED \S+ - .*\.\.\.$", re.M),
    "django_ran": re.compile(r"^Ran \d+ tests? in \d", re.M),
    "nose2_failedtest": re.compile(r"unittest\.loader\._FailedTest"),
    "node_test": re.compile(r"^# (pass|fail) \d+", re.M),
    "go_ok": re.compile(r"^ok\s+\S+\s+[\d.]+s$", re.M),
    "cargo_test_result": re.compile(r"^test result: ", re.M),
    "jest_tests": re.compile(r"^\s*Tests:\s+", re.M),
    "maven_tests": re.compile(r"Tests run: \d+, Failures: \d+", re.I),
    "gradle": re.compile(r"^\d+ tests? completed", re.M),
    "syntax_error": re.compile(r"SyntaxError"),
    "timeout_kill": re.compile(r"(timed out|Timeout|TIMEOUT|Killed|killed|took too long)"),
    "make_error1": re.compile(r"^make(\[\d+\])?: \*\*\*", re.M),
    "traceback": re.compile(r"^Traceback \(most recent call last\)", re.M),
    "collect_error_only": re.compile(r"^ERROR collecting ", re.M),
    "pytest_error_summary": re.compile(r"^ERROR \S+", re.M),
    "cov_tests": re.compile(r"^TOTAL\s+\d+", re.M),
    "tox_outcome": re.compile(r"^\s*(PASSED|FAILED|ERROR|SKIPPED)\s+\S+:\S+", re.M),
}

TRUNC = re.compile(r"^FAILED\s+(\S+)\s+-\s+.*?\.\.\.\s*$", re.M)
IDX = re.compile(r"^(\S+::\S.*?)\s+-\s+(\w+Error|\w*Exception|AssertionError|Failed)", re.M)


def ai_blocks(text: str):
    return [b.strip() for b in re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text or "", re.S)]


def main() -> int:
    n_files = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    max_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    c = Counter()
    n_obs = 0
    n_runs = 0
    runs_any = 0
    trunc_samples = Counter()
    for fi in range(n_files):
        pf = pq.ParquetFile(f"{RAW}/train-{fi:05d}-of-00012.parquet")
        stop = False
        for batch in pf.iter_batches(batch_size=8, columns=["trajectory"]):
            for rec in batch.to_pylist():
                n_runs += 1
                pending = None
                any_hit = False
                for m in rec["trajectory"]:
                    role = m.get("role")
                    text = m.get("text") or ""
                    if role == "ai":
                        pending = ai_blocks(text)
                    elif role == "user" and pending is not None:
                        n_obs += 1
                        for k, p in IND.items():
                            if p.search(text):
                                c[k] += 1
                                any_hit = True
                        for mt in TRUNC.finditer(text):
                            trunc_samples[mt.group(1)[:100]] += 1
                        for mt in IDX.finditer(text):
                            trunc_samples["|" + mt.group(0)[:110]] += 1
                        pending = None
                if any_hit:
                    runs_any += 1
                if n_runs >= max_runs:
                    stop = True
                    break
            if stop:
                break
        if stop:
            break
    print(f"runs={n_runs} obs={n_obs} runs_with_any_indicator={runs_any} ({runs_any/max(n_runs,1):.2%})")
    print(f"{'indicator':24s} {'obs_hits':>9s}  {'obs_frac':>8s}")
    for k in IND:
        print(f"  {k:22s} {c[k]:9d}  {c[k]/max(n_obs,1):8.4%}")
    print("\n--- notable truncated ids ---")
    for s, n in trunc_samples.most_common(30):
        print(f"  {n:6d}  {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
