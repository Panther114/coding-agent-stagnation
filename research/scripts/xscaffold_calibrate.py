"""Instrument check: does the *new* taxonomy code reproduce the frozen SWE-agent numbers?

The cross-scaffold port re-implements three things that the frozen study already does:
the added-line hashing, the final-patch parsing, and the kept/revised/dead_end split.
If the re-implementation is faithful, running it end-to-end on the SWE-agent corpus must
reproduce ``results/rebuild/dead_end.json`` exactly:

    kept 0.15734086568390385 / revised 0.6515751449370493 / dead_end 0.19108398937904691
    over 236,137 edits in 25,681 runs

This script does exactly that and nothing else.  It reads only; it writes only
``results/rebuild/xscaffold_calibration.json``.

    python scripts/xscaffold_calibrate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from xscaffold_analyse import taxonomy  # noqa: E402

RES = ROOT / "results" / "rebuild"
STEPS = ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet"
RAW = ROOT / "data" / "raw" / "nebius"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    import re

    import pyarrow.parquet as pq

    from xscaffold_extract import patch_hashes

    # ---- same patch recovery as scripts/analyse_alignment.py ---------------------------
    patch_by_instance: Dict[str, List[Tuple[str, str, bool]]] = {}
    n_raw = 0
    for f in sorted(RAW.glob("train-*.parquet")):
        for batch in pq.ParquetFile(f).iter_batches(
                batch_size=100, columns=["instance_id", "model_name", "generated_patch", "target"]):
            d = batch.to_pydict()
            for iid, mdl, patch, tgt in zip(d["instance_id"], d["model_name"],
                                            d["generated_patch"], d["target"]):
                patch_by_instance.setdefault(str(iid), []).append(
                    (str(mdl), patch or "", bool(tgt)))
                n_raw += 1
    print(f"raw runs with a patch: {n_raw:,}")

    # ---- the frozen step table ---------------------------------------------------------
    st = pd.read_parquet(STEPS, columns=["run_id", "task", "model", "reward", "step",
                                         "is_edit", "added_hashes", "file_shown"])
    st = st[st.is_edit == 1].copy()
    print(f"frozen edit steps: {len(st):,} over {st.run_id.nunique():,} runs")

    ph, pf = [], []
    for r in st.itertuples(index=False):
        cands = patch_by_instance.get(str(r.task), [])
        text = ""
        for m, p, res in cands:
            if m == str(r.model) and res == bool(r.reward):
                text = p
                break
        h, files = ([], []) if not text else patch_hashes(text)
        ph.append(" ".join(sorted(set(h))))
        pf.append(" ".join(sorted({Path(x).name for x in files})))
    st["patch_hashes"] = ph
    st["patch_files"] = pf
    st["file"] = st["file_shown"].fillna("").astype(str)
    st["patch_chars"] = st["patch_hashes"].str.len()
    st["resolved"] = st["reward"].astype(float)
    n_missing = int((st.patch_hashes == "").sum())
    print(f"edit steps whose run's patch is EMPTY or unrecovered: {n_missing:,}")

    ref = json.loads((RES / "dead_end.json").read_text(encoding="utf-8"))
    tx_all = taxonomy(st)
    tx_ne = taxonomy(st[st.patch_chars > 0])
    n_empty_runs = int(st.loc[st.patch_chars == 0, "run_id"].nunique())
    n_all_runs = int(st.run_id.nunique())

    out = {
        "purpose": ("re-run the kept/revised/dead_end labelling with the cross-scaffold code "
                    "path on the SWE-agent corpus, to prove the port is faithful and to fix "
                    "the reference against which the other scaffolds are compared"),
        "n_edit_steps_recomputed": tx_all["n_edits"],
        "n_runs_recomputed": tx_all["n_runs"],
        "n_edit_steps_with_empty_patch": n_missing,
        "frac_edit_steps_with_empty_patch": n_missing / max(len(st), 1),
        "n_runs_with_only_empty_patches": n_empty_runs,
        "n_runs_total": n_all_runs,
        "frozen_headline": {"kept_rate": ref["kept_rate"], "revised_rate": ref["revised_rate"],
                            "dead_end_rate": ref["dead_end_rate"], "n_edits": ref["n_edits"],
                            "scope": "every edit step of every run, including runs that "
                                     "produced no patch at all (13.99% of the edits)"},
        "reference_all_runs": {"kept_rate": tx_all["kept_rate"],
                               "revised_rate": tx_all["revised_rate"],
                               "dead_end_rate": tx_all["dead_end_rate"],
                               "n_edits": tx_all["n_edits"], "n_runs": tx_all["n_runs"]},
        "reference_nonempty_patch_runs_only": {
            "kept_rate": tx_ne["kept_rate"], "revised_rate": tx_ne["revised_rate"],
            "dead_end_rate": tx_ne["dead_end_rate"],
            "n_edits": tx_ne["n_edits"], "n_runs": tx_ne["n_runs"],
            "scope": "strictly comparable with scaffolds whose final patch has to be "
                     "recovered from the transcript, where a run with no patch cannot be "
                     "distinguished from a run with an empty patch"},
        "abs_diff_vs_frozen": {
            "kept_rate": abs(tx_all["kept_rate"] - ref["kept_rate"]),
            "revised_rate": abs(tx_all["revised_rate"] - ref["revised_rate"]),
            "dead_end_rate": abs(tx_all["dead_end_rate"] - ref["dead_end_rate"]),
        },
    }
    out["reproduces_frozen"] = bool(
        out["abs_diff_vs_frozen"]["kept_rate"] < 5e-3
        and out["abs_diff_vs_frozen"]["revised_rate"] < 5e-3
        and out["abs_diff_vs_frozen"]["dead_end_rate"] < 5e-3)
    (RES / "xscaffold_calibration.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"\nwrote {RES / 'xscaffold_calibration.json'}")


if __name__ == "__main__":
    main()
