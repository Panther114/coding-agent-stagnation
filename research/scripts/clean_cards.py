"""Strip non-printing control bytes from the generated annotation cards.

Some observations in the source corpus contain terminal control sequences, and a handful of
them survived into the card files, including a few 0x00 bytes that make text readers treat the
file as binary.  The affected cards can still be read (one annotator reported stripping the
bytes and continuing), and a check of the gold labels found no elevated disagreement on them,
so the frozen labels are left untouched.  This script cleans the card files so that any future
human re-reading --- the step this study most needs --- is not obstructed.

Usage: python scripts/clean_cards.py [--apply]
"""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
CARDS = "data/annotations/tb2/cards_dense"
BAD = set(range(0x00, 0x09)) | {0x0b, 0x0c} | set(range(0x0e, 0x20)) | {0x7f}


def main() -> None:
    apply = "--apply" in sys.argv
    names = sorted(f for f in os.listdir(CARDS) if f.endswith(".md"))
    changed, stripped = [], 0
    for n in names:
        p = os.path.join(CARDS, n)
        with open(p, "rb") as fh:
            data = fh.read()
        out = bytes(b for b in data if b not in BAD and b != 0x0a or b == 0x0a)
        # keep newlines; drop everything else in the control range
        kept = bytearray()
        for b in data:
            if b == 0x0a or b not in BAD:
                kept.append(b)
        out = bytes(kept)
        if out != data:
            stripped += len(data) - len(out)
            changed.append(n)
            if apply:
                with open(p, "wb") as fh:
                    fh.write(out)
    print(f"cards scanned: {len(names)}")
    print(f"cards with control bytes: {len(changed)}  ({stripped} bytes)")
    for n in changed[:10]:
        print(f"  {n}")
    if not apply:
        print("\ndry run; pass --apply to rewrite the files")
    else:
        print("\nrewrote the affected cards")


if __name__ == "__main__":
    main()
