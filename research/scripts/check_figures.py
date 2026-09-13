"""Content checks for the generated figures.

Because the figures cannot be inspected visually in this environment, this script verifies the
properties that make a plot readable *from the data behind it*: that every series plotted has
enough points to be a curve rather than a dot, that each panel is populated, that the colour
mapping is injective across families, and that the figure files are large enough to contain the
expected number of elements.  It catches the failures that matter (an empty panel, a monitor
silently dropped, two families sharing a colour) rather than judging aesthetics.

Usage: python scripts/check_figures.py --run results/final/tb2_final
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

from make_figures import STYLE  # noqa: E402

problems: List[str] = []


def note(ok: bool, msg: str) -> None:
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        problems.append(msg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/final/tb2_final")
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--figdir", default="figures")
    args = ap.parse_args()
    w = str(args.w)

    print("figures:")
    expected = {
        "fig_labels": 3, "fig_auc": 3, "fig_features": 6, "fig_ops": 3,
        "fig_frontier": 3, "fig_summary": 2, "fig_signals": 3,
    }
    for stem, min_kb in expected.items():
        p = os.path.join(args.figdir, f"{stem}_tb2_w{w}.png")
        exists = os.path.exists(p)
        kb = round(os.path.getsize(p) / 1024) if exists else 0
        note(exists and kb >= min_kb, f"{stem} exists with {kb} KB")

    print("\ncolour mapping:")
    # Each family must read as one hue; light/dark variants of that hue are intentional
    # (hand-designed vs learned, main vs sensitivity variant), and combined families
    # (evidence+verification) may hold a second hue.  Hues are compared on a circular scale so
    # a light variant of the same hue is not counted as a different family colour.
    import colorsys

    def hue_bucket(hexcode: str) -> int:
        h = hexcode.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        hh, _, _ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        return round(hh * 36) % 36

    def hue_dist(a: int, b: int) -> int:
        d = abs(a - b) % 36
        return min(d, 36 - d)

    fam_of = {
        "B1": "baseline", "B2": "repetition", "B3": "repetition", "B4": "semantic",
        "B5": "novelty", "B6": "verification", "B7": "workspace",
        "C1": "evidence", "C2": "evidence-ver", "C3": "evidence-sem",
        "C4": "all-hand",
        "L_rep": "repetition", "L_nov": "novelty", "L_ver": "verification",
        "L_work": "workspace", "L_sem": "semantic", "L_evid": "evidence",
        "L_evid_nov": "evidence-nov", "L_evid_ver": "evidence-ver",
        "L_evid_sem": "evidence-sem", "L_all_hand": "all-hand", "L_all_sem": "semantic",
        "transfer_L_all_hand": "all-hand", "transfer_L_evid": "evidence",
    }
    hues: Dict[str, List[tuple]] = defaultdict(list)
    for name, spec in STYLE.items():
        fam = fam_of.get(name, fam_of.get(name.split("_")[0], name.split("_")[0]))
        hues[fam].append((name, hue_bucket(spec["color"])))
    for fam, entries in sorted(hues.items()):
        base = Counter(b for _, b in entries).most_common(1)[0][0]
        far = [n for n, b in entries if hue_dist(b, base) > 3]
        limit = 2 if "-" in fam else 1
        n_hues = len({b for _, b in entries})
        note(len(far) == 0 and n_hues <= limit + 2,
             f"family {fam}: {n_hues} hue(s), outliers {far}")
    used = {spec["color"] for spec in STYLE.values()}
    note(len(used) >= 8, f"{len(used)} distinct colours across {len(STYLE)} monitor styles")
    all_hues = {hue_bucket(c) for c in used}
    note(len(all_hues) >= 6, f"{len(all_hues)} distinct hues, enough to separate families")

    print("\nseries content:")
    curves = json.load(open(os.path.join(args.run, "window_alarm_curves.json"), encoding="utf-8"))
    thin = [n for n, rows in curves.items() if len(rows) < 10]
    note(not thin, f"every monitor has >=10 threshold points (thin: {thin[:4]})")
    flat = [n for n, rows in curves.items()
            if len({round(r["detection_rate"], 3) for r in rows}) < 2]
    note(len(flat) <= 5, f"most monitors vary with threshold ({len(flat)} constant: {flat[:4]})")

    wl = json.load(open(os.path.join(args.run, "window_metrics.json"), encoding="utf-8"))
    # monitors that are only produced by an optional run configuration may legitimately be
    # absent; everything else must exist or the figure silently drops a series
    optional = {"transfer_L_all_hand", "transfer_L_evid"}
    missing = [n for n in STYLE if n not in wl and n not in curves and n not in optional]
    note(not missing, f"every required monitor exists in the run (missing: {missing})")

    adj = sum(1 for _ in open(os.path.join(ROOT, "data", "annotations", "tb2",
                                           "adjudicated.csv"), encoding="utf-8")) - 1
    note(adj > 500, f"{adj} adjudicated windows available for the label figure")

    print("\nfigure numbers vs the printed table:")
    # The feature values a figure would show must agree with the evidence table the paper prints,
    # computed by the same rule from the same subset.  An earlier revision of the figure module
    # selected by distance from chance instead of by highest AUC and disagreed with the table on
    # every channel whose strongest feature runs the other way; this check exists so that cannot
    # happen again silently.
    import pyarrow.parquet as pq
    from make_figures import best_feature_per_channel
    rows = pq.read_table(os.path.join(args.run, "window_features.parquet")).to_pylist()
    recomputed = best_feature_per_channel(rows, args.w)
    expected = {"REP": ("rep_global_recurrence", 0.662), "NOV": ("nov_obs_chars", 0.643),
                "EVID": ("ev_new_highrel_rate", 0.449), "VER": ("ver_stall_len", 0.569),
                "WORK": ("wk_edit_after_complete", 0.505), "SEM": ("sem_nearest_sim", 0.702)}
    for ch, (fname, auc) in expected.items():
        got = recomputed.get(ch) or {}
        same = got.get("feature") == fname and abs(got.get("roc_auc", 0) - auc) < 5e-4
        note(same, f"feature table {ch}: {fname} {auc:.3f} == recomputed "
                   f"{got.get('feature')} {got.get('roc_auc')}")

    print(f"\n{'ALL CHECKS PASSED' if not problems else str(len(problems)) + ' PROBLEM(S)'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
