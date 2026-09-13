"""Dump every text object of one figure with its real display box, to validate the audit itself."""
from __future__ import annotations

import collections
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
import audit_figure_text as aft  # noqa: E402


def main() -> None:
    stem = sys.argv[1] if len(sys.argv) > 1 else "fig_features_tb2_w10"
    reps = aft.render_all(False, aft.FIGDIR)
    rep = next(r for r in reps if r["stem"] == stem)
    boxes = rep["boxes"]
    print(f"{stem}: {len(boxes)} text objects, canvas {rep['figsize_in']} in @ {rep['dpi']} dpi")
    by_axes = collections.defaultdict(list)
    for b in boxes:
        by_axes[b["axes"]].append(b)
    for k in sorted(by_axes):
        print(f"\n--- axes {k} ({len(by_axes[k])} texts) ---")
        for b in sorted(by_axes[k], key=lambda z: -z["box"][1]):
            print(f'  {b["kind"]:12} {b["text"][:44]!r:48} '
                  f'x [{b["box"][0]:7.1f},{b["box"][2]:7.1f}] y [{b["box"][1]:7.1f},{b["box"][3]:7.1f}]')
    print("\n--- exact duplicate boxes ---")
    seen = collections.Counter(tuple(round(v, 1) for v in b["box"]) for b in boxes)
    for box, n in seen.items():
        if n > 1:
            who = [b["text"][:30] for b in boxes
                   if tuple(round(v, 1) for v in b["box"]) == box]
            print(f"  {box} x{n}: {who}")


if __name__ == "__main__":
    main()
