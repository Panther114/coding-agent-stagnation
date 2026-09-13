"""Throwaway probe #6: observation truncation shape - lengths, tails, recoverability."""
from __future__ import annotations

import re
import sys
from collections import Counter

import pyarrow.parquet as pq

RAW = r"D:\Gavania\Academic\Competitions\Agent_Correction\research\data\raw\nebius"

FOOTER = re.compile(r"\n?\(Open file: [^\)]*\)\n\(Current directory: [^\)]*\)\n?bash-\$\s*$")


def ai_blocks(text: str):
    return [b.strip() for b in re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text or "", re.S)]


def main() -> int:
    n_files = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    max_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    lens = Counter()
    tails = Counter()
    testish = 0
    n_obs = 0
    for fi in range(n_files):
        pf = pq.ParquetFile(f"{RAW}/train-{fi:05d}-of-00012.parquet")
        stop = False
        n_runs = 0
        for batch in pf.iter_batches(batch_size=8, columns=["trajectory"]):
            for rec in batch.to_pylist():
                n_runs += 1
                pending = None
                for m in rec["trajectory"]:
                    role, text = m.get("role"), (m.get("text") or "")
                    if role == "ai":
                        pending = ai_blocks(text)
                    elif role == "user" and pending is not None:
                        n_obs += 1
                        if re.search(r"(pytest|unittest|test session starts|Ran \d+ tests)", text, re.I):
                            testish += 1
                            lens[len(text)] += 1
                            stripped = FOOTER.sub("", text)
                            tails[stripped[-60:].replace("\n", "\\n")] += 1
                        pending = None
                if n_runs >= max_runs:
                    stop = True
                    break
            if stop:
                break
        if stop:
            break
    print(f"obs={n_obs} testish={testish}")
    print("--- length histogram (top 20, exact) ---")
    for L, n in lens.most_common(20):
        print(f"  {n:6d}  len={L}")
    print("--- common tails (top 20) ---")
    for t, n in tails.most_common(20):
        print(f"  {n:6d}  ...{t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
