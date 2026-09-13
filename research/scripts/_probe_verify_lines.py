"""Throwaway probe #2: census of test-summary line shapes and failure-id shapes."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

import pyarrow.parquet as pq

RAW = r"D:\Gavania\Academic\Competitions\Agent_Correction\research\data\raw\nebius"

# candidate terminal-summary lines
SUMS = [
    ("pytest_equals", re.compile(r"^=+ .*=+$", re.M)),
    ("unittest_ok", re.compile(r"^OK( \(.*\))?$", re.M)),
    ("unittest_failed", re.compile(r"^FAILED \(.*\)$", re.M)),
    ("ran_n", re.compile(r"^Ran \d+ tests? in .*$", re.M)),
    ("go_test", re.compile(r"^(ok|FAIL|---)\s+\S+.*$", re.M)),
    ("npm", re.compile(r"^(Tests:|Test Suites:|Suites:|Passed:|Failed:).*$", re.M)),
    ("cargo", re.compile(r"^test result: .*$", re.M)),
    ("jest", re.compile(r"^\s*Tests:\s+.*$", re.M)),
]
FAILID = re.compile(r"^(FAILED|FAIL|ERROR)\b.*$", re.M)


def ai_blocks(text: str):
    return [b.strip() for b in re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text or "", re.S)]


def main() -> int:
    n_files = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    max_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    cnt = {k: Counter() for k, _ in SUMS}
    failid = Counter()
    n_obs = 0
    n_runs = 0
    n_with_summary = 0
    examples = {}
    for fi in range(n_files):
        pf = pq.ParquetFile(f"{RAW}/train-{fi:05d}-of-00012.parquet")
        stop = False
        for batch in pf.iter_batches(batch_size=8, columns=["instance_id", "trajectory"]):
            for rec in batch.to_pylist():
                n_runs += 1
                pending = None
                got = False
                for m in rec["trajectory"]:
                    role = m.get("role")
                    text = m.get("text") or ""
                    if role == "ai":
                        pending = ai_blocks(text)
                    elif role == "user" and pending is not None:
                        n_obs += 1
                        obs = text
                        for k, p in SUMS:
                            for mt in p.findall(obs):
                                line = mt if isinstance(mt, str) else str(mt)
                                pass
                            for line in p.finditer(obs):
                                s = line.group(0).strip()
                                cnt[k][s[:170]] += 1
                                got = True
                                examples.setdefault(k, []).append((rec["instance_id"], s[:200]))
                        for mt in FAILID.finditer(obs):
                            failid[mt.group(0)[:150]] += 1
                        pending = None
                if got:
                    n_with_summary += 1
                if n_runs >= max_runs:
                    stop = True
                    break
            if stop:
                break
        if stop:
            break
    print(f"runs={n_runs} obs={n_obs} runs_with_any_summary={n_with_summary}")
    for k, _ in SUMS:
        print(f"\n########## {k}  (distinct={len(cnt[k])}, total={sum(cnt[k].values())})")
        for s, n in cnt[k].most_common(25):
            print(f"  {n:7d}  {s}")
    print(f"\n########## FAILED/FAIL/ERROR lines (distinct={len(failid)})")
    for s, n in failid.most_common(40):
        print(f"  {n:7d}  {s}")
    with open("docs/_probe_examples.json", "w", encoding="utf-8") as fh:
        json.dump({k: v[:25] for k, v in examples.items()}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
