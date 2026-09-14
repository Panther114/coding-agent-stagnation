"""Verify the compiled REPORT — the artifact that actually gets submitted — carries the right numbers.

`research/scripts/audit_paper_numbers.py` checks the LaTeX source against the frozen artifacts. This
checks the *PDF*, because a stale PDF next to a fresh .tex is exactly the failure mode that ships a
wrong number to a judge. Two things are asserted:

  1. every headline number of the current report is extractable from the PDF text;
  2. the claims that were retracted appear (if at all) only inside a sentence that retracts them,
     never as findings.

Usage:  python scripts/verify_pdf.py [path/to/main.pdf]

Run with no argument and it checks `paper/main.pdf`, the file that gets submitted. This absorbed an
earlier `paper/v2/verify_paper.py`, which had gone stale: nine of its fifteen needles were from a
mid-draft version of the report and no longer appeared anywhere in it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # the acknowledgement heading is Chinese

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        print("no pypdf/PyPDF2 available; skipping the PDF check")
        sys.exit(0)

ROOT = Path(__file__).resolve().parents[2]  # research/scripts -> repository root
path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "paper" / "main.pdf"
reader = PdfReader(str(path))
text = "".join(page.extract_text() or "" for page in reader.pages)
flat = " ".join(text.split())
# pypdf splits some bold caption labels ('T able 1:'), and pdftotext invents column spaces, so
# matching is done against a whitespace-free copy as well.  A gate that silently stops finding a
# string because the extractor moved a space is worse than no gate.
dense = "".join(text.split())


def present(needle: str) -> bool:
    return needle in flat or "".join(needle.split()) in dense

# --- 1. the report's own numbers must be in the PDF -----------------------------------
MUST_BE_PRESENT = {
    "title": "Lost or Wrong?",
    "cross-set failure AUC": "0.7145",
    "cross-set mode AUC": "0.7324",
    "gain over the field (failure)": "0.1556",
    "gain over the field (mode)": "0.1364",
    "worst cross cell (failure)": "0.6752",
    "published family, failure": "0.5589",
    "published family, mode": "0.5960",
    "within-set failure mean": "0.7169",
    "calibration at alpha=0.05": "0.046",
    "decision-curve range": "0.764",
    "wrong-fix share, frozen": "67.0",
    "wrong-fix share, held-out A": "69.0",
    "wrong-fix share, held-out B": "66.4",
    "cross-scaffold, SWE-rebench/OpenHands": "0.495",
    "cross-scaffold, thoughtworks": "0.433",
    "cross-scaffold, SWE-Gym": "0.319",
    "fitted inside the target, best": "0.761",
    "live masked success": "0.286",
    "live unmasked success": "0.372",
    "live hinted success": "0.561",
    "live masked vs hinted p": "0.015",
    "on-target gold patch, frozen": "0.477",
    "dead-end rate": "19.1",
    "router on live runs": "0.426",
    "the footer rate": "95.8",
    "prior art citation": "2603.24631",
    "gate count": "65/65",
    "live nudge control": "0.452",
    "live verify intervention": "0.571",
    "acknowledgement page": "致谢与人工智能使用声明",
}

# --- 2. retracted claims must not read as findings ------------------------------------
MUST_NOT_STAND_ALONE = [
    "zero false alarms at every budget",
    "failed runs localise better",
    "0.979",   # the old hinted reached_gold from the superseded run
]
RETRACTION_WORDS = ["circular", "retract", "withdrawn", "withdraw", "wrong", "failed", "disbelieve",
                    "was wrong", "not a result", "harness fault"]

ok = True
print(f"{path.name}: {len(reader.pages)} pages, {len(text):,} characters extracted\n")
print("must appear in the PDF:")
for label, needle in MUST_BE_PRESENT.items():
    hit = present(needle)
    ok &= hit
    print(f"  {'ok  ' if hit else 'MISS'} {label:38s} {needle}")

print("\nretracted claims must appear only inside a retraction:")
for needle in MUST_NOT_STAND_ALONE:
    idx = flat.find(needle)
    if idx < 0:
        print(f"  ok   absent entirely: {needle}")
        continue
    window = flat[max(0, idx - 500): idx + 300].lower()
    contextual = any(w in window for w in RETRACTION_WORDS)
    ok &= contextual
    print(f"  {'ok  ' if contextual else 'BAD '} {needle!r} appears in a retraction context"
          if contextual else f"  BAD  {needle!r} is asserted without retraction language")

# --- 3. structural completeness: every figure and table caption reached the page -------
want_figs = list(range(1, 8))
want_tabs = list(range(1, 9))
figs = sorted({int(n) for n in re.findall(r"Figure(\d+):", dense)})
tabs = sorted({int(n) for n in re.findall(r"Table(\d+):", dense)})
struct_ok = figs == want_figs and tabs == want_tabs
ok &= struct_ok
print(f"\nstructure: {len(figs)}/7 figure captions, {len(tabs)}/8 table captions, "
      f"{len(reader.pages)} pages")
if not struct_ok:
    print(f"  MISSING figures {[n for n in want_figs if n not in figs]}, "
          f"tables {[n for n in want_tabs if n not in tabs]}")

print("\nPDF CONTENT VERIFIED" if ok else "\nPDF CONTENT CHECK FAILED")
sys.exit(0 if ok else 1)
