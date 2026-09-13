"""Throwaway probe #4: node-id shapes for FAILED/FAIL/ERROR lines."""
from __future__ import annotations

import re
import sys
from collections import Counter

import pyarrow.parquet as pq

RAW = r"D:\Gavania\Academic\Competitions\Agent_Correction\research\data\raw\nebius"

FAILED = re.compile(r"^FAILED\s+(\S+)", re.M)
FAIL_U = re.compile(r"^FAIL:\s+(\S+)", re.M)
ERR_U = re.compile(r"^ERROR:\s+(\S+)", re.M)
ERR_P = re.compile(r"^ERROR\s+(\S+)", re.M)


def ai_blocks(text: str):
    return [b.strip() for b in re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text or "", re.S)]


def shape(s: str) -> str:
    s = re.sub(r"\[\d+\]", "[N]", s)
    s = re.sub(r"\[[A-Za-z0-9_\-.,'\" ]+\]", "[A]", s)
    return s


def main() -> int:
    n_files = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    max_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    c = Counter()
    raw_samples = Counter()
    n = 0
    for fi in range(n_files):
        pf = pq.ParquetFile(f"{RAW}/train-{fi:05d}-of-00012.parquet")
        stop = False
        for batch in pf.iter_batches(batch_size=8, columns=["trajectory"]):
            for rec in batch.to_pylist():
                n += 1
                pending = None
                for m in rec["trajectory"]:
                    role, text = m.get("role"), (m.get("text") or "")
                    if role == "ai":
                        pending = ai_blocks(text)
                    elif role == "user" and pending is not None:
                        for p, tag in ((FAILED, "FAILED"), (FAIL_U, "FAIL:"), (ERR_U, "ERROR:"), (ERR_P, "ERROR ")):
                            for mt in p.finditer(text):
                                nid = mt.group(1)
                                c[f"{tag} {shape(nid)}"] += 1
                                raw_samples[nid[:110]] += 1
                        pending = None
                if n >= max_runs:
                    stop = True
                    break
            if stop:
                break
        if stop:
            break
    print(f"runs={n}")
    print("--- SHAPES ---")
    for s, k in c.most_common(45):
        print(f"  {k:6d}  {s}")
    print("\n--- most common raw ids ---")
    for s, k in raw_samples.most_common(30):
        print(f"  {k:6d}  {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
