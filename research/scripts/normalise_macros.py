"""Align the paper's macro references with the generated (digit-spelled) macro names.

Usage: python scripts/normalise_macros.py [--check]
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
PREFIX = "p"
GEN_RE = re.compile(r"\\(?:p)?(?:auc|within|pair|cal|ann|mon|abl|outcome|corpus|desc|prauc|"
                    r"nTraj|nTasks|nWindows|nFolds|nAlarm|nTrain|nTest|wParam|best|tauTol)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    gen = open(os.path.join(ROOT, "research", "archive", "paper_v1", "generated_tb2.tex"), encoding="utf-8").read()
    defined = [m.group(1) for m in re.finditer(r"\\newcommand\{\\(\w+)\}", gen)]
    lookup = {}
    for n in defined:
        lookup[n] = n
        if n.startswith(PREFIX):
            lookup[n[len(PREFIX):]] = n
    print(f"defined macros: {len(defined)}")

    changed = 0
    for f in FILES:
        p = os.path.join(ROOT, "research", "archive", "paper_v1", f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        orig = s

        def repl(m):
            name = m.group(1)
            if name in lookup:
                return "\\" + lookup[name]
            return m.group(0)

        s = re.sub(r"\\([A-Za-z][A-Za-z0-9]*)", repl, s)
        if s != orig and not args.check:
            open(p, "w", encoding="utf-8").write(s)
            changed += 1
    print(f"files rewritten: {changed}")

    missing = []
    for f in FILES:
        p = os.path.join(ROOT, "research", "archive", "paper_v1", f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        for m in re.finditer(r"\\([A-Za-z][A-Za-z0-9]*)", s):
            name = m.group(1)
            if name in lookup or name in defined:
                continue
            if GEN_RE.match("\\" + name):
                missing.append((f, name))
    uniq = sorted(set(missing))
    print(f"generated-looking references with no macro: {len(uniq)}")
    for f, n in uniq[:20]:
        print(f"   {f}: \\{n}")


if __name__ == "__main__":
    main()
