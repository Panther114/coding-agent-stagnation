"""Score the hand-filled human sample against the stored judgement and the mechanical label.

    python scripts/score_human_sample.py

Reads ``results/rebuild/human_check_sample.csv`` after a person has filled in the
``human_label`` column (accepts true/false, 1/0, stagnant/productive, yes/no) and reports the
two agreements the paper needs. If the column is empty it says so and exits without inventing
anything.

Writes ``results/rebuild/human_check_scored.json``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"

TRUEISH = {"1", "true", "t", "yes", "y", "stagnant", "stalled", "s"}
FALSEISH = {"0", "false", "f", "no", "n", "productive", "progress", "p"}


def to_bool(v) -> object:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip().lower()
    if s in TRUEISH:
        return 1
    if s in FALSEISH:
        return 0
    return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    path = OUT / "human_check_sample.csv"
    if not path.exists():
        print(f"no sample at {path}; run scripts/make_human_sample.py first")
        return
    df = pd.read_csv(path)
    if "human_label" not in df.columns:
        df["human_label"] = ""
    got = df["human_label"].map(to_bool)
    n = int(got.notna().sum())
    if n == 0:
        print("The human_label column is empty. A person has to fill it in first — this script "
              "will not guess.")
        print(f"  sample: {path}")
        print(f"  rows:   {len(df)}")
        return
    use = df[got.notna()].copy()
    use["human"] = got[got.notna()].astype(int)

    def agree(a: str, b: str) -> float:
        return float((use[a] == use[b]).mean())

    res = {
        "n_scored": int(len(use)),
        "n_sample": int(len(df)),
        "human_vs_stored_judgement": agree("human", "binary"),
        "human_vs_mechanical": agree("human", "mech_stagnant"),
        "stored_vs_mechanical_on_sample": agree("binary", "mech_stagnant"),
        "human_stagnant_rate": float(use["human"].mean()),
        "stored_stagnant_rate": float(use["binary"].mean()),
        "mechanical_stagnant_rate": float(use["mech_stagnant"].mean()),
    }
    # Cohen's kappa against each reference, since raw agreement ignores base rates
    from sklearn.metrics import cohen_kappa_score
    res["kappa_human_vs_stored"] = float(cohen_kappa_score(use["human"], use["binary"]))
    res["kappa_human_vs_mechanical"] = float(cohen_kappa_score(use["human"], use["mech_stagnant"]))
    with open(OUT / "human_check_scored.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(f"scored {res['n_scored']}/{res['n_sample']} rows")
    print(f"  human vs stored judgement : {res['human_vs_stored_judgement']:.1%} "
          f"(kappa {res['kappa_human_vs_stored']:+.3f})")
    print(f"  human vs mechanical label : {res['human_vs_mechanical']:.1%} "
          f"(kappa {res['kappa_human_vs_mechanical']:+.3f})")
    print(f"  stored vs mechanical      : {res['stored_vs_mechanical_on_sample']:.1%}")
    print(f"wrote {OUT / 'human_check_scored.json'}")


if __name__ == "__main__":
    main()
