"""Which frozen run produced the paper's macros?

The number audit re-derives values from a run directory and compares them with `generated_tb2.tex`.
It reports mismatches, and the reason can be either a stale export or the wrong run directory.  This
script settles which run the macros actually came from by scoring every frozen run on the handful of
headline quantities the paper quotes, so the audit can be pointed at the right directory.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.normpath(os.path.join(ROOT, "archive", "paper_v1"))


def read_macros(path):
    txt = open(path, encoding="utf-8").read()
    return {m.group(1): m.group(2) for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{(.*?)\}", txt)}


def value(metrics, monitor, key, w=10):
    per = metrics.get(monitor) or {}
    row = per.get(str(w)) or per.get(w)
    return row.get(key) if row else None


def main() -> None:
    mac = read_macros(os.path.join(PAPER, "generated_tb2.tex"))
    print("paper macros for the headline window metrics:")
    for name, mon, key in (("paucBFoursemantic", "B4_semantic", "roc_auc"),
                           ("pwithinBFoursemantic", "B4_semantic", "within_roc_auc"),
                           ("paucCOneevidence", "C1_evidence", "roc_auc"),
                           ("paucBSevenworkspace", "B7_workspace", "roc_auc"),
                           ("paucBTworepThree", "B2_exact_rep3", "roc_auc")):
        print(f"  {name:24} {mac.get(name)}")
    print("\nruns on disk:")
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "results", "final", "*", "window_metrics.json"))):
        run = os.path.basename(os.path.dirname(path))
        try:
            wl = json.load(open(path, encoding="utf-8"))
        except Exception as exc:
            print(f"  {run:14} unreadable: {exc}")
            continue
        vals = [value(wl, m, k) for m, k in (("B4_semantic", "roc_auc"),
                                             ("B4_semantic", "within_roc_auc"),
                                             ("C1_evidence", "roc_auc"),
                                             ("B7_workspace", "roc_auc"),
                                             ("B2_exact_rep3", "roc_auc"))]
        arrows = []
        targets = [mac.get("paucBFoursemantic"), mac.get("pwithinBFoursemantic"),
                   mac.get("paucCOneevidence"), mac.get("paucBSevenworkspace"),
                   mac.get("paucBTworepThree")]
        for v, t in zip(vals, targets):
            if v is None or t is None:
                arrows.append("?")
                continue
            arrows.append("=" if abs(round(v, 3) - float(t)) < 5e-4 else "x")
        rows.append((run, vals, "".join(arrows)))
    for run, vals, arrows in rows:
        shown = " ".join("  None" if v is None else f"{v:.3f}" for v in vals)
        print(f"  {run:14} {shown}   match[{arrows}]")
    print("\nlegend: B4 roc, B4 within, C1 roc, B7 roc, B2_rep3 roc")


if __name__ == "__main__":
    main()
