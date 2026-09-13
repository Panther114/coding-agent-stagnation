"""Render a PNG as ASCII so a text-only checker can sanity-check a figure's layout.

Usage: python scripts/png_preview.py figures/fig_frontier_tb2_w10.png [width] [height]
"""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image

path = sys.argv[1]
W = int(sys.argv[2]) if len(sys.argv) > 2 else 110
H = int(sys.argv[3]) if len(sys.argv) > 3 else 34
im = Image.open(path).convert("L").resize((W, H))
a = np.asarray(im, dtype=float)
a = (a - a.min()) / max(1e-6, a.max() - a.min())
ramp = " .:-=+*#%@"
print(f"# {path}  {im.size[0]}x{im.size[1]} (rescaled to {W}x{H})  ink={float((a < 0.9).mean()):.3f}")
for row in a:
    print("".join(ramp[min(len(ramp) - 1, int((1 - v) * (len(ramp) - 1)))] for v in row))
