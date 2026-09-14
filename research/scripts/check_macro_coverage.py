"""Which generated macros does the paper still print, and which were dropped in the cut?

Every quantitative statement in the paper is a macro emitted by the export script.  When the paper is
shortened it is easy to delete a sentence that was the only place a value appeared, which silently
loses data.  This script lists the macros that are defined but no longer referenced anywhere in the
document, so each drop is a decision rather than an accident.

Usage: python scripts/check_macro_coverage.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.normpath(os.path.join(ROOT, "archive", "paper_v1"))

DEF_FILES = ("generated_tb2.tex", "ablation_macros.tex")
BODY_SKIP = set(DEF_FILES) | {"generated_ablation.tex", "generated_ops.tex"}


def main() -> None:
    defined = {}
    for f in DEF_FILES:
        p = os.path.join(PAPER, f)
        if not os.path.exists(p):
            continue
        txt = open(p, encoding="utf-8").read()
        for m in re.finditer(r"\\newcommand\{\\(\w+)\}", txt):
            defined[m.group(1)] = f
    body = ""
    for p in sorted(glob.glob(os.path.join(PAPER, "*.tex"))):
        if os.path.basename(p) in BODY_SKIP:
            continue
        body += open(p, encoding="utf-8").read()
    used = set(re.findall(r"\\([A-Za-z]+)", body))
    used.update(re.findall(r"\\([A-Za-z]+)\{\}", body))
    kept = sorted(n for n in defined if n in used)
    dropped = sorted(n for n in defined if n not in used)
    print(f"macros defined: {len(defined)}")
    print(f"macros printed in the document: {len(kept)}")
    print(f"macros defined but not printed: {len(dropped)}")
    # an alias is a macro whose body is exactly another macro name, plus any rerun/duplicate exports
    aliases = []
    for f in DEF_FILES:
        p = os.path.join(PAPER, f)
        if not os.path.exists(p):
            continue
        for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{\\(\w+)\}", open(p, encoding="utf-8").read()):
            aliases.append(m.group(1))
    real = [d for d in dropped if d not in aliases]
    print(f"  of which aliases or unprinted duplicates: {len(dropped) - len(real)}")
    print(f"  genuinely dropped values: {len(real)}")
    for i in range(0, len(real), 6):
        print("    " + ", ".join(real[i:i + 6]))


if __name__ == "__main__":
    main()
