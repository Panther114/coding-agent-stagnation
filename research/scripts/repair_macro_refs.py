"""Repair specific broken macro references in the paper.

A handful of references were written before the generator settled on its naming scheme or
were simply typos.  This script maps them to the macro that actually carries the value.

Usage: python scripts/repair_macro_refs.py
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES = ("abstract.tex", "sections_intro.tex", "sections_related.tex", "sections_definition.tex",
         "sections_method.tex", "sections_setup.tex", "sections_results.tex",
         "sections_discussion.tex")

FIXES = {
    # exact broken strings left by earlier passes, mapped to macros that exist
    r"\\airConeevidencevsBfoursemanticDelta": r"\\ppairCOneevvsBFoursemDelta",
    r"\\pwithinBones30": r"\\pwithinBOnestepThreeZero",
    r"\\withinBones30": r"\\pwithinBOnestepThreeZero",
    r"\\pwithinBOneStepThirty": r"\\pwithinBOnestepThreeZero",
    r"\\pcalLsemB5Det": r"\\pcalLsemBFiveDet",
    r"\\pcalLsemB5Saved": r"\\pcalLsemBFiveSaved",
    r"\\calLsemB5Det": r"\\pcalLsemBFiveDet",
    r"\\calLsemB5Saved": r"\\pcalLsemBFiveSaved",
    r"\\ppairBTwoerthreevsBFoursemDelta": r"\\ppairBTworepThreevsBFoursemDelta",
    r"\\pairBTwoerthreevsBFoursemDelta": r"\\ppairBTworepThreevsBFoursemDelta",
    r"\\setupWindows": r"\\pnWindows",
    # AUC and within-run families with the names the generator actually uses
    r"\\paucBTwoerthree\b": r"\\paucBTworepThree",
    r"\\aucBTwoerthree\b": r"\\paucBTworepThree",
    r"\\aucBtwoexactrepthree\b": r"\\paucBTworepThree",
    r"\\paucCOneevidence\b": r"\\paucCOneevidence",
    r"\\aucCOneevidence\b": r"\\paucCOneevidence",
    r"\\aucConeevidence\b": r"\\paucCOneevidence",
    r"\\aucC1evidence\b": r"\\paucCOneevidence",
    r"\\aucBFoursemantic\b": r"\\paucBFoursemantic",
    r"\\aucBfoursemantic\b": r"\\paucBFoursemantic",
    r"\\aucCThreeevidsem\b": r"\\paucCThreeevidSem",
    r"\\aucCthreeevidsem\b": r"\\paucCThreeevidSem",
    r"\\aucC3evidSem\b": r"\\paucCThreeevidSem",
    r"\\aucBFivenovelty\b": r"\\paucBFivenovelty",
    r"\\aucBfivenovelty\b": r"\\paucBFivenovelty",
    r"\\aucBSixverification\b": r"\\paucBSixverification",
    r"\\aucBsixverification\b": r"\\paucBSixverification",
    r"\\aucBSevenworkspace\b": r"\\paucBSevenworkspace",
    r"\\aucBsevenworkspace\b": r"\\paucBSevenworkspace",
    r"\\aucBOnestepThreeZero\b": r"\\paucBOnestepThreeZero",
    r"\\aucBones30\b": r"\\paucBOnestepThreeZero",
    r"\\aucBOnestepSixZero\b": r"\\paucBOnestepSixZero",
    r"\\aucBones60\b": r"\\paucBOnestepSixZero",
    r"\\aucCFourallHand\b": r"\\paucCFourallhand",
    r"\\aucCfourallhand\b": r"\\paucCFourallhand",
    r"\\aucLseventyeight\b": r"\\paucLsem",
    r"\\withinBFoursemantic\b": r"\\pwithinBFoursemantic",
    r"\\withinBfoursemantic\b": r"\\pwithinBFoursemantic",
    r"\\withinBFivenovelty\b": r"\\pwithinBFivenovelty",
    r"\\withinBfivenovelty\b": r"\\pwithinBFivenovelty",
    r"\\withinCThreeevidsem\b": r"\\pwithinCThreeevidSem",
    r"\\withinCthreeevidsem\b": r"\\pwithinCThreeevidSem",
    r"\\withinCOneevidence\b": r"\\pwithinCOneevidence",
    r"\\withinC1evidence\b": r"\\pwithinCOneevidence",
}


def main() -> None:
    total = 0
    for f in FILES:
        p = os.path.join(ROOT, "paper", f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        orig = s
        for pat, rep in FIXES.items():
            s, n = re.subn(pat, rep, s)
            total += n
        if s != orig:
            open(p, "w", encoding="utf-8").write(s)
            print(f"  rewrote {f}")
    print(f"total replacements: {total}")


if __name__ == "__main__":
    main()
