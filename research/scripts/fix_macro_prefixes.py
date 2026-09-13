"""Rewrite stale macro references in the paper text to the current generated names.

Run after re-exporting ``generated_tb2.tex``.  Two substitutions are applied across all
section files:

* any reference with the old ``\\pp`` prefix becomes ``\\ppx`` (``\\pp`` is a TeX primitive);
* any reference to a retired name is mapped through ``RENAMES``.

Usage: python scripts/fix_macro_prefixes.py
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREFIX = "p"
FILES = ("main.tex", "abstract.tex", "sections_intro.tex", "sections_related.tex",
         "sections_definition.tex", "sections_method.tex", "sections_setup.tex",
         "sections_results.tex", "sections_discussion.tex")

# retired generated names -> current names (value semantics unchanged)
RENAMES = {
    "resC1evidenceDetectionRate": "monC1evidenceDetectionRate",
    "resB6verificationDetectionRate": "monB6verificationDetectionRate",
    "resB6verificationMedianLatency": "monB6verificationMedianLatency",
    "resC1evidenceMeanSavedSteps": "monC1evidenceMeanSavedSteps",
    "resB2rep3DetectionRate": "monB2rep3DetectionRate",
    "resB4semanticDetectionRate": "monB4semanticDetectionRate",
    "resB7workspaceDetectionRate": "monB7workspaceDetectionRate",
}


def main() -> None:
    gen = open(os.path.join(ROOT, "paper", "generated_tb2.tex"), encoding="utf-8").read()
    known = {m.group(1) for m in re.finditer(r"\\newcommand\{\\(\w+)\}", gen)}
    bare = {n[len(PREFIX):] for n in known if n.startswith(PREFIX)}
    print(f"generated macros: {len(known)} (with prefix: {len(bare)})")

    total = 0
    for f in FILES:
        p = os.path.join(ROOT, "paper", f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        orig = s
        for old, new in RENAMES.items():
            s = re.sub(r"\\" + PREFIX + r"?" + old + r"\b", lambda m, n=new: "\\" + PREFIX + n, s)
            s = re.sub(r"\\" + old + r"\b", lambda m, n=new: "\\" + PREFIX + n, s)
        # strip any prefix previously applied (ppx / pp) and apply the current one
        s = re.sub(r"\\ppx?", lambda m: "\\", s)
        s = re.sub(r"\\" + PREFIX + r"?(?:" + "|".join(map(re.escape, sorted(bare, key=len, reverse=True))) + r")\b",
                   lambda m: "\\" + PREFIX + m.group(0).lstrip("\\").lstrip(PREFIX), s)
        if s != orig:
            open(p, "w", encoding="utf-8").write(s)
            total += 1
            print(f"  rewrote {f}")

    leftovers = []
    for f in FILES:
        p = os.path.join(ROOT, "paper", f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        for m in re.finditer(r"\\(ppx|pp)?(" + "|".join(map(re.escape, sorted(bare, key=len, reverse=True))) + r")\b", s):
            if m.group(1) != PREFIX:
                leftovers.append((f, m.group(0)))
    print(f"files rewritten: {total}; stale references left: {len(leftovers)} {leftovers[:6]}")


if __name__ == "__main__":
    main()
