"""One concrete example, printed in full, so the classification can be checked by a human.

    python scripts/show_one_example.py --cls kept
    python scripts/show_one_example.py --cls dead_end

The aggregate rates rest on a mechanical comparison between two sets of line hashes. This prints
everything needed to falsify that comparison on a single case: the chosen edit's raw turn, the
lines recovered from it, the agent's own final patch, and which of the recovered lines appear in
that patch. If the answer looks wrong here, the headline number is wrong.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "results" / "rebuild"
FENCE = re.compile(r"```(?:bash|sh)?\s*\n(.*?)```", re.S)
_ADDED = re.compile(r"^\+(?!\+\+)(.*)$", re.M)


def lh(s: str) -> str:
    return hashlib.blake2b(s.strip().encode("utf-8", "ignore"), digest_size=6).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", default="kept", choices=["kept", "dead_end", "revised"])
    ap.add_argument("--limit", type=int, default=400)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    st = pd.read_parquet(OUT / "alignment_steps.parquet")
    steps = pd.read_parquet(ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet",
                            columns=["run_id", "step", "file_shown", "added_hashes"])
    d = st.merge(steps, on=["run_id", "step"], how="left").sort_values(["run_id", "step"])
    later = {}
    for _rid, g in d.groupby("run_id", sort=False):
        files = g["file_shown"].astype(str).to_numpy()
        idx = g.index.to_numpy()
        for k in range(len(idx) - 1):
            cur = files[k]
            later[idx[k]] = bool(cur) and (files[k + 1:] == cur).any()
    d["revisited_later"] = d.index.map(lambda i: later.get(i, False))
    d["cls"] = "revised"
    d.loc[d["hit"] == 1, "cls"] = "kept"
    d.loc[(d["hit"] == 0) & (~d["revisited_later"]), "cls"] = "dead_end"

    cand = d[d["cls"] == args.cls].head(args.limit)
    import pyarrow.parquet as pq
    for f in sorted((ROOT / "data" / "raw" / "nebius").glob("train-*.parquet")):
        for batch in pq.ParquetFile(f).iter_batches(batch_size=60):
            for row in batch.to_pylist():
                rid_prefix = f"{row['instance_id']}::{row['model_name']}::"
                match = cand[cand.run_id.str.startswith(rid_prefix)]
                if not len(match):
                    continue
                r = match.iloc[0]
                traj = list(row["trajectory"])
                patch = row["generated_patch"] or ""
                # find the ai turn at the step before this edit
                ai_idx = -1
                for i, m in enumerate(traj):
                    if m.get("role") == "ai":
                        ai_idx += 1
                        if ai_idx == int(r["step"]) - 1:
                            break
                action = (traj[ai_idx].get("text") or "") if 0 <= ai_idx < len(traj) else ""
                hashes = [h for h in str(r["added_hashes"]).split() if h]
                patch_hashes = {lh(m.group(1)) for m in _ADDED.finditer(patch)
                                if len(m.group(1).strip()) >= 3}

                print("=" * 100)
                print(f"class: {args.cls}   run: {rid_prefix}...   step {int(r['step'])}   "
                      f"file: {r['file_shown']}")
                print(f"agent solved this instance: {bool(r['reward'])}   "
                      f"edit had {len(hashes)} recovered lines   "
                      f"of which {sum(1 for h in hashes if h in patch_hashes)} appear in the patch")
                print("-" * 100)
                print("RAW ACTION (the ai turn that produced this edit):")
                print(action[:1400])
                print("-" * 100)
                print("FINAL PATCH (as recorded by the harness, first 1200 chars):")
                print(patch[:1200])
                print("-" * 100)
                print("RECOVERED LINE HASHES vs PATCH HASHES")
                for h in hashes[:12]:
                    print(f"   {h}  in patch: {h in patch_hashes}")
                return
    print(f"no example of class {args.cls} found in the first files scanned")


if __name__ == "__main__":
    main()
