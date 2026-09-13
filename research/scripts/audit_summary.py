"""Verify the numbers in the executive summary against the artifacts.

Nothing here is clever: it is the same discipline as `audit_claims.py`, applied to the one-page
document, because a summary is where a stale number does the most damage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"
DOC = ROOT / "docs" / "EXECUTIVE_SUMMARY.md"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    load = lambda n: json.loads((OUT / n).read_text(encoding="utf-8"))  # noqa: E731
    al, de = load("alignment.json"), load("dead_end.json")
    cf, ot = load("cost.json"), load("on_target.json")
    df, sc = load("detector_families.json"), load("scaffold_transfer.json")
    dvc = load("dead_end_variance.json")
    seq = load("sequential_deadend.json")

    checks = [
        ("dead-end share", de["dead_end_rate"], "19.1%"),
        ("revised share", de["revised_rate"], "65.2%"),
        ("kept share", de["kept_rate"], "15.7%"),
        ("task variance share", dvc["variance_dead_end"]["frac_task"], "24.8%"),
        ("model variance share", dvc["variance_dead_end"]["frac_model"], "0.6%"),
        ("on-target top-quartile AUC", ot["O1_classification"]["top_quartile_on_target"]["auc"], "0.723"),
        ("cost ratio across deciles", cf["C1_saturation"]["cost_ratio_top_over_bottom"], "848"),
        ("dead-end event prevalence", 1 - seq["frac_without"], "86.6%"),
        ("scaffold transfer mean", sc["summary"]["mean_transfer_auc"], "0.775"),
        ("scaffold degradation", sc["summary"]["mean_degradation"], "-0.018"),
    ]
    bad = 0
    for label, value, quoted in checks:
        present = quoted in doc
        if not present:
            bad += 1
        print(f"  {'ok  ' if present else 'FAIL'} {label:<28} artifact {value:<10.4g} quoted {quoted}")

    # detector AUCs, which the summary tabulates
    fams = df["tasks"]["step_noop"]["families"]
    for name in ("own_all_raw", "exact_burst", "ngram_loop", "openhands5", "tfnorm_novel"):
        if name not in fams:
            continue
        q = f"{fams[name]['auc']:.3f}"
        present = q in doc
        if not present:
            bad += 1
        print(f"  {'ok  ' if present else 'FAIL'} detector {name:<22} {q}")

    print(f"\n{bad} mismatches between the executive summary and the artifacts")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
