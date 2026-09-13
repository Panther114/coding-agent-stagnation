"""Throwaway: how do 80,036 raw rows map to distinct run_ids?"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(r"D:\Gavania\Academic\Competitions\Agent_Correction\research")
sys.path.insert(0, str(ROOT / "scripts"))
import extract_step_verification as EX  # noqa: E402


def main() -> None:
    runs = pd.read_parquet(ROOT / "data/processed/steps/nebius/runs.parquet")
    print("published runs:", len(runs), "distinct run_id:", runs["run_id"].nunique())
    print("duplicate run_id rows:", len(runs) - runs["run_id"].nunique())

    ids = Counter()
    keys = Counter()
    n = 0
    for p in sorted(ROOT.glob("data/raw/nebius/train-*.parquet")):
        pf = pq.ParquetFile(p)
        for b in pf.iter_batches(batch_size=16, columns=["instance_id", "model_name", "trajectory"]):
            for row in b.to_pylist():
                if not row["trajectory"]:
                    continue
                n += 1
                ids[row["instance_id"] + "::" + row["model_name"]] += 1
                keys["{}::{}::{}".format(row["instance_id"], row["model_name"],
                                         EX.traj_key(row["trajectory"]))] += 1
    print("raw rows:", n)
    print("distinct (instance,model):", len(ids))
    print("distinct run_id:", len(keys))
    print("max copies of one (instance,model):", max(ids.values()))
    print("max copies of one run_id:", max(keys.values()))
    print("top (instance,model) multiplicities:", ids.most_common(5))
    print("published run_id set == raw run_id set:",
          set(runs["run_id"]) == set(keys))


if __name__ == "__main__":
    main()
