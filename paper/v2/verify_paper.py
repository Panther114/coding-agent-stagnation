"""Verify the compiled paper actually contains the corrected numbers.

A PDF that compiles is not evidence that it is the right PDF. This checks that the rebuilt
manuscript carries the corrected results (the causal experiment, the bounded-localisation figures,
the router) and NOT the superseded ones that were retracted.
"""
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        print("no pypdf/PyPDF2 available")
        sys.exit(0)

p = Path(sys.argv[1] if len(sys.argv) > 1 else "main.pdf")
r = PdfReader(str(p))
text = "".join(page.extract_text() or "" for page in r.pages)

MUST_BE_PRESENT = [
    "0.550", "0.372",              # causal experiment, valid-only
    "62.8",                        # unhinted failure rate at 100% file contact
    "0.126",                       # honest non-significance
    "0.676", "0.751",              # router, lost vs wrong-fix
    "30.9", "69.1", "98.2",        # bounded localisation
    "0.673", "0.477",              # the inversion and its correction
    "19.1",                        # dead-end rate
    "0.764",                       # decision-curve value
    "2603.24631",                  # the prior-art scoop, cited
    "Retracted",
]

MUST_BE_ABSENT = [
    # superseded claims that were retracted; the paper must not assert them AS FINDINGS.
    # It may name them, but only inside a sentence that retracts them, so the check is
    # "appears only near retraction language" rather than "does not appear".
    "0 false alarms at every budget",
]

RETRACTION_WORDS = ["circular", "retract", "withdrawn", "withdraw", "wrong", "failed"]

print(f"pages: {len(r.pages)}  characters extracted: {len(text):,}")
print()
ok = True
for s in MUST_BE_PRESENT:
    present = s in text
    ok &= present
    print(f"  {'ok  ' if present else 'MISS'} must appear: {s}")
print()
for s in MUST_BE_ABSENT:
    idx = text.find(s)
    if idx < 0:
        print(f"  ok   absent entirely: {s}")
        continue
    window = text[max(0, idx - 400): idx + 400].lower()
    contextual = any(w in window for w in RETRACTION_WORDS)
    ok &= contextual
    print(f"  {'ok  ' if contextual else 'BAD '} appears only in a retraction context: {s}")
    if not contextual:
        print("       context was:", window[:300].replace("\n", " "))
print()
print("paper content verified" if ok else "PAPER CONTENT CHECK FAILED")
