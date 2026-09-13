"""Probe the real control-sequence length limit with a correct LaTeX file."""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "paper")
DOC = "\\documentclass{article}\n"


def run(name: str) -> bool:
    body = (DOC
            + "\\newcommand{\\" + name + "}{0.000}\n"
            + "\\begin{document}\n"
            + "x \\" + name + "\n"
            + "\\end{document}\n")
    open(os.path.join(PAPER, "_probe.tex"), "w", encoding="utf-8", newline="\n").write(body)
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "_probe.tex"],
                       cwd=PAPER, capture_output=True, text=True, timeout=120)
    out = (r.stdout or "")
    if "Fatal error" in out or "Missing \\begin{document}" in out:
        return False
    return True


print("baseline:", run("abc"))
for n in (20, 24, 26, 28, 29, 30, 31, 32, 34, 36, 40):
    print(f"  length {n}: {'ok' if run('q' * n) else 'FAIL'}")
print("digit-containing:", run("qC1evidenceDetectionRate"))
print("digit-free same length:", run("qCxevidenceDetectionRate"))
