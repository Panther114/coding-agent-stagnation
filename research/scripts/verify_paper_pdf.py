"""Does the shortened paper still print the values it is supposed to print?

The length cut removed tables and sentences, so this checks the compiled PDF for the specific
quantities the paper claims, plus the structural elements (sections, figures, tables, references).
It reads the PDF, not the sources, so it fails if a value exists in a macro but no longer reaches the
page.

Usage: python scripts/verify_paper_pdf.py
"""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import pypdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.normpath(os.path.join(ROOT, "archive", "paper_v1"))

MUST_HAVE = [
    ("title", "ActivityIsNotProgress"),
    ("detector rule", "smooththescoreover3windows"),
    ("reference = first 15%", "first15%"),
    ("alarm detection 53%", "53%"),
    ("nested detection 56%", "56%"),
    ("region-level false alarms", "17%"),
    ("episode count", "68"),
    ("episode separation 83%", "83%"),
    ("position proxy 12 of 36", "12of36"),
    ("positive prevalence", "0.284"),
    ("semantic ROC-AUC", "0.775"),
    ("evidence ROC-AUC", "0.587"),
    ("exact repetition ROC-AUC", "0.608"),
    ("workspace ROC-AUC", "0.557"),
    ("label agreement kappa", "\u03ba=0.70"),
    ("label agreement percent", "88.1%binaryagreement"),
    ("redaction share", "25.5"),
    ("number audit", "checkedvaluesmatched"),
    ("window-size sensitivity", "0.565"),
    ("cross-corpus limitation", "cross-corpuscheck"),
    ("within-run AUC", "0.633"),
    ("paired delta evidence-semantic", "-0.193"),
    ("ablation semantic", "-0.044"),
]


def main() -> None:
    pdf = os.path.join(PAPER, "main.pdf")
    r = pypdf.PdfReader(pdf)
    flat = re.sub(r"\s+", "", "".join((p.extract_text() or "") for p in r.pages))
    print(f"pages: {len(r.pages)}   characters of text: {len(flat)}")
    bad = 0
    for label, needle in MUST_HAVE:
        ok = needle in flat
        print(f"  {'ok  ' if ok else 'FAIL'} {label:34} {needle}")
        bad += 0 if ok else 1

    print("\nstructure:")
    for what, pat in (("figures", r"Figure\s*\d"), ("tables", r"Table\s*\d"),
                      ("sections", r"\d+\.\d+"), ("references", r"\[1\]")):
        print(f"  {what:10} {len(re.findall(pat, ' '.join((p.extract_text() or '') for p in r.pages)))}")
    refs = len(re.findall(r"\n\[\d+\]", "\n".join((p.extract_text() or "") for p in r.pages)))
    print(f"  bibliography entries rendered: {refs}")
    print("\nVERDICT:", "PASS" if bad == 0 else f"{bad} MISSING VALUE(S)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
