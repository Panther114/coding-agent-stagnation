"""Validate the audit's own pixel mapping: does each text box really contain that text's ink?

Renders a known string at a known place, then checks that the ink mask returned by the audit
helpers has ink exactly in that box and nowhere else.  If this fails, every collision the audit
reports is suspect, so it runs before the figures are trusted.
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import audit_figure_text as aft  # noqa: E402


def ink_centroid(fig, box):
    m = aft._ink_in(fig, box)
    ys, xs = np.nonzero(m)
    return (float(xs.mean() + box[0]), float(ys.mean() + box[1]), int(m.sum())) if m is not None \
        else (float("nan"), float("nan"), 0)


def main() -> int:
    fails = 0
    fig = plt.figure(figsize=(4.0, 2.0), dpi=100)
    ax = fig.add_axes([0.15, 0.2, 0.7, 0.6])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    t1 = ax.text(0.05, 0.75, "LEFTTOP", fontsize=8, va="top")
    t2 = ax.text(0.95, 0.75, "RIGHTTOP", fontsize=8, ha="right", va="top")
    t3 = ax.text(0.5, 0.5, "BOTTOM", fontsize=8, ha="center", va="top")
    fig.canvas.draw()

    # the ink centroid must sit inside the reported box, and the reported box must contain the
    # glyph's true width (an 8 pt "LEFTTOP" is about 40 px at 100 dpi, not 8 px and not 200 px)
    for name, t in (("LEFTTOP", t1), ("RIGHTTOP", t2), ("BOTTOM", t3)):
        bb = aft._bbox(t)
        box = [bb.x0, bb.y0, bb.x1, bb.y1]
        cx, cy, ink = ink_centroid(fig, box)
        inside = (box[0] <= cx <= box[2]) and (box[1] <= cy <= box[3]) and ink > 5
        width = box[2] - box[0]
        sane = 20 <= width <= 120
        print(f"  {name:9} box w {width:5.1f} cx {cx:6.1f} cy {cy:6.1f} ink {ink:4d} "
              f"{'ok' if inside and sane else 'MISALIGNED'}")
        fails += 0 if (inside and sane) else 1
        if name == "BOTTOM":
            print(f"    (column where ink starts: "
                  f"{int(np.nonzero(aft._ink_in(fig, box).any(axis=0))[0][0]) + int(box[0])})")

    # a box far away must contain no ink
    for name, t in (("LEFTTOP", t1), ("RIGHTTOP", t2), ("BOTTOM", t3)):
        bb = aft._bbox(t)
        far = [bb.x0 + 400, bb.y0 + 200, bb.x1 + 400, bb.y1 + 200]
        m2 = aft._ink_in(fig, far)
        if m2 is not None and m2.sum() > 0:
            print(f"  {name:9} box far away still has {int(m2.sum())} ink px -> mapping is wrong")
            fails += 1

    # two labels printed on top of each other must be reported; two labels 20 px apart must not
    fig2 = plt.figure(figsize=(4.0, 1.2), dpi=100)
    ax2 = fig2.add_axes([0.1, 0.2, 0.8, 0.6])
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.axis("off")
    ax2.text(0.50, 0.5, "OVERPRINT", fontsize=9, ha="center", va="center")
    ax2.text(0.503, 0.5, "OVERPRINT", fontsize=9, ha="center", va="center")
    fig2.canvas.draw()
    ov = aft.diagnose_text_overlaps(fig2)
    print(f"  overprinted pair (reserved boxes): {len(ov)} (expect >=1)")
    fails += 0 if ov else 1
    fp2, und2 = aft.glyph_footprints(fig2)
    ov2 = aft.overlap_from_footprints(fp2)
    print(f"  overprinted pair (glyph ink): {len(ov2)} footprints {len(fp2)} unprobeable {len(und2)} "
          f"(expect >=1)")
    fails += 0 if ov2 else 1
    plt.close(fig2)

    fig3 = plt.figure(figsize=(4.0, 1.2), dpi=100)
    ax3 = fig3.add_axes([0.1, 0.2, 0.8, 0.6])
    ax3.axis("off")
    ax3.text(0.1, 0.5, "AAA", fontsize=9, va="center")
    ax3.text(0.6, 0.5, "BBB", fontsize=9, va="center")
    fig3.canvas.draw()
    ov3 = aft.diagnose_text_overlaps(fig3)
    fp3, und3 = aft.glyph_footprints(fig3)
    ov3b = aft.overlap_from_footprints(fp3)
    print(f"  separated pair false positives: reserved {len(ov3)}, glyph ink {len(ov3b)} "
          f"(expect 0, 0)")
    # every probed label must have been found: 2 texts + xtick labels of the hidden axes
    print(f"    (glyph footprints measured: {len(fp3)}, unprobeable: {len(und3)})")
    fails += 0 if not ov3 and not ov3b else 1
    plt.close(fig3)

    # probe accuracy: the measured ink of an on-canvas label must match its reserved box closely
    fig4 = plt.figure(figsize=(4.0, 1.2), dpi=100)
    ax4 = fig4.add_axes([0.1, 0.2, 0.8, 0.6])
    ax4.axis("off")
    t4 = ax4.text(0.2, 0.5, "PROBE ME", fontsize=9, va="center")
    fig4.canvas.draw()
    fp4, _ = aft.glyph_footprints(fig4)
    got = next((f for f in fp4 if f["text"] == "PROBE ME"), None)
    box4 = aft._bbox(t4)
    if got is None:
        print("  probe accuracy: FAILED (label not measured)")
        fails += 1
    else:
        err = max(abs(got["ink"][0] - box4.x0), abs(got["ink"][1] - box4.y0),
                  abs(got["ink"][2] - box4.x1), abs(got["ink"][3] - box4.y1))
        print(f"  probe accuracy: max |ink - reserved box| = {err:.1f} px (expect < 30)")
        fails += 0 if err < 30 else 1
    plt.close(fig4)

    print("AUDIT SELF-TEST:", "PASS" if fails == 0 else f"{fails} FAILURE(S)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
