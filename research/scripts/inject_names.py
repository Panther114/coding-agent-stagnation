"""Inject single macro definitions one at a time to find which names break LaTeX."""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "research", "archive", "paper_v1")

CANDIDATES = [
    "\\monC1evidenceDetectionRate",
    "\\pmonC1evidenceDetectionRate",
    "\\qmonC1evidenceDetectionRate",
    "\\zkmonxyzC1evidenceDetectionRate",
    "\\monC1evidence",
    "\\monC",
    "\\monX",
    "\\monC1",
    "\\monC1e",
    "\\monC1evidenceDetectionRateLongerName",
    "\\aucB4semantic",
    "\\pannWindowsTotal",
    "\\pcorpusSteps",
    "\\ptauTol",
    "\\pnFolds",
    "\\pa",
    "\\pz",
    "\\pk",
]


def run(name: str) -> bool:
    body = name[1:]
    tex = ("\\documentclass{article}\n"
           f"\\newcommand{{{name}}}{{0.000}}\n"
           "\\begin{document}\n"
           f"x {name}\n"
           "\\end{document}\n")
    open(os.path.join(PAPER, "_probe.tex"), "w", encoding="utf-8", newline="\n").write(tex)
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "_probe.tex"],
                       cwd=PAPER, capture_output=True, text=True, timeout=120)
    return "Missing \\begin{document}" not in (r.stdout or "")


for c in CANDIDATES:
    print(f"{'ok  ' if run(c) else 'FAIL'} {c}")
