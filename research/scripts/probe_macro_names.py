"""Find which generated macro names LaTeX refuses, by bisection and injection."""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "research", "archive", "paper_v1")
gen_path = os.path.join(PAPER, "generated_tb2.tex")
lines = open(gen_path, encoding="utf-8").read().split("\n")
names = []
for line in lines:
    m = re.match(r"\\newcommand\{\\(\w+)\}", line)
    if m:
        names.append(m.group(1))
print(f"macro definitions: {len(names)}")
print(f"longest names: {sorted(set(names), key=len, reverse=True)[:5]}")

# Test each name alone, properly escaped this time.
bad = []
for n in names:
    tex = ("\\documentclass{article}\n"
           f"\\newcommand{{\\{n}}}{{1.5}}\n"
           "\\begin{document}\n"
           f"x \\{n}\n"
           "\\end{document}\n")
    p = os.path.join(PAPER, "_probe.tex")
    open(p, "w", encoding="utf-8").write(tex)
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "_probe.tex"],
                       cwd=PAPER, capture_output=True, text=True, timeout=120)
    if "Missing \\begin{document}" in (r.stdout or ""):
        bad.append(n)
print(f"names LaTeX rejects: {len(bad)}")
print(bad[:20])
