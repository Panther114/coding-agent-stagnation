"""Final: R2E-Gym-SFT schema + Nemotron-Terminal-Corpus per-step test outcomes."""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

import fsspec
import pyarrow.parquet as pq

BASE = "https://hf-mirror.com"
RECON = Path(__file__).resolve().parents[1] / "_cache" / "recon"

VERDICT = {
    "pytest_summary": re.compile(r"\b\d+\s+(?:passed|failed|error)\b|=\s*\d+ (?:passed|failed)", re.I),
    "testid_verdict": re.compile(r"^\s*(?:PASSED|FAILED|ERROR)\b", re.M),
    "assertion": re.compile(r"AssertionError|^E\s{1,4}\w*Error", re.M),
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "exit_nonzero": re.compile(r"exit[_ ]?code[\"'\s:=]+[1-9]\d*|returncode[\"'\s:=]+[1-9]\d*", re.I),
}
STATE = {
    "lines_total": re.compile(r"\(\d+\s+lines?\s+total\)"),
    "open_file": re.compile(r"\[File:"),
    "dir_listing": re.compile(r"Here's the files? and directories", re.I),
}


def openq(repo, rel, tries=4):
    url = f"{BASE}/datasets/{repo}/resolve/main/{rel}"
    for i in range(tries):
        try:
            return pq.ParquetFile(fsspec.open(url, "rb", timeout=120).open())
        except Exception as e:  # noqa: BLE001
            print(f"    open {type(e).__name__}")
            time.sleep(4 * (i + 1))
    return None


def scan(repo, rel, col="conversations", n=60):
    pf = openq(repo, rel)
    if pf is None:
        return None
    per = {"repo": repo, "path": rel, "rows_shard": pf.metadata.num_rows,
           "cols": pf.schema_arrow.names, "read": 0, "obs": 0, "obsV": 0,
           "rowsV": 0, "kinds": Counter(), "state": Counter()}
    for b in pf.iter_batches(batch_size=30, columns=[col] if col in pf.schema_arrow.names else None):
        for row in b.to_pylist():
            if per["read"] >= n:
                break
            per["read"] += 1
            ml = row.get(col if col in pf.schema_arrow.names else "messages")
            if isinstance(ml, str):
                try:
                    ml = json.loads(ml)
                except Exception:  # noqa: BLE001
                    continue
            if isinstance(ml, dict):
                ml = ml.get("messages") or ml.get("conversations")
            if not isinstance(ml, list):
                continue
            hit = False
            for m in ml:
                if not isinstance(m, dict):
                    continue
                role = str(m.get("role") or "").lower()
                if role in ("assistant", "agent", "ai"):
                    continue
                c = m.get("content")
                c = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                per["obs"] += 1
                for k, rx in VERDICT.items():
                    if rx.search(c):
                        per["kinds"][k] += 1
                        hit = True
                for k, rx in STATE.items():
                    if rx.search(c):
                        per["state"][k] += 1
            if hit:
                per["rowsV"] += 1
        if per["read"] >= n:
            break
    per["kinds"] = dict(per["kinds"])
    per["state"] = dict(per["state"])
    per["rate_rowsV"] = round(per["rowsV"] / per["read"], 3) if per["read"] else None
    return per


JOBS = [
    ("R2E-Gym/R2EGym-SFT-Trajectories", "data/train-00000-of-00001.parquet", "messages"),
    ("nvidia/Nemotron-Terminal-Corpus", "dataset_adapters/swe.parquet", "conversations"),
    ("nvidia/Nemotron-Terminal-Corpus", "dataset_adapters/code.parquet", "conversations"),
    ("nvidia/Nemotron-Terminal-Corpus",
     "synthetic_tasks/skill_based/medium/software_engineering/data_filtered.parquet", "conversations"),
    ("nvidia/Nemotron-Terminal-Corpus",
     "synthetic_tasks/skill_based/medium/debugging/data_filtered.parquet", "conversations"),
    ("mlfoundations-dev/terminal-bench-traces-local", "data/train-00000-of-00001.parquet", "conversations"),
    ("hanspeterlyngsoeraaschoujensen/terminal-bench-pro-eval-trajectories",
     "data/train-00000-of-00001.parquet", "messages"),
]
out = {}
for repo, rel, col in JOBS:
    print(f"== {repo} :: {rel}", flush=True)
    try:
        r = scan(repo, rel, col)
    except Exception as e:  # noqa: BLE001
        r = {"repo": repo, "path": rel, "error": f"{type(e).__name__}: {e}"}
    out[f"{repo}::{rel}"] = r
    if r is None or r.get("error"):
        print("   !! failed")
        continue
    print(f"   shard_rows={r['rows_shard']} read={r['read']} obs={r['obs']} rowsV={r['rowsV']} "
          f"({r['rate_rowsV']}) cols={r['cols']}")
    print(f"   verdicts={r['kinds']}  state={r['state']}")
(RECON / "_nemotron_r2e.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwrote _nemotron_r2e.json")
