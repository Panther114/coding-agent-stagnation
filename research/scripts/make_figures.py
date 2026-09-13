"""Figures for the paper.

Reads only frozen artifacts from a run directory, so every figure is reproducible without
re-running experiments.  The design goal is a reader who is skimming: each figure answers one
question, uses one colour per signal family, labels the quantities directly, and keeps the
annotation honest (baselines thin and grey, the proposed monitor saturated).

Layout contract (enforced independently by scripts/audit_figure_text.py, which does not reuse this
file's assumptions):

  * every figure is drawn at, or very near, the width at which the paper prints it, so the font
    sizes declared here are the font sizes the reader sees;
  * no legend is placed below the axes, because that is what put legend rows on top of the
    x-tick labels in the previous revision;
  * no in-axes label is longer than its panel is wide, because text does not clip to the axes it
    belongs to and spills into its neighbour;
  * axis labels stay short enough to survive the print scale without falling under 5 pt.

Usage:
  python scripts/make_figures.py --run results/final/tb2_final --corpus tb2
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402

import paths  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

TEXT_WIDTH_IN = 6.5          # geometry: 1in margins on letter paper
DPI = 400                    # figures print at 6.5in wide, so 400dpi keeps them crisp in print

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": DPI, "font.size": 8.5, "axes.labelsize": 8.5,
    "axes.titlesize": 9.0, "legend.fontsize": 7.0, "xtick.labelsize": 7.6,
    "ytick.labelsize": 7.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.alpha": 0.22, "grid.linewidth": 0.5, "font.family": "DejaVu Sans",
    "axes.axisbelow": True, "figure.facecolor": "white",
    "axes.linewidth": 0.8, "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "xtick.major.size": 3.0, "ytick.major.size": 3.0,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.04,
})

STYLE: Dict[str, Dict[str, Any]] = {
    "B1_step30":     dict(color="#9aa0a6", ls=(0, (1, 1.6)), lw=1.1, label="step budget 30"),
    "B1_step60":     dict(color="#9aa0a6", ls=(0, (1, 1.6)), lw=1.1, label="step budget 60"),
    "B2_exact_rep3": dict(color="#b3651a", ls=(0, (4, 1.6)), lw=1.2, label="exact repetition"),
    "B2_exact_rep5": dict(color="#b3651a", ls=(0, (4, 1.6)), lw=1.2, label="exact repetition (k=5)"),
    "B3_rep_target": dict(color="#c98a4b", ls=(0, (4, 1.6)), lw=1.2, label="target repetition"),
    # indigo marks the family that wins: it must read as prominent rather than recede
    "B4_semantic":   dict(color="#3b4cc0", ls="-", lw=2.0, label="semantic redundancy"),
    "B4_sem_diversity": dict(color="#7a86d8", ls=(0, (5, 2)), lw=1.2,
                             label="rolling diversity only"),
    "B5_novelty":    dict(color="#7a4fbf", ls="-", lw=1.4, label="novelty (relevance-blind)"),
    "B5_novelty_sig": dict(color="#a98fd6", ls=(0, (5, 2)), lw=1.2, label="distinct actions"),
    "B6_verification": dict(color="#2e7d32", ls="-", lw=1.5, label="verification deltas"),
    "B6_ver_stall":  dict(color="#7cb342", ls=(0, (5, 2)), lw=1.2, label="time since improvement"),
    "B7_workspace":  dict(color="#a01a4a", ls="-", lw=1.4, label="workspace churn"),
    "C1_evidence":   dict(color="#1f6fd0", ls="-", lw=1.7, label="task-grounded evidence"),
    "C1_evidence_rel": dict(color="#1f6fd0", ls=(0, (5, 2)), lw=1.2,
                            label="evidence (relevant only)"),
    "C2_evid_ver":   dict(color="#0f8b8d", ls="-", lw=1.6, label="evidence + verification"),
    "C2_evid_ver_work": dict(color="#6fc0c2", ls=(0, (5, 2)), lw=1.2,
                             label="evidence + verification + edits"),
    "C3_evid_sem":   dict(color="#8854d0", ls="-", lw=1.6, label="evidence + semantic"),
    "C4_all_hand":   dict(color="#4a4a4a", ls="-", lw=1.4, label="all hand-designed"),
    "L_evid":        dict(color="#1f6fd0", ls=(0, (2, 1.4)), lw=1.5, label="evidence (learned)"),
    "L_all_hand":    dict(color="#4a4a4a", ls=(0, (2, 1.4)), lw=1.5, label="all hand (learned)"),
    "L_all_sem":     dict(color="#3b4cc0", ls=(0, (1, 1.4)), lw=1.5,
                          label="all + semantic (learned)"),
    "L_evid_sem":    dict(color="#8854d0", ls=(0, (2, 1.4)), lw=1.6,
                          label="evidence + semantic (learned)"),
    "L_rep":         dict(color="#b3651a", ls=(0, (2, 1.4)), lw=1.3, label="repetition (learned)"),
    "L_nov":         dict(color="#7a4fbf", ls=(0, (2, 1.4)), lw=1.3, label="novelty (learned)"),
    "L_ver":         dict(color="#2e7d32", ls=(0, (2, 1.4)), lw=1.3, label="verification (learned)"),
    "L_work":        dict(color="#a01a4a", ls=(0, (2, 1.4)), lw=1.3, label="workspace (learned)"),
    "L_sem":         dict(color="#3b4cc0", ls=(0, (2, 1.4)), lw=1.8, label="semantic (learned)"),
    "L_evid_nov":    dict(color="#5b7fbf", ls=(0, (2, 1.4)), lw=1.3,
                          label="evidence + novelty (learned)"),
    "L_evid_ver":    dict(color="#0f8b8d", ls=(0, (2, 1.4)), lw=1.3,
                          label="evidence + verification (learned)"),
    "transfer_L_all_hand": dict(color="#4a4a4a", ls=(0, (1, 1.2)), lw=1.3,
                                label="all hand (transferred)"),
    "transfer_L_evid": dict(color="#1f6fd0", ls=(0, (1, 1.2)), lw=1.3,
                            label="evidence (transferred)"),
}

# Row labels are written compactly because they are drawn to the left of their own axes and text
# does not clip to the axes it belongs to; the full name is used in the legends and the tables.
SHORT: Dict[str, str] = {
    "B1_step30": "step budget 30",
    "B1_step60": "step budget 60",
    "B2_exact_rep3": "exact repetition",
    "B2_exact_rep5": "exact repetition k=5",
    "B3_rep_target": "target repetition",
    "B4_semantic": "semantic redundancy",
    "B4_sem_diversity": "rolling diversity",
    "B5_novelty": "novelty (blind)",
    "B6_verification": "verification deltas",
    "B6_ver_stall": "time since improve",
    "B7_workspace": "workspace churn",
    "C1_evidence": "task-grounded evid.",
    "C2_evid_ver": "evid. + verif.",
    "C3_evid_sem": "evid. + semantic",
    "C4_all_hand": "all hand-designed",
    "L_sem": "semantic (learned)",
    "L_evid_sem": "evid.+sem. (learned)",
    "L_all_sem": "all+sem. (learned)",
    "L_all_hand": "all hand (learned)",
    "L_evid": "evidence (learned)",
    "L_evid_ver": "evid.+verif. (learned)",
    "L_evid_nov": "evid.+nov. (learned)",
    "L_rep": "repetition (learned)",
    "L_nov": "novelty (learned)",
    "L_ver": "verification (learned)",
    "L_work": "workspace (learned)",
}


def st(name: str) -> Dict[str, Any]:
    return STYLE.get(name, dict(color="#222222", ls="-", lw=1.2, label=name))


def row_label(name: str) -> str:
    return SHORT.get(name, st(name)["label"])


def fam_color(name: str) -> str:
    return st(name)["color"]


# The figure set is curated: the tables carry the full zoo, the figures carry the comparison.
# Twenty series produced legends that covered the tick labels and three-word-wide panels.
PLOT_ORDER: List[str] = [
    "B1_step60", "B2_exact_rep3", "B4_semantic", "B4_sem_diversity", "B5_novelty",
    "B6_verification", "B7_workspace", "C1_evidence", "C2_evid_ver", "C3_evid_sem",
    "L_sem", "L_evid_sem",
]


def _put_legend(fig, names: Sequence[str], ncol: int, y: float, fontsize: float = 6.8) -> None:
    """Legend inside the canvas, above the axes — never below them.

    A legend anchored below the axes occupies the same strip as the x-tick labels and the axis
    label, which is exactly how the previous revision came to have legend text printed over
    numeral ticks.  Placing it in the top margin costs nothing and cannot collide.
    """
    handles, seen = [], set()
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        handles.append(Line2D([], [], **st(n)))
    fig.legend(handles=handles, loc="lower center", ncol=ncol, frameon=False,
               bbox_to_anchor=(0.5, y), fontsize=fontsize, handlelength=1.8,
               columnspacing=1.0, handletextpad=0.5, borderaxespad=0.0)


# --------------------------------------------------------------------------------------
# operational figures
# --------------------------------------------------------------------------------------

def fig_frontier_window(curves: Dict[str, Any], frontier: Dict[str, Any], w: int, out: str,
                        title: str, order: Sequence[str], n_pos: int, n_neg: int,
                        n_runs: int) -> None:
    """Operating characteristics: per-window cost of a stricter threshold, and the per-run view.

    The right panel is the per-run view (first alarm only), folded in here rather than drawn as a
    separate figure: as its own float it carried one short curve per monitor and cost most of a
    page. The middle panel plots the firing rate against the threshold rather than coverage against
    the false-stop rate, because the latter needs a y-label long enough to collide with the
    neighbouring panel.
    """
    fig, axes = plt.subplots(1, 3, figsize=(TEXT_WIDTH_IN * 1.108, 2.3),
                             gridspec_kw={"wspace": 0.44})
    for name in order:
        rows = curves.get(name, [])
        if not rows:
            continue
        rows = sorted(rows, key=lambda r: r["threshold"])
        keep = [r for r in rows if r["false_stop_rate"] == r["false_stop_rate"]]
        if not keep:
            continue
        s = st(name)
        axes[0].plot([r["false_stop_rate"] for r in keep],
                     [r["detection_rate"] for r in keep], **s)
        axes[1].plot([r["threshold"] for r in keep],
                     [r["false_stop_rate"] for r in keep], **s)
        per = frontier.get(name, {})
        frows = per.get(str(w)) or per.get(w) or []
        pts = [(r["false_stop_rate"], r["detection_rate"]) for r in frows
               if r.get("false_stop_rate") == r.get("false_stop_rate")
               and r.get("detection_rate") == r.get("detection_rate")]
        if pts:
            pts.sort()
            axes[2].plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=2.4,
                         markeredgewidth=0, **s)
    for ax in axes:
        ax.axhline(0, color="#cfcfcf", lw=0.7)
        ax.axvspan(0, 0.05, color="#3b4cc0", alpha=0.13, lw=0)
    axes[0].set_xlabel("false-stop rate")
    axes[0].set_ylabel("stagnant windows detected")
    axes[1].set_xlabel("score threshold")
    axes[1].set_ylabel("false-stop rate")
    axes[2].set_xlabel("false-stop rate")
    axes[2].set_ylabel("stagnating runs caught")
    axes[0].set_xlim(-0.01, 0.35)
    axes[1].set_xlim(0.28, 1.02)
    axes[2].set_xlim(-0.01, 0.35)
    axes[0].set_ylim(-0.02, 0.68)
    axes[1].set_ylim(-0.02, 0.32)
    axes[2].set_ylim(-0.02, 0.42)
    # Explicit locators keep matplotlib from labelling ticks outside the view limits, which is what
    # printed a '0.35' tick on top of a panel title and put a '1.2' numeral beside the neighbouring
    # panel's '−0.1'.  The *number* of ticks is capped too: at this print width, five labels across a
    # 0.20-wide axis leave their numerals touching, which the ink probe reports as a collision.
    axes[0].set_yticks([0.0, 0.2, 0.4, 0.6])
    axes[0].set_xticks([0.0, 0.1, 0.2, 0.3])
    axes[1].set_yticks([0.0, 0.1, 0.2, 0.3])
    axes[1].set_xticks([0.4, 0.6, 0.8, 1.0])
    axes[2].set_yticks([0.0, 0.1, 0.2, 0.3, 0.4])
    axes[2].set_xticks([0.0, 0.1, 0.2, 0.3])
    # Label the shaded band at the top of the axes, where nothing is plotted, and give the text a
    # solid background: at the bottom it sat on the curves.
    axes[0].text(0.5 * 0.05 / 0.36, 0.97, "5% budget", transform=axes[0].transAxes,
                 fontsize=6.2, color="#3d5c8c", va="top", ha="center",
                 bbox=dict(facecolor="white", edgecolor="none", pad=1.4, alpha=0.85))
    axes[0].set_title("detection vs risk")
    axes[1].set_title("cost vs threshold")
    axes[2].set_title("per-run view")
    # The legend goes in the top margin and the caption does *not*: a suptitle at the same height
    # as the legend is printed straight through it (this figure had the legend text and the caption
    # overprinted, the caption unreadable).  The panel titles carry the caption's content instead.
    _put_legend(fig, order, ncol=4, y=1.02, fontsize=7.0)
    fig.savefig(out)
    plt.close(fig)


# --------------------------------------------------------------------------------------
# window-level discrimination
# --------------------------------------------------------------------------------------

def fig_auc(wl: Dict[str, Any], w: int, out: str, title: str, order: Sequence[str]) -> None:
    """One ordered list of monitors, ROC-AUC and best F1 as two metrics.

    A two-block layout needs a gap wide enough for the second block's row labels *and* three
    metric panels per block; at 6.5in that leaves each panel about 1.2in, and the rows of the
    second block then reach into the bars of the first.  A single ordered list removes the
    question.  Rows are the monitors the text discusses; the full zoo is in the tables.
    """
    rows = []
    for name in order:
        per = wl.get(name, {})
        m = per.get(str(w)) or per.get(w)
        if m and m["roc_auc"] == m["roc_auc"]:
            rows.append((name, m["roc_auc"], m["pr_auc"], m["prev"], m["n"], m["f1_best"]))
    if not rows:
        return
    rows.sort(key=lambda r: r[1], reverse=True)

    fig = plt.figure(figsize=(TEXT_WIDTH_IN, 0.215 * len(rows) + 0.95))
    gs = fig.add_gridspec(1, 2, wspace=0.16, width_ratios=[3.1, 1.0])
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]
    y = np.arange(len(rows))
    cols = [fam_color(r[0]) for r in rows]
    vals = [[r[1] for r in rows], [r[5] for r in rows]]
    refs = [0.5, 0.0]
    labels = ["ROC-AUC   (0.50 = chance)", "best F1"]
    # The list is sorted by ROC-AUC, so both the top and the bottom rows have a bar reaching into
    # each corner; an in-axes legend is therefore printed across a bar whichever corner it takes.
    # The key for the two reference lines goes under the axis instead, where nothing is plotted.
    lims = [(0.40, 0.80), (0.0, 0.65)]
    prev = rows[0][3]
    for k, ax in enumerate(axes):
        ax.barh(y, vals[k], color=cols, height=0.66)
        ax.axvline(refs[k], color="#9a9a9a", lw=0.8,
                   ls=(0, (3, 2)) if k == 0 else (0, (1, 1.6)))
        ax.set_xlim(*lims[k])
        ax.set_ylim(-0.7, len(rows) - 0.3)
        ax.tick_params(labelsize=6.6, length=0)
        ax.set_xlabel(labels[k], fontsize=7.2)
        ax.set_yticks(y)
    axes[0].set_xticks([0.4, 0.5, 0.6, 0.7, 0.8])
    axes[1].set_xticks([0.0, 0.2, 0.4, 0.6])
    axes[1].set_yticklabels([])
    axes[0].set_yticklabels([row_label(r[0]) for r in rows], fontsize=6.8)
    # A figure-level legend in the margin under the left panel's x-label, where no bar reaches.
    axes[0].legend(handles=[
        Line2D([], [], color="#9a9a9a", lw=0.8, ls=(0, (3, 2)), label="chance (0.50)"),
        Line2D([], [], color="#9a9a9a", lw=0.8, ls=(0, (1, 1.6)),
               label=f"positive prevalence ({prev:.2f})"),
    ], loc="upper left", bbox_to_anchor=(0.0, -0.115), frameon=False, fontsize=6.6,
        handlelength=1.8, ncol=2, columnspacing=1.6, handletextpad=0.5, borderaxespad=0.0)
    fig.suptitle(title, fontsize=8.8, y=1.0)
    fig.savefig(out)
    plt.close(fig)


def best_feature_per_channel(rows: Sequence[Dict[str, Any]], w: int = 10) -> Dict[str, Any]:
    """Strongest single feature per channel, by the same rule the evidence table uses.

    The rule matters and is easy to get subtly wrong.  The exported table picks, per channel, the
    feature with the *highest* window ROC-AUC on the annotated windows at $w=10$ — which is not the
    same thing as the feature farthest from 0.5, because several channels contain features whose
    strongest association with stagnation is negative (their AUC is far below 0.5).  An earlier
    revision of this module selected by distance from chance, so the feature panel and the table
    disagreed: novelty came out as 0.28 in the panel and 0.64 in the table.  Both numbers are real,
    they just answer different questions, and a paper may only contain one of them.

    Returns the selected feature and AUC per channel, so the caller can check them against the table
    the paper actually prints.
    """
    from evaluation import window_metrics  # local import (src on path)
    from features import FEATURE_CHANNEL

    sub = [r for r in rows if r["binary"] is not None and r.get("w") == w]
    y = np.array([r["binary"] for r in sub])
    if len(set(y.tolist())) < 2:
        return {}
    feat_auc: Dict[str, Tuple[float, str]] = {}
    for f, ch in FEATURE_CHANNEL.items():
        x = np.array([r.get(f, np.nan) for r in sub], dtype=float)
        if np.all(np.isnan(x)) or np.nanstd(x) == 0:
            continue
        auc = window_metrics(y, np.nan_to_num(x, nan=float(np.nanmean(x))))["roc_auc"]
        if auc == auc:
            feat_auc[f] = (auc, ch)
    out: Dict[str, Any] = {}
    for ch in ("REP", "NOV", "EVID", "VER", "WORK", "SEM"):
        cands = [(f, v[0]) for f, v in feat_auc.items() if v[1] == ch]
        if not cands:
            continue
        f, auc = max(cands, key=lambda t: t[1])
        out[ch] = {"feature": f, "roc_auc": round(auc, 3)}
    return out


def _wrap(s: str, width: int) -> str:
    out, line = [], ""
    for word in s.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = word if not line else line + " " + word
    if line:
        out.append(line)
    return "\n".join(out)


def fig_labels(adj: Sequence[Dict[str, str]], out: str, title: str) -> Dict[str, Any]:
    """Label distribution, per-scaffold positive rate, and stagnation subtype.

    Every panel is horizontal so its category names can be printed in full: rotated and abbreviated
    vertical labels were overlapping each other in the previous revision.
    """
    lab = Counter(a["gold"] for a in adj)
    by_agent: Dict[str, Counter] = defaultdict(Counter)
    for a in adj:
        if a["binary"] in {"0", "1"}:
            by_agent[a["agent"]]["POS" if a["binary"] == "1" else "NEG"] += 1
    details = Counter(a["detail"] for a in adj if a["detail"])
    agents = sorted(by_agent, key=lambda k: (by_agent[k]["POS"] + by_agent[k]["NEG"]),
                    reverse=True)[:10]
    agents = agents[::-1]

    fig, axes = plt.subplots(1, 3, figsize=(TEXT_WIDTH_IN, 3.0),
                             gridspec_kw={"wspace": 0.98, "width_ratios": [0.90, 1.0, 1.35]})

    order = [("PRODUCTIVE", "#3f7d3c"), ("STAGNANT", "#b03030"), ("DONE_REDUNDANT", "#d08a3a"),
             ("REGRESSION", "#7a4fbf"), ("BLOCKED_EXTERNAL", "#8a8f98"), ("UNCERTAIN", "#c9c9c9")]
    names = [k for k, _ in order]
    vals = [lab.get(k, 0) for k, _ in order]
    ypos = np.arange(len(order))
    axes[0].barh(ypos, vals, color=[c for _, c in order], height=0.66)
    top = max(vals) if vals else 1
    for i, v in enumerate(vals):
        axes[0].text(v + top * 0.03, i, str(v), va="center", fontsize=7.0)
    axes[0].set_yticks(ypos)
    # Title-case so the label set reads the same way here as it does in the text
    axes[0].set_yticklabels([k.replace("_", " ").title() for k in names], fontsize=7.2)
    axes[0].set_xlim(0, top * 1.28)
    axes[0].set_xlabel("annotated windows")
    axes[0].set_title("labels")

    y = np.arange(len(agents))
    neg = [by_agent[a]["NEG"] for a in agents]
    pos = [by_agent[a]["POS"] for a in agents]
    axes[1].barh(y, neg, color="#3f7d3c", height=0.64, label="productive")
    axes[1].barh(y, pos, left=neg, color="#b03030", height=0.64, label="stagnant")
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([_wrap(a.replace("_", " "), 13) for a in agents], fontsize=6.8)
    axes[1].set_xlim(0, max((n + p) for n, p in zip(neg, pos)) * 1.06)
    axes[1].set_xlabel("annotated windows")
    axes[1].set_title("by scaffold")
    axes[1].set_xlim(0, max((n + p) for n, p in zip(neg, pos)) * 1.06)
    # A figure-level legend in the bottom margin: the panel's own top-right corner is where its
    # longest bar ends, so an in-axes legend lands on a coloured bar whichever corner it takes, and
    # the top margin is occupied by the suptitle and the panel titles.
    axes[1].legend(frameon=False, fontsize=7.0, loc="upper center", ncol=2,
                   bbox_to_anchor=(0.5, -0.135), handlelength=1.4, columnspacing=1.6,
                   handletextpad=0.5)

    det = details.most_common(6)
    yy = np.arange(len(det))
    axes[2].barh(yy, [d[1] for d in det], color="#b03030", height=0.64)
    axes[2].set_yticks(yy)
    axes[2].set_yticklabels([_wrap(d[0].replace("_", " "), 18) for d in det], fontsize=6.8)
    axes[2].set_xlim(0, max(d[1] for d in det) * 1.10)
    axes[2].set_xlabel("stagnant windows")
    axes[2].set_title("why it stagnated")
    for ax in axes:
        ax.tick_params(length=0)
    fig.suptitle(title, fontsize=8.8, y=1.0)
    fig.savefig(out)
    plt.close(fig)
    return {"labels": dict(lab), "by_agent": {k: dict(v) for k, v in by_agent.items()},
            "subtypes": dict(details)}


def fig_signal_examples(rows: Sequence[Dict[str, Any]], out: str,
                        max_traj: int = 2) -> List[str]:
    """Per-step channels on illustrative trajectories.

    Trajectories are chosen for contrast, not availability: we score each candidate by how many
    labelled windows it has, how balanced the two classes are, and how far apart the two classes
    sit in the run (a trajectory with a productive opening and a stagnant ending shows the pattern
    far better than one that is uniform).

    The panels are stacked with a generous gap and each x-label sits inside its own axes, because a
    label placed below one axes lands on the shrunken axes beneath it.
    """
    by_traj: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_traj[r["traj_id"]].append(r)

    def score(tid: str) -> float:
        rs = by_traj[tid]
        labelled = [r for r in rs if r["binary"] is not None]
        pos = [r["t"] for r in labelled if r["binary"] == 1]
        neg = [r["t"] for r in labelled if r["binary"] == 0]
        if not pos or not neg:
            return -1.0
        balance = min(len(pos), len(neg)) / max(len(pos), len(neg))
        separation = abs(sum(pos) / len(pos) - sum(neg) / len(neg)) / max(
            1, max(r["n_steps"] for r in rs))
        return len(labelled) + 6.0 * balance + 12.0 * separation

    chosen = sorted((t for t in by_traj if score(t) > 0), key=score, reverse=True)[:max_traj]
    fig, axes = plt.subplots(len(chosen), 1, figsize=(TEXT_WIDTH_IN, 1.10 * len(chosen)),
                             gridspec_kw={"hspace": 0.80})
    if len(chosen) == 1:
        axes = [axes]
    for ax, tid in zip(axes, chosen):
        rs = sorted(by_traj[tid], key=lambda r: r["t"])
        ts = [r["t"] for r in rs]
        w = rs[0]["w"]
        ev = [r.get("ev_new_relevant_rate", np.nan) for r in rs]
        rep = [r.get("rep_exact_frac", np.nan) for r in rs]
        ver = [1.0 if (r.get("ver_has_improvement", 0.0) or 0) > 0 else 0.0 for r in rs]
        # Both channel series are drawn step-wise.  Drawn as straight segments, a feature that
        # alternates between two values every window becomes a dense sawtooth that reads as noise;
        # as steps it reads as the discrete quantity it is.
        ax.step(ts, ev, where="mid", color="#1f5fbf", lw=1.1, label="relevant evidence rate")
        ax.step(ts, rep, where="mid", color="#b3651a", lw=1.0, ls=(0, (4, 1.6)),
                label="exact repetition")
        ax.step(ts, [0.03 + 0.07 * v for v in ver], where="mid", color="#3f7d3c", lw=1.5,
                label="verification improved")
        labelled = [r for r in rs if r["binary"] is not None]
        runs, cur = [], None
        for r in labelled:
            lab = int(r["binary"])
            if cur and lab == cur["label"]:
                cur["end"] = r["t"]
            else:
                if cur:
                    runs.append(cur)
                cur = {"label": lab, "start": r["t"], "end": r["t"]}
        if cur:
            runs.append(cur)
        # Stagnant windows are marked with a neutral hatched band and productive windows with a
        # faint green one.  Two translucent fills in complementary colours turned every overlap
        # into an unreadable brown blot; the hatch distinguishes them without relying on colour.
        for run in runs:
            if run["label"] == 1:
                ax.axvspan(run["start"] - w + 1, run["end"], facecolor="#8a8f98", alpha=0.34,
                           edgecolor="#6d7278", hatch="///", lw=0.0, zorder=0)
            else:
                ax.axvspan(run["start"] - w + 1, run["end"], facecolor="#3f7d3c", alpha=0.10,
                           lw=0, zorder=0)
        ax.set_title(f"{tid.split('__')[0]}  ·  {rs[0]['agent']}  ·  final reward "
                     f"{rs[0]['reward']}", fontsize=7.2, loc="left")
        ax.set_ylim(-0.05, 1.18)
        ax.set_xlim(min(ts), max(ts))
        ax.set_yticks([0.0, 0.5, 1.0])
        ax.text(0.995, 0.06, "agent step", transform=ax.transAxes, fontsize=6.6,
                color="#555555", ha="right", va="bottom")
        if ax is axes[0]:
            ax.legend(frameon=True, framealpha=0.9, edgecolor="none", fontsize=6.8,
                      ncol=3, loc="upper left", handlelength=1.6, columnspacing=1.0,
                      borderpad=0.3)
    handles = [Patch(facecolor="#8a8f98", alpha=0.34, hatch="///", edgecolor="#6d7278",
                     label="annotated stagnant region"),
               Patch(facecolor="#3f7d3c", alpha=0.12, label="annotated productive region")]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.0), fontsize=7.2)
    fig.savefig(out)
    plt.close(fig)
    return chosen


# --------------------------------------------------------------------------------------
# per-run summary
# --------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--ann", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--w", type=int, default=10)
    args = ap.parse_args()
    outdir = args.outdir or paths.FIGURES
    os.makedirs(outdir, exist_ok=True)
    tag = f"{args.corpus}_w{args.w}"
    ann = args.ann or os.path.join(paths.DATA, "annotations", args.corpus)

    wl = json.load(open(os.path.join(args.run, "window_metrics.json"), encoding="utf-8"))
    frontier = json.load(open(os.path.join(args.run, "alarm_frontier.json"), encoding="utf-8"))
    win_curves = json.load(open(os.path.join(args.run, "window_alarm_curves.json"),
                                encoding="utf-8"))
    cfg = json.load(open(os.path.join(args.run, "run_config.json"), encoding="utf-8"))
    adj = list(csv.DictReader(open(os.path.join(ann, "adjudicated.csv"), encoding="utf-8")))
    import pyarrow.parquet as pq
    rows = pq.read_table(os.path.join(args.run, "window_features.parquet")).to_pylist()

    order = [c for c in PLOT_ORDER if c in wl or c in frontier or c in win_curves]
    n_runs = cfg.get("n_alarm_eval_traj_with_region", cfg.get("n_alarm_eval_traj", 0))

    # exactly the five figures the paper includes.  Three more were drawn by earlier revisions
    # (a per-run frontier, a per-run summary and a per-channel feature panel); each was folded into
    # another figure, dropped as duplicated by a table, or replaced by the evidence table, and the
    # paper's figure list is kept in step with what is generated here.
    flat: Dict[str, Any] = {n: win_curves[n] for n in order
                            if isinstance(win_curves.get(n), list) and win_curves[n]}
    if flat:
        pos = max((s[0].get("n_positive_windows", 0) for s in flat.values()), default=0)
        neg = max((s[0].get("n_negative_windows", 0) for s in flat.values()), default=0)
        fig_frontier_window(flat, frontier, args.w, os.path.join(outdir, f"fig_ops_{tag}.png"),
                            "Operating characteristics: per-window and per-run",
                            order, pos, neg, n_runs)
    fig_auc(wl, args.w, os.path.join(outdir, f"fig_auc_{tag}.png"),
            f"Window-level discrimination (w={args.w}, held-out tasks)", order)
    stats = fig_labels(adj, os.path.join(outdir, f"fig_labels_{tag}.png"),
                       "What the annotations contain")
    chosen = fig_signal_examples(rows, os.path.join(outdir, f"fig_signals_{tag}.png"))
    feats = best_feature_per_channel(rows, args.w)
    with open(os.path.join(args.run, "figure_notes.json"), "w", encoding="utf-8") as fh:
        json.dump({"label_stats": stats, "signal_example_trajectories": chosen,
                   "best_feature_per_channel": feats}, fh, indent=2)
    print(f"figures -> {outdir} (tag {tag}); signal examples: {chosen}")
    expected = {"REP": ("rep_global_recurrence", 0.662), "NOV": ("nov_obs_chars", 0.643),
                "EVID": ("ev_new_highrel_rate", 0.449), "VER": ("ver_stall_len", 0.569),
                "WORK": ("wk_edit_after_complete", 0.505), "SEM": ("sem_nearest_sim", 0.702)}
    print("strongest feature per channel (recomputed here, compared with the paper's evidence table):")
    mismatch = 0
    for ch, want in expected.items():
        got = feats.get(ch)
        if not got:
            print(f"  {ch:5} not computed")
            mismatch += 1
            continue
        same = got["feature"] == want[0] and abs(got["roc_auc"] - want[1]) < 5e-4
        mismatch += 0 if same else 1
        print(f"  {ch:5} table {want[0]} {want[1]:.3f}   recomputed {got['feature']} "
              f"{got['roc_auc']:.3f}   {'match' if same else 'DIFFERENT'}")
    if mismatch:
        print(f"  !! {mismatch} channel(s) disagree with the printed evidence table")
    print(json.dumps(stats["labels"], indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
