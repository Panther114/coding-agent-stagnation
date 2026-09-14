"""Find prose problems: repetition across sections, weak phrasing, and blunt instrument words.

Targets the specific complaints: not formal, not natural, too sloppy. Reports repeated sentences,
overused connectives, and first-person/meta phrasing that reads as a lab notebook rather than a
paper.
"""
from __future__ import annotations

import collections
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAPER = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "archive", "paper_v1"))
FILES = ("sections_intro.tex", "sections_related.tex", "sections_definition.tex",
         "sections_method.tex", "sections_setup.tex", "sections_results.tex",
         "sections_discussion.tex", "abstract.tex")

text = {}
raw = {}
for f in FILES:
    p = os.path.join(PAPER, f)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8").read()
    raw[f] = s
    body = re.sub(r"%.*", "", s)
    body = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", " ", body)
    body = re.sub(r"\\[a-zA-Z]+", " ", body)
    text[f] = body

# ---- repeated sentences across files ----
sents = collections.defaultdict(set)
for f, t in text.items():
    for m in re.finditer(r"[A-Z][^.!?]{40,200}[.!?]", t):
        sents[m.group(0).strip()].add(f)
dupes = {k: v for k, v in sents.items() if len(v) > 1}
print(f"=== sentences appearing in more than one file: {len(dupes)}")
for k, v in list(dupes.items())[:6]:
    print(f"  {sorted(v)}: {k[:110]}")

# ---- repeated phrases within the paper ----
flat = " ".join(text.values()).lower()
words = re.findall(r"[a-z]{4,}", flat)
grams = collections.Counter()
for n in (6, 8):
    for i in range(len(words) - n):
        grams[" ".join(words[i:i + n])] += 1
rep = [(g, c) for g, c in grams.items() if c >= 3 and len(set(g.split())) > n - 2]
rep.sort(key=lambda kv: -kv[1])
print(f"\n=== repeated 6-8 word strings (>=3 times): {len(rep)}")
for g, c in rep[:12]:
    print(f"  {c}x  {g}")

# ---- informality markers ----
print("\n=== informality / hedging markers ===")
markers = {
    "we did": r"\bwe did\b", "our own": r"\bour own\b", "we think": r"\bwe think\b",
    "kind of": r"\bkind of\b", "sort of": r"\bsort of\b", "really": r"\breally\b",
    "quite": r"\bquite\b", "just": r"\bjust\b", "a lot": r"\ba lot\b",
    "pretty": r"\bpretty\b", "actually": r"\bactually\b", "of course": r"\bof course\b",
    "let us": r"\blet us\b", "note that": r"\bnote that\b", "it turns out": r"\bit turns out\b",
    "surprisingly": r"\bsurprisingly\b", "honest": r"\bhonest\b", "sloppy": r"\bsloppy\b",
    "at all costs": r"\bat all costs\b", "we were surprised": r"\bsurprised\b",
    "deliberately": r"\bdeliberately\b", "worth stating": r"\bworth stating\b",
    "worth knowing": r"\bworth knowing\b", "worth noting": r"\bworth noting\b",
}
totals = collections.Counter()
for label, pat in markers.items():
    for f, t in text.items():
        n = len(re.findall(pat, t, re.I))
        if n:
            totals[label] += n
for label, n in totals.most_common():
    print(f"  {label:22} {n}")
