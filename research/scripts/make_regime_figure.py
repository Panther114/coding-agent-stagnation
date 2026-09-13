"""Figure for the regime-level headline result.

Left   : every stagnant episode's mean score against its own run's productive-region mean, paired.
         Points above the diagonal are episodes the monitor separates from their own run's
         productive work. This is a within-run comparison by construction, so it cannot be won by
         recognising the run.
Centre : the same comparison restricted to episodes matched in run position, with the position
         proxy shown alongside, which is what rules out "stalls just happen later in runs".
Right  : episode length distribution, showing these are sustained regimes rather than flickers.

Usage: python scripts/make_regime_figure.py --run results/final/tb2_v5
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pyarrow.parquet as pq

GOLD = "../datasets/annotations/tb2/adjudicated.csv"
W = 10
MON = "B4_semantic"
PROXY = "B1_step30"


def regions_of(rs):
    regs, cur = [], None
    for r in rs:
        lab, t = int(r["binary"]), int(r["t"])
        if cur and lab == cur["label"]:
            cur["windows"].append(t); cur["end"] = max(cur["end"], t)
        else:
            if cur:
                regs.append(cur)
            cur = {"traj": r["traj_id"], "label": lab, "start": t, "end": t, "windows": [t]}
    if cur:
        regs.append(cur)
    return regs


def regime_figure(run: str, out: str, w: int = W) -> None:
    """Draw the regime figure for ``run`` into ``out``.

    Split out of main() so the layout audit can execute exactly the same code path the paper's
    figure comes from, instead of a reconstruction of it.
    """
    global W
    W = w
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8")) if r["binary"] != ""]
    by_traj = collections.defaultdict(list)
    for r in gold:
        by_traj[r["traj_id"]].append(r)
    for t in by_traj:
        by_traj[t].sort(key=lambda r: int(r["t"]))
    regs = []
    for tid, rs in by_traj.items():
        regs += regions_of(rs)
    pos = [g for g in regs if g["label"] == 1]
    neg = [g for g in regs if g["label"] == 0]

    sc = collections.defaultdict(dict)
    for r in pq.read_table(os.path.join(run, "monitor_scores.parquet"),
                           columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["w"] == W:
            sc[r["monitor"]][(r["traj_id"], r["t"])] = r["score"]

    def means(mon, g):
        v = [sc[mon].get((g["traj"], t)) for t in g["windows"]]
        v = [x for x in v if x is not None and x == x]
        return float(np.mean(v)) if v else None

    rows = []
    for g in pos:
        a = means(MON, g)
        nv = [sc[MON].get((h["traj"], t)) for h in neg if h["traj"] == g["traj"]
              for t in h["windows"]]
        nv = [x for x in nv if x is not None and x == x]
        if a is None or not nv:
            continue
        n = max(int(r["n_steps"]) for r in by_traj[g["traj"]])
        rows.append({"a": a, "b": float(np.mean(nv)), "len": g["end"] - g["start"] + W,
                     "rel": g["start"] / max(1, n), "traj": g["traj"]})

    # position-matched subset with proxy
    pm = []
    for g in pos:
        n = max(int(r["n_steps"]) for r in by_traj[g["traj"]])
        pr = g["start"] / max(1, n)
        band = 0 if pr < 0.33 else (1 if pr < 0.66 else 2)
        a = means(MON, g)
        pa = means(PROXY, g)
        nv, pv = [], []
        for h in neg:
            if h["traj"] != g["traj"]:
                continue
            hr = h["start"] / max(1, n)
            hb = 0 if hr < 0.33 else (1 if hr < 0.66 else 2)
            if hb != band:
                continue
            for t in h["windows"]:
                x = sc[MON].get((h["traj"], t))
                if x is not None and x == x:
                    nv.append(x)
                y = sc[PROXY].get((h["traj"], t))
                if y is not None and y == y:
                    pv.append(y)
        if a is not None and nv and pa is not None and pv:
            pm.append({"mon": a - float(np.mean(nv)), "proxy": pa - float(np.mean(pv))})

    # drawn at the width the paper prints it, and with the same font sizes, so the audit of the
    # canvas measures what the reader will see.  The right margin is reserved because the third
    # panel's x-label is wider than its panel and a tight bbox was trimming it at the figure edge.
    fig, axes = plt.subplots(1, 3, figsize=(6.5, 3.0),
                             gridspec_kw={"wspace": 0.50, "width_ratios": [1.10, 0.82, 0.92],
                                          "right": 0.955})

    # --- panel 1: paired within-run separation ---
    ax = axes[0]
    A = np.array([r["a"] for r in rows]); B = np.array([r["b"] for r in rows])
    ax.scatter(B, A, s=11, c="#3b4cc0", alpha=0.75, lw=0)
    lim = [min(B.min(), A.min()) - 0.05, max(B.max(), A.max()) + 0.05]
    ax.plot(lim, lim, color="#999999", lw=0.9, ls="--")
    ax.fill_between(lim, lim, [lim[1]] * 2, color="#3b4cc0", alpha=0.06, lw=0)
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("run's productive regions (mean)", fontsize=7)
    ax.set_ylabel("that run's stagnant episode", fontsize=7)
    above = int((A > B).sum())
    # a boxed caption: placed bare, this text is printed across the scatter points
    ax.text(0.04, 0.96, f"{above}/{len(rows)} above the diagonal", transform=ax.transAxes,
            fontsize=6.8, va="top", color="#2a3a8f",
            bbox=dict(facecolor="white", edgecolor="#c8cfe8", lw=0.5, pad=1.6, alpha=0.92))
    ax.set_title("within-run separation", fontsize=8)

    # --- panel 2: matched, monitor vs position proxy ---
    ax = axes[1]
    m = np.array([r["mon"] for r in pm]); p = np.array([r["proxy"] for r in pm])
    parts = ax.violinplot([m, p], showextrema=False, widths=0.75)
    for i, body in enumerate(parts["bodies"]):
        body.set_facecolor(["#3b4cc0", "#b0b0b0"][i])
        body.set_alpha(0.55)
    for i, d in enumerate((m, p), start=1):
        ax.scatter(np.full(len(d), i) + np.random.default_rng(i).normal(0, 0.035, len(d)),
                   d, s=8, color=["#3b4cc0", "#8a8a8a"][i - 1], alpha=0.8, lw=0, zorder=3)
        ax.hlines(np.median(d), i - 0.22, i + 0.22, color="k", lw=1.4, zorder=4)
    ax.axhline(0, color="#cc4444", lw=1.0, ls="-")
    ax.set_xticks([1, 2]); ax.set_xticklabels(["semantic\nmonitor", "position\nproxy"], fontsize=7)
    ax.set_ylabel("episode $-$ matched mean", fontsize=7)
    ax.text(0.03, 0.96, f"{(m>0).sum()}/{len(m)} vs {(p>0).sum()}/{len(p)}",
            transform=ax.transAxes, fontsize=6.8, va="top")
    ax.set_title("position-matched", fontsize=8)

    # --- panel 3: episode lengths ---
    ax = axes[2]
    L = np.array([r["len"] for r in rows])
    ax.hist(L, bins=np.arange(0, L.max() + 15, 15), color="#7a86d8", edgecolor="white", lw=0.5)
    ax.axvline(np.median(L), color="#2a3a8f", lw=1.2, ls="--")
    # Label widths are checked against panel widths: a label wider than its panel is trimmed by the
    # tight bbox at the figure edge, which is how "stagnant episode length (steps)" lost its last
    # characters.  The two-axis label is split so it fits inside an 0.82-of-2.84 panel.
    ax.set_xlabel("episode length", fontsize=7)
    ax.set_ylabel("episodes", fontsize=7)
    ax.text(0.96, 0.94, f"median {int(np.median(L))} steps\nmax {int(L.max())}",
            transform=ax.transAxes, fontsize=6.8, va="top", ha="right")
    ax.set_title("episodes are sustained", fontsize=8)

    for ax in axes:
        ax.tick_params(labelsize=6.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)

    # explicit ticks: a pane whose y-limits are set after autoscaling otherwise keeps a tick
    # label from beyond the new limits, which lands on the title.  Three values rather than five,
    # because five two-decimal labels within 0.20 of each other touch at this print height.
    axes[1].set_yticks([-0.10, 0.00, 0.10])
    axes[2].set_yticks([0, 5, 10, 15])

    fig.suptitle("Stagnation is an episode: the detector separates each run's own stalls",
                 fontsize=9.2, y=1.03)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fig.savefig(out, bbox_inches="tight", dpi=400)
    plt.close(fig)
    print(f"wrote {out}")
    print(f"  paired windows: {len(rows)}; matched subset: {len(pm)}")
    print(f"  monitor above zero: {(m>0).sum()}/{len(m)}; proxy: {(p>0).sum()}/{len(p)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/final/tb2_v5")
    ap.add_argument("--out", default="figures/fig_regimes_tb2_w10.png")
    args = ap.parse_args()
    regime_figure(args.run, args.out)


if __name__ == "__main__":
    main()
