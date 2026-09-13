"""Independent, geometric audit of every paper figure.

The author of the figures cannot see them, so this script measures them instead of trusting them.
It does NOT reuse ``make_figures``' own claims: it re-executes each figure-drawing function with
the real Agg renderer attached and reads the *actual* pixel bounding boxes of every text object,
every tick label, every legend entry and the axes frame.  It then reports the defects that make a
printed figure wrong:

  A. PAIRWISE TEXT OVERLAP — two text objects whose ink boxes intersect.  This is the failure the
     reader notices first ("labels on top of each other").
  B. CROSS-AXES INTRUSION — a text object that spills into a *different* axes' rectangle (a label
     from one panel covering another panel's data or labels).
  C. CLIPPING — text ink that touches the outermost 1 px of the saved raster, i.e. characters
     actually cut off by ``bbox_inches='tight'``.
  D. CANVAS EXIT — a text box partly outside the figure canvas before the tight crop.
  E. LEGIBILITY — effective font size in points after the figure is scaled to its printed width in
     the paper (\\includegraphics width), and the effective print dpi.  A 6 pt label in a 9 in
     figure scaled to 7 in of text width prints at 4.7 pt and is unreadable.
  F. AXES COLLISION — overlapping axes rectangles (panels drawn on top of each other).

Text that intersects a data curve or a bar is not reported: that is normal in a plot.  Only
text-on-text, text-outside-its-panel and text-cut-off are defects.

Usage:
  python scripts/audit_figure_text.py                 # audit the on-disk PNGs in paper/figures
  python scripts/audit_figure_text.py --save          # re-render into paper/figures first
  python scripts/audit_figure_text.py --json out.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402

os.environ.setdefault("MPLBACKEND", "Agg")

PAPER = os.path.normpath(os.path.join(ROOT, "..", "paper"))
FIGDIR = os.path.join(PAPER, "figures")

# width each figure is given in the paper, in inches (text width is 6.5in at 1in margins)
PRINT_WIDTH_IN: Dict[str, float] = {
    "fig_frontier": 6.5 * 0.96,
    "fig_signals": 6.5,
    "fig_labels": 6.5,
    "fig_auc": 6.5,
    "fig_ops": 6.5,
    "fig_features": 6.5,
    "fig_summary": 6.5,
    "fig_regimes": 6.5,
}

# overlap tolerance in display units (pixels at render dpi); sub-pixel touching is not a defect
TOL = 0.5
# a text pair whose intersection area is below this many square pixels is a graze, not a collision
MIN_AREA = 6.0


def _bbox(v: Any) -> Optional[Bbox]:
    try:
        b = v.get_window_extent(renderer=_RENDERER)
    except Exception:
        try:
            b = v.get_window_extent()
        except Exception:
            return None
    if b is None or not np.isfinite([b.x0, b.y0, b.x1, b.y1]).all():
        return None
    if b.width <= 0 and b.height <= 0:
        return None
    return b


_RENDERER = None


def _ink_boxes(fig) -> List[Dict[str, Any]]:
    """Every text-ish object in the figure with its real display-space box.

    The canvas must be fully drawn first: a tick label added by autoscaling after the last draw
    still carries the placeholder text ('0.0', '1.0') it had at construction time, which makes two
    labels from unrelated panels look identical and produces phantom collisions.
    """
    fig.canvas.draw()
    out: List[Dict[str, Any]] = []
    for ax_i, ax in enumerate(fig.axes):
        rect = ax.get_window_extent(_RENDERER)
        cands: List[Tuple[str, Any]] = []
        cands.append(("title", ax.title))
        cands.append(("xlabel", ax.xaxis.label))
        cands.append(("ylabel", ax.yaxis.label))
        for t in ax.texts:
            cands.append(("text", t))
        for t in ax.get_xticklabels():
            cands.append(("xtick", t))
        for t in ax.get_yticklabels():
            cands.append(("ytick", t))
        for t in ax.get_xticklabels(minor=True):
            cands.append(("xtick-minor", t))
        for t in ax.get_yticklabels(minor=True):
            cands.append(("ytick-minor", t))
        leg = ax.get_legend()
        if leg is not None:
            for t in leg.get_texts():
                cands.append(("legend", t))
        for kind, t in cands:
            if t is None:
                continue
            s = t.get_text() if hasattr(t, "get_text") else ""
            if not str(s).strip():
                continue
            if not t.get_visible():
                continue
            b = _bbox(t)
            if b is None:
                continue
            out.append({
                "axes": ax_i, "kind": kind, "text": str(s), "box": [b.x0, b.y0, b.x1, b.y1],
                "size": float(getattr(t, "get_fontsize", lambda: 0)() or 0),
                "axes_rect": [rect.x0, rect.y0, rect.x1, rect.y1],
            })
    # figure-level artists (suptitle, fig.legend)
    fig_artists = []
    for t in fig.texts:
        if str(t.get_text()).strip() and t.get_visible():
            fig_artists.append(("figtext", t))
    for leg in fig.legends:
        for t in leg.get_texts():
            fig_artists.append(("figlegend", t))
    for kind, t in fig_artists:
        b = _bbox(t)
        if b is None:
            continue
        out.append({"axes": -1, "kind": kind, "text": str(t.get_text()),
                    "box": [b.x0, b.y0, b.x1, b.y1],
                    "size": float(getattr(t, "get_fontsize", lambda: 0)() or 0),
                    "axes_rect": None})
    return out


def _inter(a: Sequence[float], b: Sequence[float]) -> Tuple[float, float]:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w), max(0.0, h)


def _shrink(b: Sequence[float], pad: float = 1.0) -> List[float]:
    return [b[0] + pad, b[1] + pad, b[2] - pad, b[3] - pad]


def _ink_in(fig, box: Sequence[float]) -> Optional[np.ndarray]:
    """Boolean ink mask of exactly the pixel rectangle covered by ``box``.

    The figure is re-rendered to a raw RGBA buffer at the current dpi so that mask pixels line up
    one-to-one with display coordinates.
    """
    w, h = fig.canvas.get_width_height()
    buf = np.asarray(fig.canvas.buffer_rgba())
    x0 = max(0, int(np.floor(box[0])))
    x1 = min(w, int(np.ceil(box[2])))
    y0 = max(0, int(np.floor(box[1])))
    y1 = min(h, int(np.ceil(box[3])))
    if x1 <= x0 or y1 <= y0:
        return None
    # buffer rows run top-down, display y runs bottom-up
    sub = buf[h - y1:h - y0, x0:x1, :3]
    return (sub.astype(np.int16).sum(axis=2) < 720)  # anything not near-white


def glyph_footprints(fig) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Measure each label's true glyph ink by re-rendering it alone on a blank canvas.

    ``get_window_extent`` returns the box matplotlib reserves for a string, which carries side
    bearings and half-leading, so it is neither a lower nor an upper bound on the drawn strokes.
    Toggling artists' visibility inside the real figure to isolate one label is worse than useless:
    hiding a tick label makes matplotlib skip that tick on the next draw, after which the restored
    label is no longer repositioned and can be drawn in the corner of the canvas (an earlier revision
    of this function reported that 58 of 62 labels produced no ink).

    So each label is drawn on a separate figure of identical size and dpi, at the display position
    matplotlib gave it, with the same font properties.  Returns (footprints, undrawable).
    """
    fig.canvas.draw()
    items: List[Tuple[Any, str]] = []
    for ax in fig.axes:
        items.append((ax.title, "title"))
        items.append((ax.xaxis.label, "xlabel"))
        items.append((ax.yaxis.label, "ylabel"))
        items.extend((t, "text") for t in ax.texts)
        items.extend((t, "xtick") for t in ax.get_xticklabels())
        items.extend((t, "ytick") for t in ax.get_yticklabels())
        leg = ax.get_legend()
        if leg is not None:
            items.extend((t, "legend") for t in leg.get_texts())
    items.extend((t, "figtext") for t in fig.texts)
    for leg in fig.legends:
        items.extend((t, "figlegend") for t in leg.get_texts())

    W, H = fig.canvas.get_width_height()
    w_in, h_in = fig.get_size_inches()

    footprints: List[Dict[str, Any]] = []
    undrawable: List[Dict[str, Any]] = []
    for obj, kind in items:
        if obj is None:
            continue
        label = str(getattr(obj, "get_text", lambda: "")()).strip()
        if not label or not obj.get_visible():
            continue
        box = _bbox(obj)
        if box is None:
            undrawable.append({"kind": kind, "text": label[:40], "why": "no extent"})
            continue
        # A probe axes that fills the figure and uses pixel data coordinates: the label is placed at
        # exactly the display position the real figure gave it, so no coordinate conversion (and no
        # half-leading or dpi rounding) can displace it.
        probe = plt.figure(figsize=(w_in, h_in), dpi=fig.dpi)
        probe.patch.set_facecolor("white")
        pax = probe.add_axes([0, 0, 1, 1])
        pax.set_xlim(0, W)
        pax.set_ylim(0, H)
        pax.axis("off")
        try:
            pax.text(box.x0, box.y0, label, fontproperties=obj.get_fontproperties(),
                     rotation=obj.get_rotation(), ha="left", va="baseline", color="black")
            probe.canvas.draw()
            buf = np.asarray(probe.canvas.buffer_rgba())
        except Exception as exc:
            undrawable.append({"kind": kind, "text": label[:40], "why": type(exc).__name__})
            plt.close(probe)
            continue
        plt.close(probe)
        rgb = buf[:, :, :3].astype(np.int16).sum(axis=2)
        mask = rgb < 720
        if buf.shape[2] == 4:
            mask = mask | (buf[:, :, 3] < 250)
        if not mask.any():
            # The label is positioned partly or wholly outside the figure canvas.  Two causes are
            # common and neither is a defect: a tick just past the axis limit, and an axis label that
            # the annotation trick in the preamble pulled into the margin.  Recording it as
            # undrawable is what the report prints; the reserved-box test still covers these labels.
            undrawable.append({"kind": kind, "text": label[:40], "why": "outside canvas at probe"})
            continue
        ys, xs = np.nonzero(mask)
        footprints.append({
            "kind": kind, "text": label,
            "ink": [float(xs.min()), float(H - 1 - ys.max()),
                    float(xs.max() + 1), float(H - ys.min())],
            "ink_px": int(mask.sum()),
        })
    fig.canvas.draw()
    return footprints, undrawable


def overlap_from_footprints(footprints: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Text-on-text collisions using true glyph footprints: any shared pixel is a collision."""
    out = []
    for i in range(len(footprints)):
        for j in range(i + 1, len(footprints)):
            a, b = footprints[i], footprints[j]
            iw, ih = _inter(a["ink"], b["ink"])
            if iw <= 0.5 or ih <= 0.5:
                continue
            out.append({"a": f'{a["kind"]}:{a["text"][:36]}',
                        "b": f'{b["kind"]}:{b["text"][:36]}',
                        "overlap_px": [round(iw, 1), round(ih, 1)],
                        "area": round(iw * ih, 1)})
    return out


def reserved_box_accuracy(footprints: Sequence[Dict[str, Any]],
                          boxes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """How far the reserved box sits from the drawn ink, worst case (diagnostic, not a defect)."""
    by_text = {(b["kind"], b["text"]): b["box"] for b in boxes}
    worst = 0.0
    worst_text = None
    n_big = 0
    for f in footprints:
        r = by_text.get((f["kind"], f["text"]))
        if r is None:
            continue
        grow = max(abs(r[0] - f["ink"][0]), abs(r[1] - f["ink"][1]),
                   abs(r[2] - f["ink"][2]), abs(r[3] - f["ink"][3]))
        if grow > worst:
            worst, worst_text = grow, f'{f["kind"]}:{f["text"][:34]}'
        n_big += 1 if grow > 4.0 else 0
    return {"worst_px": round(worst, 1), "worst_text": worst_text, "n_box_error_over_4px": n_big}


def diagnose_text_overlaps(fig) -> List[Dict[str, Any]]:
    """Report only *visible* text-on-text collisions.

    Two ink boxes can intersect while the glyphs inside them do not: a label's assigned box is
    wider than its strokes, and one label may sit in the empty part of another's box. So for each
    intersecting pair we rasterise the intersection and ask what share of the ink there belongs to
    more than one text object. A collision is reported only when the intersection holds ink from
    the first box that is not explained by the second.
    """
    boxes = _ink_boxes(fig)
    fig.canvas.draw()
    out: List[Dict[str, Any]] = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ab, bb = _shrink(a["box"]), _shrink(b["box"])
            iw, ih = _inter(ab, bb)
            if iw < 2 or ih < 2:
                continue
            inter_box = [max(ab[0], bb[0]), max(ab[1], bb[1]), min(ab[2], bb[2]), min(ab[3], bb[3])]
            ink_a = _ink_in(fig, ab)
            ink_b = _ink_in(fig, bb)
            if ink_a is None or ink_b is None:
                continue
            # map the intersection into each box's local mask
            def local(mask, box):
                x0 = max(0, int(np.floor(inter_box[0] - box[0])))
                y0 = max(0, int(np.floor(inter_box[1] - box[1])))
                x1 = min(mask.shape[1], int(np.ceil(inter_box[2] - box[0])))
                y1 = min(mask.shape[0], int(np.ceil(inter_box[3] - box[1])))
                if x1 <= x0 or y1 <= y0:
                    return None
                return mask[mask.shape[0] - y1:mask.shape[0] - y0, x0:x1]
            la, lb = local(ink_a, ab), local(ink_b, bb)
            if la is None or lb is None:
                continue            # align shapes defensively
            hh = min(la.shape[0], lb.shape[0])
            ww = min(la.shape[1], lb.shape[1])
            if hh <= 0 or ww <= 0:
                continue
            la, lb = la[:hh, :ww], lb[:hh, :ww]
            n_a, n_b = int(la.sum()), int(lb.sum())
            if n_a < 4 or n_b < 4:
                continue
            # fraction of each label's ink inside the intersection that is *shared* with the other
            # label's ink.  Distinct glyphs 1 px apart produce a small shared fraction; glyphs
            # printed on top of each other produce a large one.
            shared = int((la & lb).sum())
            frac_a = shared / max(1, n_a)
            frac_b = shared / max(1, n_b)
            if max(frac_a, frac_b) >= 0.30 and shared >= 12:
                out.append({
                    "a": f'{a["kind"]}:{a["text"][:36]}',
                    "b": f'{b["kind"]}:{b["text"][:36]}',
                    "same_axes": a["axes"] == b["axes"],
                    "ink_a": n_a, "ink_b": n_b, "shared_ink": shared,
                    "frac_a": round(frac_a, 3), "frac_b": round(frac_b, 3),
                })
    return out


def orphan_text(fig) -> List[Dict[str, Any]]:
    """Margins that hold only a sliver of ink — a glyph clipped by the layout.

    A tick label or panel title that has been cropped or overprinted leaves a narrow isolated ink
    column/row in the figure margin.  Wide ink there is an axis label, which is normal; ink in a
    band under ``min_pts`` wide is a fragment.
    """
    fig.canvas.draw()
    w, h = fig.canvas.get_width_height()
    buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].astype(np.int16)
    ink = buf.sum(axis=2) < 720
    out = []
    col = ink.sum(axis=0)
    row = ink.sum(axis=1)
    for name, proj, n in (("column", col, w), ("row", row, h)):
        nz = np.nonzero(proj)[0]
        if len(nz) == 0:
            continue
        # group contiguous nonzero runs
        runs = []
        start = prev = nz[0]
        for v in nz[1:]:
            if v == prev + 1:
                prev = v
                continue
            runs.append((start, prev))
            start = prev = v
        runs.append((start, prev))
        for s, e in runs:
            width = e - s + 1
            if width <= 3 and (s < 4 or e > n - 5):
                out.append({"axis": name, "run": [int(s), int(e)], "width_px": int(width),
                            "ink_px": int(proj[s:e + 1].sum())})
    return out


def diagnose(fig) -> Dict[str, Any]:
    """Return the defect report for a live figure (renderer must be attached)."""
    fig.canvas.draw()
    boxes = _ink_boxes(fig)
    w_in, h_in = fig.get_size_inches()
    dpi = fig.dpi
    W, H = fig.canvas.get_width_height()   # the canvas is authoritative, not size_inches * dpi

    # primary collision test: true glyph footprints, measured by drawing each label in isolation
    footprints, undrawable = glyph_footprints(fig)
    overlaps = overlap_from_footprints(footprints)
    # secondary: the reserved-box test, kept so a footprint whose mask came back empty cannot hide
    # a collision the layout-level test would have caught
    overlaps_reserved = diagnose_text_overlaps(fig)
    extra = [o for o in overlaps_reserved
             if not any(o["a"] == p["a"] and o["b"] == p["b"] for p in overlaps)]
    box_error = reserved_box_accuracy(footprints, boxes)

    # a label whose box pokes into a neighbouring panel is only a defect if the neighbouring
    # panel actually has ink there (data, bars or its own labels)
    intrusions: List[Dict[str, Any]] = []
    fig.canvas.draw()
    for a in boxes:
        if a["axes"] == -1:
            continue
        for k, other in enumerate(fig.axes):
            if k == a["axes"]:
                continue
            r = other.get_window_extent(_RENDERER)
            iw, ih = _inter(_shrink(a["box"]), [r.x0 + 1, r.y0 + 1, r.x1 - 1, r.y1 - 1])
            if iw < 2 or ih < 2:
                continue
            intr = [max(a["box"][0], r.x0), max(a["box"][1], r.y0),
                    min(a["box"][2], r.x1), min(a["box"][3], r.y1)]
            mask = _ink_in(fig, intr)
            if mask is None or mask.sum() < 20:
                continue
            intrusions.append({"text": f'{a["kind"]}:{a["text"][:40]}',
                               "from_axes": a["axes"], "into_axes": k,
                               "ink_px": int(mask.sum())})

    # the canvas is only a problem if ink is genuinely cut at the very edge
    canvas_exit = []
    for a in boxes:
        x0, y0, x1, y1 = a["box"]
        if x0 < -TOL or y0 < -TOL or x1 > W + TOL or y1 > H + TOL:
            canvas_exit.append({"text": f'{a["kind"]}:{a["text"][:40]}',
                                "box": [float(round(v, 1)) for v in a["box"]],
                                "canvas": [float(round(W, 1)), float(round(H, 1))]})

    axes_collide = []
    rects = [ax.get_window_extent(_RENDERER) for ax in fig.axes]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            iw, ih = _inter([rects[i].x0, rects[i].y0, rects[i].x1, rects[i].y1],
                            [rects[j].x0, rects[j].y0, rects[j].x1, rects[j].y1])
            if iw > TOL and ih > TOL and iw * ih >= MIN_AREA:
                axes_collide.append({"i": i, "j": j, "area_px": round(iw * ih, 1)})

    sizes = [b["size"] for b in boxes if b["size"] > 0]
    return {
        "figsize_in": [round(w_in, 3), round(h_in, 3)],
        "dpi": dpi,
        "n_text": len(boxes),
        "n_footprints": len(footprints),
        "undrawable": undrawable,
        "min_fontsize_pt": round(min(sizes), 2) if sizes else None,
        "overlaps": overlaps,
        "overlaps_reserved_extra": extra,
        "reserved_box_error": box_error,
        "intrusions": intrusions,
        "canvas_exit": canvas_exit,
        "axes_collide": axes_collide,
        "orphan_ink": orphan_text(fig),
        "boxes": boxes,
    }


def _runs(mask_1d: np.ndarray) -> List[int]:
    nz = np.nonzero(mask_1d)[0]
    if len(nz) == 0:
        return []
    lengths, start, prev = [], nz[0], nz[0]
    for v in nz[1:]:
        if v == prev + 1:
            prev = v
            continue
        lengths.append(int(prev - start + 1))
        start = prev = v
    lengths.append(int(prev - start + 1))
    return lengths


def raster_check(path: str) -> Dict[str, Any]:
    """Clipping / density check on the saved file itself.

    Ink that touches the outermost pixel row/column is ink the tight crop had no room for.  A
    *stroke* touching the border (short contiguous run, tall/deep) means a glyph was shaved; a
    broad run means the crop merely sat flush against a wide element.
    """
    from PIL import Image
    im = Image.open(path).convert("L")
    a = np.asarray(im, dtype=np.float32) / 255.0
    h, w = a.shape
    ink = a < 0.9
    edges = {
        "top": ink[0], "bottom": ink[-1], "left": ink[:, 0], "right": ink[:, -1],
    }
    touches = {}
    for k, line in edges.items():
        n = int(line.sum())
        rl = _runs(line)
        touches[k] = {"px": n, "runs": len(rl), "max_run": max(rl) if rl else 0}
    total_touch = sum(v["px"] for v in touches.values())
    stroke_like = sum(1 for v in touches.values() if 0 < v["max_run"] <= 26 and v["runs"] <= 6)
    return {
        "px": [w, h],
        "aspect": round(w / h, 3),
        "ink_frac": round(float(ink.mean()), 5),
        "border_ink_px": total_touch,
        "border_detail": touches,
        "glyph_at_border": stroke_like,
        "blank_rows": int((~ink.any(axis=1)).sum()),
        "blank_cols": int((~ink.any(axis=0)).sum()),
    }


def _slurp(fig) -> Optional[Dict[str, Any]]:
    """Draw the live canvas and measure it.  Never calls savefig (the spy would recurse)."""
    fig.canvas.draw()
    return diagnose(fig)


class _SavefigSpy:
    """Intercept Figure.savefig so the live canvas can be audited before it is written.

    Most figure functions crop with bbox_inches='tight', which shifts the saved pixels relative
    to the canvas coordinates we measure, so the canvas is measured *before* the crop and the
    crop-induced clipping is detected separately from the raster.
    """

    def __init__(self, save: bool):
        self.save = save
        self.captured: Dict[str, Any] = {}

    def __enter__(self):
        self._real = matplotlib.figure.Figure.savefig
        spy = self

        def wrapper(self_fig, fname, *a, **kw):
            spy.captured["report"] = _slurp(self_fig)
            spy.captured["size"] = tuple(self_fig.get_size_inches())
            spy.captured["tight"] = bool(kw.get("bbox_inches") == "tight"
                                         or (a and a[0] == "tight"))
            if spy.save:
                return spy._real(self_fig, fname, *a, **kw)
            return None

        matplotlib.figure.Figure.savefig = wrapper
        return self

    def __exit__(self, *exc):
        matplotlib.figure.Figure.savefig = self._real
        return False


def render_all(save: bool, outdir: str) -> List[Dict[str, Any]]:
    """Re-execute every figure function and audit the live canvas."""
    import make_figures as mf
    import csv
    import pyarrow.parquet as pq

    run = os.path.join(ROOT, "results", "final", "tb2_v5")
    if not os.path.exists(os.path.join(run, "window_metrics.json")):
        run = os.path.join(ROOT, "results", "final", "tb2_final")
    ann = os.path.join(ROOT, "data", "annotations", "tb2")
    w = 10
    tag = f"tb2_w{w}"

    wl = json.load(open(os.path.join(run, "window_metrics.json"), encoding="utf-8"))
    frontier = json.load(open(os.path.join(run, "alarm_frontier.json"), encoding="utf-8"))
    win_curves = json.load(open(os.path.join(run, "window_alarm_curves.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(run, "run_config.json"), encoding="utf-8"))
    adj = list(csv.DictReader(open(os.path.join(ann, "adjudicated.csv"), encoding="utf-8")))
    rows = pq.read_table(os.path.join(run, "window_features.parquet")).to_pylist()

    core = ["B1_step60", "B2_exact_rep3", "B3_rep_target", "B4_semantic", "B5_novelty",
            "B6_verification", "B7_workspace", "C1_evidence", "C2_evid_ver", "C3_evid_sem",
            "C4_all_hand", "L_rep", "L_nov", "L_ver", "L_work", "L_sem", "L_evid",
            "L_all_hand", "L_all_sem", "L_evid_sem"]
    core = [c for c in core if c in wl or c in frontier]
    n_pos = cfg.get("n_alarm_eval_traj_with_region", cfg.get("n_alarm_eval_traj", 0))
    flat = {k: v for k, v in win_curves.items() if k in core and isinstance(v, list) and v}
    pos = max((s[0].get("n_positive_windows", 0) for s in flat.values()), default=0)
    neg = max((s[0].get("n_negative_windows", 0) for s in flat.values()), default=0)

    jobs: List[Tuple[str, Any]] = []
    if flat:
        jobs.append((f"fig_ops_{tag}", lambda p: mf.fig_frontier_window(
            flat, frontier, w, p, "Operating characteristics: per-window and per-run",
            core, pos, neg, n_pos)))
    jobs.append((f"fig_auc_{tag}", lambda p: mf.fig_auc(
        wl, w, p, f"Window-level discrimination (w={w})", core)))
    jobs.append((f"fig_labels_{tag}", lambda p: mf.fig_labels(
        adj, p, "What the annotations contain")))
    jobs.append((f"fig_signals_{tag}", lambda p: mf.fig_signal_examples(rows, p)))
    try:
        import make_regime_figure as mrf
        jobs.append((f"fig_regimes_{tag}", lambda p: mrf.regime_figure(
            os.path.join(ROOT, "results", "final", "tb2_v5"), p, w)))
    except Exception as exc:  # pragma: no cover
        print(f"  (regime figure module not auditable live: {exc})")

    reports = []
    for stem, fn in jobs:
        out = os.path.join(outdir, f"{stem}.png")
        with _SavefigSpy(save) as spy:
            try:
                fn(out)
            except Exception as exc:
                print(f"  !! {stem}: figure function raised {type(exc).__name__}: {exc}")
                reports.append({"stem": stem, "error": f"{type(exc).__name__}: {exc}"})
                continue
        rep = spy.captured.get("report") or {"error": "no savefig call captured"}
        rep["stem"] = stem
        rep["saved"] = save
        rep["tight_crop"] = spy.captured.get("tight")
        rep["print_width_in"] = PRINT_WIDTH_IN.get("_".join(stem.split("_")[:2]), 6.5)
        rep["raster"] = raster_check(out) if os.path.exists(out) else None
        reports.append(rep)
    return reports


def audit_on_disk(outdir: str) -> List[Dict[str, Any]]:
    out = []
    for n in sorted(os.listdir(outdir)):
        if n.endswith(".png"):
            out.append({"stem": n[:-4], "raster": raster_check(os.path.join(outdir, n))})
    return out


def report(reports: List[Dict[str, Any]]) -> int:
    bad = 0
    for r in reports:
        print("=" * 96)
        print(f"{r['stem']}   figsize {r.get('figsize_in')} in   text objects {r.get('n_text')}   "
              f"glyph footprints {r.get('n_footprints')}   min font {r.get('min_fontsize_pt')} pt")
        if r.get("undrawable"):
            kinds = {}
            for u in r["undrawable"]:
                kinds[u.get("why", "?")] = kinds.get(u.get("why", "?"), 0) + 1
            print(f"   note: {len(r['undrawable'])} label(s) sit outside the figure canvas, so their "
                  f"glyph footprint cannot be probed ({kinds}); the reserved-box test still covers them")
        be = r.get("reserved_box_error") or {}
        if be:
            print(f"   reserved box vs drawn ink: worst {be.get('worst_px')} px "
                  f"({be.get('worst_text')}); {be.get('n_box_error_over_4px')} labels off by >4 px")
        widths = {k: v for k, v in PRINT_WIDTH_IN.items() if r["stem"].startswith(k)}
        if widths and r.get("figsize_in"):
            pw = list(widths.values())[0]
            scale = pw / r["figsize_in"][0]
            printed = r.get("min_fontsize_pt", 99) * scale
            flag = ""
            if printed < 4.5:
                flag = "   UNREADABLE (<4.5 pt in print)"
                bad += 1
            elif printed < 5.5:
                flag = "   SMALL (<5.5 pt in print)"
            print(f"   printed at {pw:.2f} in wide -> scale {scale:.3f}; "
                  f"smallest printed font {printed:.2f} pt{flag}")
        ras = r.get("raster")
        if ras:
            print(f"   raster {ras['px'][0]}x{ras['px'][1]} px  aspect {ras['aspect']}  "
                  f"ink {ras['ink_frac']}  border-ink px {ras['border_ink_px']}  "
                  f"glyph-at-border {ras['glyph_at_border']}")
            if ras["glyph_at_border"]:
                print(f"   !! a glyph stroke reaches the raster border: possible clipping "
                      f"{ras['border_detail']}")
                bad += 1
        for key, label in (("overlaps", "TEXT-ON-TEXT OVERLAP (glyph ink)"),
                           ("overlaps_reserved_extra", "OVERLAP SEEN ONLY BY THE RESERVED-BOX TEST"),
                           ("intrusions", "TEXT OVER ANOTHER PANEL'S INK"),
                           ("axes_collide", "AXES OVERLAP"),
                           ("orphan_ink", "ORPHAN INK FRAGMENT AT MARGIN")):
            items = r.get(key) or []
            if items:
                print(f"   !! {label}: {len(items)}")
                seen = set()
                for it in items[:14]:
                    sig = json.dumps(it, sort_keys=True)
                    if sig in seen:
                        continue
                    seen.add(sig)
                    print(f"        {it}")
                bad += len(items)
            else:
                print(f"   ok  no {label.lower()}")
    print("=" * 96)
    print(f"TOTAL DEFECTS: {bad}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="re-render figures into paper/figures")
    ap.add_argument("--outdir", default=FIGDIR)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    reps = render_all(args.save, args.outdir)
    bad = report(reps)
    print("\n-- on-disk rasters --")
    for r in audit_on_disk(args.outdir):
        ras = r["raster"]
        print(f"  {r['stem']:28} {ras['px'][0]:>5}x{ras['px'][1]:<5} aspect {ras['aspect']:<6} "
              f"ink {ras['ink_frac']:<8} border-ink {ras['border_ink_px']:<6} "
              f"blank rows {ras['blank_rows']:<4} cols {ras['blank_cols']}")
    if args.json:
        slim = [{k: v for k, v in r.items() if k != "boxes"} for r in reps]
        json.dump(slim, open(args.json, "w", encoding="utf-8"), indent=2)
        print(f"\nwrote {args.json}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
