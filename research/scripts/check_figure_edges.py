"""Check whether any ink in a saved figure is cut off at the raster edge.

Reading the figures confirms the layout; this confirms the pixels.  A tight bbox crop that lands
inside a glyph leaves ink running to the very last column or row, which is a cropped character,
whereas normal padding leaves white margins.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
FIG = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "research", "archive", "paper_v1", "figures"))


def main() -> None:
    worst = 0
    for name in sorted(os.listdir(FIG)):
        if not name.endswith(".png"):
            continue
        a = np.asarray(Image.open(os.path.join(FIG, name)).convert("L"), dtype=np.float32) / 255.0
        ink = a < 0.9
        h, w = ink.shape
        edges = {
            "left": int(ink[:, 0].sum()), "right": int(ink[:, -1].sum()),
            "top": int(ink[0].sum()), "bottom": int(ink[-1].sum()),
        }
        # distance from each edge to the first row/column that contains any ink
        col_any = ink.any(axis=0)
        row_any = ink.any(axis=1)
        first_col = int(np.argmax(col_any)) if col_any.any() else w
        last_col = w - 1 - int(np.argmax(col_any[::-1])) if col_any.any() else -1
        first_row = int(np.argmax(row_any)) if row_any.any() else h
        last_row = h - 1 - int(np.argmax(row_any[::-1])) if row_any.any() else -1
        flag = "CUT" if any(v > 0 for v in edges.values()) else "ok "
        worst += 1 if flag == "CUT" else 0
        print(f"  {flag} {name:28} {w}x{h}  edge ink {edges}  margins "
              f"L{first_col} R{w-1-last_col} T{first_row} B{h-1-last_row}")
    print(f"\nfigures with ink at the raster edge: {worst}")


if __name__ == "__main__":
    main()
