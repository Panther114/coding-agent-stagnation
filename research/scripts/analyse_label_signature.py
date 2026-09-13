"""Does the label disagreement have the behavioural signature I claimed for it?

    python scripts/analyse_label_signature.py

§2.13 of the findings claims the two targets measure different quantities: the codebook counts a
window as productive when the agent *learns* (reading, eliminating hypotheses), while the
mechanical target counts it as productive when the *workspace changes*. That is a claim about
behaviour, so it has a signature, and a signature can be checked.

Prediction: the windows the reader called PRODUCTIVE but the mechanical target called quiet should
be dominated by **read-and-search** actions with few or no edits — the agent is investigating.
Conversely the windows both call stagnant should be the ones with nothing happening at all, and
the windows both call productive should carry the edits.

If the first group turns out to be full of edits, the explanation is wrong and the findings
document must say so. The measurement uses only the action composition of the window, which was
never used to build either label.

Writes ``results/rebuild/label_signature.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "results" / "rebuild"


def main() -> None:
    ap = argparse.ArgumentParser()
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    m = pd.read_parquet(OUT / "gold_matched_windows.parquet")
    m = m[m["binary"].notna()].copy()
    m["judged"] = m["binary"].astype(int)
    m["mech"] = (m["y_stagnation"] > 0.5).astype(int)
    print(f"{len(m)} matched windows carrying both labels")

    groups = {
        "both_productive": (m["judged"] == 0) & (m["mech"] == 0),
        "judged_productive_mech_quiet": (m["judged"] == 0) & (m["mech"] == 1),
        "judged_stagnant_mech_active": (m["judged"] == 1) & (m["mech"] == 0),
        "both_stagnant": (m["judged"] == 1) & (m["mech"] == 1),
    }
    cols = [c for c in ("mix_n_edit", "mix_edit_frac", "mix_read_frac", "mix_test_frac",
                        "mix_total_actions", "nov_new_rate", "nov_new_file_rate",
                        "rep_exact_frac", "ws_n_size_deltas", "ver_n_test_obs",
                        "ver_stall_len", "ws_stall_len") if c in m.columns]
    res: Dict[str, object] = {"n_windows": int(len(m)), "groups": {}}
    print(f"\n{'group':<32} {'n':>5}  " + "  ".join(f"{c.replace('_',' ')[:13]:>13}" for c in cols[:6]))
    profiles: Dict[str, Dict[str, float]] = {}
    for name, mask in groups.items():
        sub = m[mask]
        if len(sub) < 5:
            continue
        prof = {c: float(sub[c].mean()) for c in cols}
        profiles[name] = prof
        res["groups"][name] = {"n": int(len(sub)), **prof}
        print(f"{name:<32} {len(sub):>5}  " + "  ".join(f"{prof[c]:>13.3f}" for c in cols[:6]))

    # ---- the specific prediction ------------------------------------------------------
    key = "judged_productive_mech_quiet"
    if key in profiles and "both_productive" in profiles and "mix_n_edit" in cols:
        pred = profiles[key]
        ref = profiles["both_productive"]
        res["prediction_test"] = {
            "judged_productive_mech_quiet_n": int(groups[key].sum()),
            "edits_per_window": pred.get("mix_n_edit"),
            "edits_per_window_in_both_productive": ref.get("mix_n_edit"),
            "read_fraction": pred.get("mix_read_frac"),
            "read_fraction_in_both_productive": ref.get("mix_read_frac"),
            "no_op_edits_per_window": ref.get("mix_n_edit", 0.0) - pred.get("mix_n_edit", 0.0),
        }
        t = res["prediction_test"]
        print(f"\nprediction: the {t['judged_productive_mech_quiet_n']} windows a reader called "
              f"productive but the workspace called quiet should be read-dominated")
        print(f"  edits per window: {t['edits_per_window']:.3f} "
              f"(both-productive windows: {t['edits_per_window_in_both_productive']:.3f})")
        print(f"  read fraction:    {t['read_fraction']:.3f} "
              f"(both-productive: {t['read_fraction_in_both_productive']:.3f})")
        verdict = (t["edits_per_window"] < t["edits_per_window_in_both_productive"]
                   and t["read_fraction"] >= t["read_fraction_in_both_productive"])
        res["prediction_supported"] = bool(verdict)
        print(f"\n  PREDICTION {'SUPPORTED' if verdict else 'NOT SUPPORTED'} — "
              f"{'the quiet-but-productive windows do carry fewer edits and comparable reading' if verdict else 'the signature is not there; the explanation in the findings is wrong and must be corrected'}")

    # a significance check on the edit-count difference, per window
    if key in groups:
        a = m.loc[groups[key], "mix_n_edit"].to_numpy(dtype=float)
        b = m.loc[groups["both_productive"], "mix_n_edit"].to_numpy(dtype=float)
        from scipy import stats
        if len(a) > 5 and len(b) > 5:
            u = stats.mannwhitneyu(a, b, alternative="less")
            res["edit_count_test"] = {"median_group": float(np.median(a)),
                                      "median_both_productive": float(np.median(b)),
                                      "p": float(u.pvalue)}
            print(f"  edit counts: median {np.median(a):.1f} vs {np.median(b):.1f}, "
                  f"Mann-Whitney p={u.pvalue:.2e}")

    with open(OUT / "label_signature.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    print(f"\nwrote {OUT / 'label_signature.json'}")


if __name__ == "__main__":
    main()
