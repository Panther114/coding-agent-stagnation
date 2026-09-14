"""Which macro-derived values did the 28-page draft print that the 19-page version no longer prints?

The length cut removed rows from tables and paragraphs from the text, so this compares the two
drafts macro by macro and lists what disappeared.  Values that are *represented differently* (a
dropped table row whose monitor is still plotted in a figure) are not losses; this list is what a
reviewer should sanity-check before the shorter version is submitted.

Usage: python scripts/compare_dropped_values.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import pypdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.normpath(os.path.join(ROOT, "archive", "paper_v1"))
OLD_PDF = os.path.join(ROOT, "results", "backup_pre_dense2", "main_pre_dense2.pdf")


def main() -> None:
    if not os.path.exists(OLD_PDF):
        print(f"no previous draft at {OLD_PDF}")
        return
    old = pypdf.PdfReader(OLD_PDF)
    old_flat = re.sub(r"\s+", "", "".join((p.extract_text() or "") for p in old.pages))
    new = pypdf.PdfReader(os.path.join(PAPER, "main.pdf"))
    new_flat = re.sub(r"\s+", "", "".join((p.extract_text() or "") for p in new.pages))
    print(f"previous draft {len(old.pages)} pages, {len(old_flat)} chars")
    print(f"current draft  {len(new.pages)} pages, {len(new_flat)} chars")

    # every numeric macro value the OLD draft printed
    macros = {}
    for f in ("generated_tb2.tex", "ablation_macros.tex"):
        p = os.path.join(PAPER, f)
        if not os.path.exists(p):
            continue
        for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{(.*?)\}", open(p, encoding="utf-8").read()):
            macros[m.group(1)] = m.group(2)

    interesting = {k: v for k, v in macros.items() if re.fullmatch(r"[-+]?\d+(\.\d+)?%?", v)
                   and len(v) >= 4}
    lost = []
    for k, v in interesting.items():
        if v in old_flat and v not in new_flat:
            lost.append((k, v))
    print(f"\nnumeric macro values printed by the previous draft but not by this one: {len(lost)}")
    for k, v in sorted(lost)[:120]:
        print(f"  {k:36} {v}")
    if len(lost) > 120:
        print(f"  ... and {len(lost) - 120} more")
    print("\nNote: a value can be absent because its table row was cut while the monitor is still "
          "plotted in a figure, or because the sentence quoting it was condensed.  Both are "
          "deliberate; nothing in the release changes.")


if __name__ == "__main__":
    main()
