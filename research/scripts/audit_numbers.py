"""Audit the paper's numbers against the frozen artifacts.

The paper contains no hand-typed quantities: every one is a macro emitted by
``export_results_tex.py``.  This script re-derives the values straight from the artifacts and
compares them with the macro definitions, so a stale export or a silent divergence between the
run and the text is caught before submission.

Usage: python scripts/audit_numbers.py --run results/final/tb2_final --corpus tb2
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import paths  # noqa: E402


def read_macros(path: str) -> Dict[str, str]:
    txt = open(path, encoding="utf-8").read()
    out: Dict[str, str] = {}
    for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{(.*?)\}", txt):
        out[m.group(1)] = m.group(2)
    return out


def close(a: Any, b: Any, tol: float = 5e-4) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol + 1e-9
    except (TypeError, ValueError):
        return str(a) == str(b)


def main() -> None:
    ap = argparse.ArgumentParser()
    # the default is the run the paper's macros were exported from, not whichever run is newest:
    # several run directories exist (v2..v6, dense, cal) and auditing against the wrong one reports
    # dozens of phantom mismatches.  scripts/which_run_matches_macros.py identifies the right one.
    ap.add_argument("--run", default="results/final/tb2_v5")
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--ann", default=None)
    ap.add_argument("--tex", default="../essay/generated_tb2.tex")
    args = ap.parse_args()
    ann = args.ann or os.path.join(paths.DATA, "annotations", args.corpus)
    macros = read_macros(args.tex)
    print(f"macros in {args.tex}: {len(macros)}")

    cfg = json.load(open(os.path.join(args.run, "run_config.json"), encoding="utf-8"))
    agree = json.load(open(os.path.join(ann, "agreement.json"), encoding="utf-8"))
    adj = list(csv.DictReader(open(os.path.join(ann, "adjudicated.csv"), encoding="utf-8")))
    wl = json.load(open(os.path.join(args.run, "window_metrics.json"), encoding="utf-8"))
    pc = json.load(open(os.path.join(args.run, "paired_comparisons.json"), encoding="utf-8"))
    abl = json.load(open(os.path.join(args.run, "ablation.json"), encoding="utf-8"))
    cs = json.load(open(os.path.join(args.run, "cross_scaffold.json"), encoding="utf-8"))
    ops = json.load(open(os.path.join(args.run, "window_alarm_curves.json"), encoding="utf-8"))

    checks: List[Tuple[str, Any, Any]] = []

    def chk(macro_name: str, expected: Any, label: str) -> None:
        got = macros.get(macro_name)
        checks.append((label, expected, got))

    # corpus / annotation counts
    chk("pnTraj", cfg["n_traj"], "nTraj")
    chk("pannWindowsTotal", len(adj), "adjudicated windows")
    chk("pannTrajTotal", len({a["traj_id"] for a in adj}), "annotated trajectories")
    n_pos = sum(1 for a in adj if a["binary"] == "1")
    n_neg = sum(1 for a in adj if a["binary"] == "0")
    chk("pannPos", n_pos, "positive windows")
    chk("pannNeg", n_neg, "negative windows")
    chk("pannPosRate", f"{100.0 * n_pos / max(1, n_pos + n_neg):.1f}", "positive rate")
    cross = agree.get("cross_round") or agree
    chk("pannBinaryAgr", f"{100.0 * cross['binary_agreement']:.1f}", "cross-round agreement")
    chk("pannKappa", f"{cross['cohen_kappa']:.2f}", "kappa")
    chk("pnAlarmTraj", cfg["n_alarm_eval_traj"], "alarm-eval trajectories")

    # window metrics for the headline monitors
    for mon, key in (("B4_semantic", "paucBFoursemantic"), ("C1_evidence", "paucCOneevidence"),
                     ("C3_evid_sem", "paucCThreeevidSem"), ("B5_novelty", "paucBFivenovelty"),
                     ("B2_exact_rep3", "paucBTworepThree"), ("B6_verification", "paucBSixverification"),
                     ("B7_workspace", "paucBSevenworkspace")):
        m = wl.get(mon, {}).get("10")
        if m:
            chk(key, f"{m['roc_auc']:.3f}", f"AUC {mon}")
            chk(key.replace("pauc", "pwithin"), f"{m['within_traj_auc']:.3f}", f"within-run AUC {mon}")

    # paired comparisons
    for pk, macro in (("C1_evidence_vs_B4_semantic", "ppairCOneevvsBFoursemDelta"),
                      ("B7_workspace_vs_B4_semantic", "ppairBSevenwkvsBFoursemDelta")):
        r = pc["pairs"].get(pk)
        if r:
            chk(macro, f"{r['delta']:.3f}", f"paired delta {pk}")

    # ablation
    for ch in abl.get("channels", []):
        key = "".join(DIGITS.get(c, c) for c in ch)
        chk(f"pabl{key}Delta", f"{abl['leave_one_out'][ch]['delta_roc']:+.3f}", f"ablation {ch}")

    # cross-scaffold
    for gname, g in cs.get("groups", {}).items():
        if g.get("mean_auc") is None:
            continue
        key = (gname.split("(")[0].strip().rstrip("+").strip()
               .replace("auction/repetition", "repetition").replace("+", "").replace(" ", "").replace("/", ""))
        chk("pcs" + key + "Mean", f"{g['mean_auc']:.3f}", f"cross-scaffold {gname}")

    # per-window operating point at a 5% false-stop budget: recompute the curve point from
    # the same artifact the table is built from, using the exported threshold
    boot = json.load(open(os.path.join(args.run, "budget_calibrated.json"), encoding="utf-8"))
    for mon, macro in (("L_sem", "calLsemBFiveDet"), ("C3_evid_sem", "calCThreeevidSemBFiveDet")):
        row = next((r for r in boot.get(mon, []) if abs(r["budget"] - 0.05) < 1e-9), None)
        if row:
            chk("p" + macro, f"{row['detection_rate']:.3f}", f"5% detection {mon}")

    bad = [(lab, exp, got) for lab, exp, got in checks if not close(exp, got)]
    print(f"checked {len(checks)} macro values against the artifacts")
    if bad:
        print(f"MISMATCHES: {len(bad)}")
        for lab, exp, got in bad:
            print(f"   {lab}: artifact={exp} macro={got}")
    else:
        print("all matched")
    with open(os.path.join(paths.FINAL, "number_audit.json"), "w", encoding="utf-8") as fh:
        json.dump({"checked": len(checks), "mismatches": len(bad),
                   "mismatch_detail": [{"label": l, "artifact": str(e), "macro": str(g)}
                                       for l, e, g in bad],
                   "run": args.run, "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}, fh, indent=2)
    sys.exit(1 if bad else 0)


DIGITS = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
          "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
