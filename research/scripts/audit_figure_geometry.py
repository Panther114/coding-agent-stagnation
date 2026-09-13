"""Audit figure geometry: sizes, aspect ratios, and whether anything is clipped.

The user reports the figures look malformed. I cannot view images with this model, so this checks
the properties that make a figure wrong in print and that are measurable from the files:

  * pixel dimensions and effective aspect ratio
  * whether the figure is too small to read once scaled to the text width (IEEE single column is
    3.5in, two-column 7.16in); a 6.5x2.5in figure at low dpi becomes illegible
  * ink coverage and edge ink, which reveal clipped labels: if ink touches the border, text is
    being cut off
  * number of near-white rows/columns at the edges (whitespace balance)
"""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image

FIG = "../essay/figures"
TEXT_WIDTH_IN = 7.0   # usenix/ieee two-column text width
DPI = 220


def main() -> None:
    names = sorted(f for f in os.listdir(FIG) if f.endswith(".png"))
    print(f"{'figure':30}{'px':>13}{'inches':>13}{'aspect':>8}{'ink':>7}{'edge':>7}  note")
    for n in names:
        p = os.path.join(FIG, n)
        im = Image.open(p).convert("L")
        a = np.asarray(im, dtype=np.float32) / 255.0
        h, w = a.shape
        inches = (w / DPI, h / DPI)
        aspect = w / h
        ink = float((a < 0.9).mean())
        # edge ink: darkest pixel within a 2px border
        border = np.concatenate([a[:2].ravel(), a[-2:].ravel(), a[:, :2].ravel(), a[:, -2:].ravel()])
        edge_ink = float(border.min())
        notes = []
        if inches[0] < 5.0:
            notes.append("narrow")
        if edge_ink < 0.65:
            notes.append("INK AT EDGE (clipped?)")
        if ink < 0.02:
            notes.append("nearly empty")
        if ink > 0.6:
            notes.append("very dense")
        if aspect < 1.6 and "regimes" not in n:
            notes.append("check aspect")
        print(f"{n:30}{f'{w}x{h}':>13}{f'{inches[0]:.1f}x{inches[1]:.1f}':>13}"
              f"{aspect:>8.2f}{ink:>7.3f}{edge_ink:>7.2f}  {', '.join(notes)}")


if __name__ == "__main__":
    main()
