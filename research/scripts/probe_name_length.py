"""Determine the LaTeX control-sequence length limit empirically.

Some TeX builds fail with the confusing error "Missing \\begin{document}" when a
``\\newcommand`` name is too long, rather than reporting a length problem.  This script finds
the boundary so the generator can enforce it.

Usage: python scripts/probe_name_length.py
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "paper")


def try_name(name: str) -> bool:
    tex = ("\\documentclass{article}\n"
           f"\\newcommand{{\\{name}}}{{1.5}}\n"
           "\\begin{document}\n"
           f"x \\{name}\n"
           "\\end{document}\n")
    open(os.path.join(PAPER, "_probe.tex"), "w", encoding="utf-8").write(tex)
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "_probe.tex"],
                       cwd=PAPER, capture_output=True, text=True, timeout=120)
    return "Missing \\begin{document}" not in (r.stdout or "")


lo, hi = 1, 60
assert try_name("a" * lo), "1-character name failed, something else is wrong"
results = {}
for n in range(20, 46):
    ok = try_name("z" * n)
    results[n] = ok
    print(f"length {n}: {'ok' if ok else 'FAIL'}")
longest = max((n for n, ok in results.items() if ok), default=0)
print(f"\nlongest accepted: {longest}")
