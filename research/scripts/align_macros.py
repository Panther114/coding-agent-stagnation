"""Align macro references in the paper with the names actually generated.

Reads the macro names from ``research/archive/paper_v1/generated_tb2.tex`` and rewrites every reference in the
section files so that it matches, using a canonical short form for each semantic name.  Any
reference with no corresponding macro is reported, because a missing macro silently prints as
"??" in LaTeX and would corrupt a number in the paper.

Usage: python scripts/align_macros.py [--check]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES = ("main.tex", "abstract.tex", "sections_intro.tex", "sections_related.tex",
         "sections_definition.tex", "sections_method.tex", "sections_setup.tex",
         "sections_results.tex", "sections_discussion.tex")

# semantic name -> the exact macro name emitted by export_results_tex.py
CANON = {
    "aucB4semantic": "aucB4semantic", "aucC1evidence": "aucC1evidence",
    "aucC3evidSem": "aucC3evidSem", "aucB2exactrep3": "aucB2rep3",
    "aucB5novelty": "aucB5novelty", "aucB6verification": "aucB6verification",
    "aucB7workspace": "aucB7workspace", "aucB1step30": "aucB1step30",
    "aucB1step60": "aucB1step60", "aucC4allHand": "aucC4allHand",
    "pairC1evidencevsB4semanticDelta": "pairC1evvsB4semDelta",
    "pairC1evidencevsB4semanticLo": "pairC1evvsB4semLo",
    "pairC1evidencevsB4semanticHi": "pairC1evvsB4semHi",
    "pairB7workspacevsB4semanticDelta": "pairB7wkvsB4semDelta",
    "pairB7workspacevsB4semanticLo": "pairB7wkvsB4semLo",
    "pairB7workspacevsB4semanticHi": "pairB7wkvsB4semHi",
    "pairB2rep3vsB4semanticDelta": "pairB2r3vsB4semDelta",
    "pairB6verificationvsB4semanticDelta": "pairB6vervsB4semDelta",
    "pairC3evidSemvsB4semanticDelta": "pairC3esvsB4semDelta",
    "pairC3evidSemvsB4semanticLo": "pairC3esvsB4semLo",
    "pairC3evidSemvsB4semanticHi": "pairC3esvsB4semHi",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, do not rewrite")
    args = ap.parse_args()
    gen = open(os.path.join(ROOT, "research", "archive", "paper_v1", "generated_tb2.tex"), encoding="utf-8").read()
    known = {m.group(1) for m in re.finditer(r"\\newcommand\{\\(\w+)\}", gen)}
    # bare names (macro definitions carry the short "p" prefix)
    bare = {n[1:] if n.startswith("p") else n for n in known}
    print(f"macros generated: {len(known)}")

    used, missing = set(), set()
    for f in FILES:
        p = os.path.join(ROOT, "research", "archive", "paper_v1", f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        orig = s
        # normalise any previously applied prefix, then map semantic names to canonical ones
        s = re.sub(r"\\p(?:px)?(?=[A-Za-z])", lambda m: "\\", s)
        for sem, mac in CANON.items():
            s = re.sub(r"\\" + sem + r"\b", lambda m, mm=mac: "\\" + mm, s)
        for m in re.finditer(r"\\((?:p)?([A-Za-z][A-Za-z0-9]*))\b", s):
            name = m.group(1)
            if name in bare or name in known:
                used.add(name)
        if not args.check and s != orig:
            open(p, "w", encoding="utf-8").write(s)

    # references that look generated but have no macro
    gen_like = re.compile(r"\\(p)?(auc|within|pair|cal|ann|n[A-Z]|mon|abl|outcome|corpus|desc|prauc|wParam|best)")
    for f in FILES:
        p = os.path.join(ROOT, "research", "archive", "paper_v1", f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        for m in gen_like.finditer(s):
            name = m.group(0)[1:]
            if name not in known and name not in bare and name.lstrip("p") not in bare:
                missing.add((f, m.group(0)))
    print(f"macros referenced: {len(used)}")
    print(f"references with no macro: {len(missing)}")
    for f, n in sorted(missing)[:25]:
        print(f"   {f}: {n}")


if __name__ == "__main__":
    main()
