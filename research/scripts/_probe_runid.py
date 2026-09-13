"""Throwaway: verify run_id reproduction against the published runs table."""
from __future__ import annotations

import hashlib
import json

import pandas as pd
import pyarrow.parquet as pq

RAW = r"D:\Gavania\Academic\Competitions\Agent_Correction\research\data\raw\nebius"
RUNS = r"D:\Gavania\Academic\Competitions\Agent_Correction\research\data\processed\steps\nebius\runs.parquet"


def traj_key(traj) -> str:
    try:
        blob = json.dumps(traj, default=str, sort_keys=True)
    except Exception:
        blob = str(traj)
    return hashlib.blake2b(blob.encode("utf-8", "ignore"), digest_size=6).hexdigest()


def main() -> None:
    runs = pd.read_parquet(RUNS)
    want = set(runs["run_id"].tolist())
    pf = pq.ParquetFile(f"{RAW}/train-00000-of-00012.parquet")
    tot = hit = 0
    miss = []
    for batch in pf.iter_batches(batch_size=8, columns=["instance_id", "model_name", "trajectory"]):
        for row in batch.to_pylist():
            traj = row["trajectory"]
            if traj is None:
                continue
            rid = "{}::{}::{}".format(row["instance_id"], row["model_name"], traj_key(traj))
            tot += 1
            if rid in want:
                hit += 1
            elif len(miss) < 5:
                miss.append((rid, row["instance_id"]))
        if tot >= 3000:
            break
    print(f"constructed={tot} matched={hit} rate={hit/max(tot,1):.4%}")
    for m in miss:
        print("  MISS", m)


if __name__ == "__main__":
    main()
