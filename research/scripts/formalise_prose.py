"""Formalise phrasing and standardise terminology.

Prose audit found the paper is structurally clean (no repeated sentences or phrases across files),
but carries a handful of markers that read as a lab notebook rather than a paper. Fix those, and
standardise on "alarm" for the crossing event and "detect" for the episode-level decision, since
"fire" was used informally for both.
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAPER = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "archive", "paper_v1"))
FILES = ("abstract.tex", "sections_intro.tex", "sections_related.tex", "sections_definition.tex",
         "sections_method.tex", "sections_setup.tex", "sections_results.tex",
         "sections_discussion.tex")

REPLACEMENTS = [
    # terminology: "fire" was informal and ambiguous between alarm and detection
    (r"\bfires on\b", "alarms on"),
    (r"\bfiring on\b", "alarming on"),
    (r"\bfired\b", "alarmed"),
    (r"\bfires\b", "alarms"),
    (r"\bfiring rate\b", "alarm rate"),
    (r"\bfire\b", "alarm"),
    # hedging / informality
    (r"\bwe did\b", "we ran"),
    (r"\ba lot of\b", "many"),
    (r"\ba lot\b", "substantially"),
    (r"\bactually\b", ""),
    (r"\bdeliberately cautious\b", "conservative"),
    (r"\bour own earlier reading\b", "our earlier reading"),
    (r"\bworth stating plainly\b", "notable"),
    (r"\bworth stating\b", "notable"),
    (r"\bworth knowing\b", "notable"),
    (r"\bit turns out\b", "in fact"),
    (r"\bthe honest reading\b", "the correct reading"),
    (r"\bhonest\b", "conservative"),
    (r"\bpretty much\b", "largely"),
    (r"\bkind of\b", "somewhat"),
    (r"\bquite\b", ""),
]

total = 0
for f in FILES:
    p = os.path.join(PAPER, f)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8").read()
    orig = s
    for pat, rep in REPLACEMENTS:
        s = re.sub(pat, rep, s, flags=re.I)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r" +([,.;:])", r"\1", s)
    if s != orig:
        open(p, "w", encoding="utf-8").write(s)
        total += 1
        print(f"  rewrote {f}")

print(f"files changed: {total}")

# report what remains
print("\nremaining informal markers:")
for label, pat in (("we did", r"\bwe did\b"), ("a lot", r"\ba lot\b"),
                   ("actually", r"\bactually\b"), ("fire/fired", r"\bfir(e|ed|es)\b"),
                   ("honest", r"\bhonest\b"), ("kind of", r"\bkind of\b")):
    n = 0
    for f in FILES:
        p = os.path.join(PAPER, f)
        if os.path.exists(p):
            n += len(re.findall(pat, open(p, encoding="utf-8").read(), re.I))
    print(f"  {label:12} {n}")
