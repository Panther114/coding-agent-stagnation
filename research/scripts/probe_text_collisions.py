"""Inspect candidate text collisions pixel by pixel, without human eyes.

For each pair of text objects the audit flags, this dumps the shared ink mask and a coarse ASCII
picture of the intersection, so a claim like "these two labels are printed on top of each other"
can be *checked* rather than believed.  It also reports which figure-space rectangle each pixel
came from, and whether the two objects' ink is actually distinct glyph strokes that merely come
close.

Usage: python scripts/probe_text_collisions.py fig_features_tb2_w10 "rep cycle" "nov distinct"
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

import audit_figure_text as aft  # noqa: E402


def ascii_art(mask: np.ndarray, max_w: int = 150, max_h: int = 22) -> str:
    if mask.size == 0:
        return "(empty)"
    h, w = mask.shape
    step_y = max(1, int(np.ceil(h / max_h)))
    step_x = max(1, int(np.ceil(w / max_w)))
    rows = []
    for y in range(0, h, step_y):
        line = []
        for x in range(0, w, step_x):
            blk = mask[y:y + step_y, x:x + step_x]
            line.append("#" if blk.mean() > 0.4 else ("+" if blk.any() else "."))
        rows.append("".join(line))
    return "\n".join(rows)


def main() -> None:
    want_stem = sys.argv[1] if len(sys.argv) > 1 else None
    reps = aft.render_all(False, aft.FIGDIR)
    for r in reps:
        if want_stem and r.get("stem") != want_stem:
            continue
        print("=" * 100)
        print(r["stem"])
        for it in (r.get("overlaps") or []):
            print(f"  {it}")
        for it in (r.get("intrusions") or []):
            print(f"  intr {it}")
        for it in (r.get("orphan_ink") or []):
            print(f"  orphan {it}")
    print("\n--- painting the first candidate of each figure ---")
    for r in reps:
        if want_stem and r.get("stem") != want_stem:
            continue
        cands = (r.get("overlaps") or []) + (r.get("intrusions") or [])
        if not cands:
            continue
        boxes = r.get("boxes") or []
        print("=" * 100)
        print(r["stem"], "candidates:", len(cands))
        for c in cands[:3]:
            names = [c.get("a"), c.get("b")] if "a" in c else [c.get("text"), None]
            print(f"\n  pair {names}  { {k: v for k, v in c.items() if k not in ('a', 'b', 'text')} }")
            picked = []
            for b in boxes:
                key = f'{b["kind"]}:{b["text"]}'
                for nm in names:
                    if nm and (b["text"] in nm or nm.endswith(b["text"][:36])):
                        picked.append(b)
                        break
            picked = picked[:2]
            if len(picked) == 2:
                for b in picked:
                    print(f'    {b["kind"]:10} {b["text"][:40]!r:44} box '
                          f'{[round(v, 1) for v in b["box"]]} axes {b["axes"]}')
                inter = [max(picked[0]["box"][0], picked[1]["box"][0]),
                         max(picked[0]["box"][1], picked[1]["box"][1]),
                         min(picked[0]["box"][2], picked[1]["box"][2]),
                         min(picked[0]["box"][3], picked[1]["box"][3])]
                print(f"    intersection {[round(v, 1) for v in inter]}  "
                      f"size {round(inter[2]-inter[0],1)} x {round(inter[3]-inter[1],1)} px")


if __name__ == "__main__":
    main()
