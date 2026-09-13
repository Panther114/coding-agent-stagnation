"""Zero-rebuild verification of the mechanism: is the recovered line the line that shipped?

    python scripts/verify_extraction.py --n 500

The waste rate rests on one comparison: the lines recovered from an edit action are checked
against the added lines of the agent's own final patch. This script re-derives both sides
*independently of the pipeline* — it re-parses trajectories straight from the raw parquet with
`agentstall.corpus` and compares the recovered text against the patch text — and prints the cases
where a recovered line does or does not appear, as text. If the extractor is grabbing the wrong
lines, it shows up here as recovered text that no reasonable patch would contain.

For each sampled edit it reports:
  * the recovered lines, verbatim;
  * whether each appears in the final patch (exact text match on the stripped line);
  * the file and whether the patch touches that file.

Writes ``results/rebuild/extraction_verification.json`` and prints a few cases.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall.corpus import build_nebius_steps  # noqa: E402

OUT = ROOT / "results" / "rebuild"
_ADDED = re.compile(r"^\+(?!\+\+)(.*)$", re.M)
_DIFF_FILE = re.compile(r"^diff --git a/(\S+)", re.M)


def patch_line_texts(patch: str) -> set:
    return {m.group(1).strip() for m in _ADDED.finditer(patch) if len(m.group(1).strip()) >= 3}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400, help="runs to scan")
    ap.add_argument("--show", type=int, default=4)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    files = sorted((ROOT / "data" / "raw" / "nebius").glob("train-*.parquet"))
    rows: List[Dict[str, object]] = []
    shown = 0
    scanned = 0
    for f in files:
        for batch in pq.ParquetFile(f).iter_batches(batch_size=40):
            for row in batch.to_pylist():
                traj = row["trajectory"]
                if traj is None:
                    continue
                scanned += 1
                patch = row["generated_patch"] or ""
                texts = patch_line_texts(patch)
                files_touched = {Path(x).name for x in _DIFF_FILE.findall(patch)}
                steps = build_nebius_steps(traj)
                for s in steps:
                    if not s.is_edit:
                        continue
                    lines = s.meta.get("added_lines") or []
                    if not lines:
                        continue
                    fname = Path(s.meta.get("file_shown") or "").name
                    hits = sum(1 for ln in lines if ln.strip() in texts)
                    rows.append({
                        "instance": row["instance_id"], "solved": bool(row["target"]),
                        "step": s.index, "file": s.meta.get("file_shown") or "",
                        "file_in_patch": bool(fname) and fname in files_touched,
                        "n_recovered": len(lines), "n_matching_patch": hits,
                        "hit": bool(hits),
                        "sample_lines": lines[:3], "sample_match": [ln.strip() in texts
                                                                    for ln in lines[:3]],
                    })
                    if shown < args.show and hits:
                        shown += 1
                        print("=" * 96)
                        print(f"{row['instance_id']} step {s.index} file={fname} "
                              f"(patch touches that file: {bool(fname) and fname in files_touched})")
                        print(f"  recovered {len(lines)} line(s), {hits} appear verbatim in the patch")
                        for ln, m in list(zip(lines, [l.strip() in texts for l in lines]))[:4]:
                            print(f"    [{'MATCH' if m else '  -  '}] {ln[:110]!r}")
                if scanned >= args.n:
                    break
            if scanned >= args.n:
                break
        if scanned >= args.n:
            break

    if not rows:
        print("no edit actions recovered; nothing to verify")
        return
    import pandas as pd
    df = pd.DataFrame(rows)
    res = {
        "n_runs_scanned": scanned, "n_edit_steps_with_lines": int(len(df)),
        "hit_rate_on_these_steps": float(df["hit"].mean()),
        "mean_lines_recovered": float(df["n_recovered"].mean()),
        "mean_matching": float(df["n_matching_patch"].mean()),
        "share_of_steps_where_file_is_in_patch": float(df["file_in_patch"].mean()),
        "hit_rate_when_file_in_patch": float(df.loc[df.file_in_patch, "hit"].mean()),
        "hit_rate_when_file_not_in_patch": float(df.loc[~df.file_in_patch, "hit"].mean()),
        "note": ("re-derived independently of the pipeline: trajectories are re-parsed from the raw "
                 "parquet and the patch is read directly, so a systematic extractor error would "
                 "show as recovered text that never matches"),
    }
    print(f"\nscanned {scanned} runs; {len(df)} edit steps with recovered lines")
    print(f"  a recovered line appears in the patch on {res['hit_rate_on_these_steps']:.3f} of them")
    print(f"  mean {res['mean_lines_recovered']:.2f} lines recovered, "
          f"{res['mean_matching']:.2f} matching")
    print(f"  when the patch touches the edited file:  hit rate "
          f"{res['hit_rate_when_file_in_patch']:.3f} ({int(df.file_in_patch.sum())} steps)")
    print(f"  when the patch never touches that file:  hit rate "
          f"{res['hit_rate_when_file_not_in_patch']:.3f} ({int((~df.file_in_patch).sum())} steps)")
    with open(OUT / "extraction_verification.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'extraction_verification.json'}")


if __name__ == "__main__":
    main()
