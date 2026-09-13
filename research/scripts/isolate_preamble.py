"""Isolate the LaTeX preamble failure by feeding exact lines from the generated file."""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "paper")
lines = open(os.path.join(PAPER, "generated_tb2.tex"), encoding="utf-8").read().split("\n")


def run(block: str, label: str) -> str:
    tex = ("\\documentclass{article}\n" + block +
           "\n\\begin{document}\nx\n\\end{document}\n")
    open(os.path.join(PAPER, "_probe.tex"), "w", encoding="utf-8", newline="\n").write(tex)
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "_probe.tex"],
                       cwd=PAPER, capture_output=True, text=True, timeout=120)
    ok = "Missing \\begin{document}" not in (r.stdout or "")
    print(f"{label}: {'ok' if ok else 'FAIL'}")
    return r.stdout or ""


# exact single line
run(lines[77].strip(), "line 78 alone (exact)")
# with the previous line
run(lines[76].strip() + "\n" + lines[77].strip(), "lines 77-78")
# same macro written by hand
run("\\newcommand{\\pmonC1evidenceDetectionRate}{0.000}", "hand written X")
# a plain long name
run("\\newcommand{\\pmonxyzC1evidenceDetectionRate}{0.000}", "hand written Y")
# check the log for the real complaint
out = run("\n".join(l.strip() for l in lines[3:80]), "first 80 lines")
for i, line in enumerate(out.split("\n")):
    if "pmonC1" in line or "Missing" in line or "l.7" in line:
        print("  LOG:", line[:160])
