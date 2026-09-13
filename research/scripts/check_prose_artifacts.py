"""Check the formalisation pass did not create awkward or ungrammatical text."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAPER = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "..", "paper"))
FILES = ("abstract.tex", "sections_intro.tex", "sections_related.tex", "sections_definition.tex",
         "sections_method.tex", "sections_setup.tex", "sections_results.tex",
         "sections_discussion.tex")

print("=== doubled words ===")
for f in FILES:
    p = os.path.join(PAPER, f)
    if not os.path.exists(p):
        continue
    for i, line in enumerate(open(p, encoding="utf-8"), 1):
        for m in re.finditer(r"\b(\w+)\s+\1\b", line, re.I):
            if m.group(1).lower() not in ("that",):
                print(f"  {f}:{i}: '{m.group(0)}'")

print("\n=== suspicious constructions from the mass replacement ===")
pats = [(r"alarms? on\s*\.", "alarm followed by period"),
        (r"\balarmed on\b", "alarmed on"),
        (r"\bthe alarm rate on\b", "alarm rate on"),
        (r"\balarm\s+alarm", "alarm alarm"),
        (r"we ran the same", "we ran the same (fine)"),
        (r"\bnotable\b", "notable (check context)")]
for f in FILES:
    p = os.path.join(PAPER, f)
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8").read()
    for pat, label in pats:
        for m in re.finditer(pat, t, re.I):
            ctx = t[max(0, m.start() - 70):m.end() + 50].replace("\n", " ")
            print(f"  [{label}] {f}: ...{ctx}...")

print("\n=== sentences that became ungrammatical (alarm as verb) ===")
for f in FILES:
    p = os.path.join(PAPER, f)
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8").read()
    for m in re.finditer(r"[^.]*\balarms?\b[^.]*\.", t):
        seg = m.group(0)
        if re.search(r"\balarms?\s+(?:on|at|when)\b", seg):
            continue
        if len(seg) < 260 and re.search(r"\balarms?\s+(?:a|the|each|one|two)\b", seg):
            print(f"  {f}: {seg.strip()[:150]}")
