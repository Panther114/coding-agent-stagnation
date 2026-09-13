"""Figures for the report, drawn only from frozen artifacts.

    python scripts/make_v2_figures.py            # writes paper/v2/figures/*.pdf and *.png

Every number plotted here is read out of the same JSON the report's audit checks
(`scripts/audit_paper_numbers.py`), so a figure cannot drift from the text.  Style rules: no
chartjunk, no in-figure titles (the LaTeX caption does that), direct labelling over legends,
horizontal gridlines only, one palette across all figures.

    fig1_measurement_trap    the self-referential metric inverts; the independent target restores it
    fig2_router_vs_field     router against every published family on identical rows and folds
    fig3_transfer_grid       six ordered train->test pairs, within vs cross
    fig4_calibration         requested vs achieved false-alarm rate, and what detection it buys
    fig5_decision_curve      value of routing vs always-verify / always-search / random
    fig6_cross_scaffold      fitted inside each scaffold vs transferred from SWE-agent
    fig7_live_conditions     the five live conditions, with Wilson intervals
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "rebuild"
LIVE = ROOT / "results" / "live"
OUT = ROOT.parent / "paper" / "v2" / "figures"

C = {
    "router": "#1b6ca8",
    "baseline": "#9aa5b1",
    "good": "#2f8f5b",
    "bad": "#c0554d",
    "accent": "#d98f28",
    "grid": "#dddddd",
    "text": "#222222",
}
plt.rcParams.update({
    "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5, "axes.edgecolor": "#888888",
    "axes.linewidth": 0.7, "xtick.color": C["text"], "ytick.color": C["text"],
    "axes.labelcolor": C["text"], "text.color": C["text"], "figure.dpi": 150,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "legend.frameon": False,
    "font.family": "DejaVu Sans",
})


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def tidy(ax, ygrid: bool = True) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if ygrid:
        ax.yaxis.grid(True, color=C["grid"], lw=0.6)
        ax.set_axisbelow(True)


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)
    print(f"  wrote {name}.pdf / .png")


# ---------------------------------------------------------------------------------------
# 1. the measurement trap
# ---------------------------------------------------------------------------------------


def fig1() -> None:
    sets = [("frozen\n(shards 0-3)", load(RES / "wrongness.json")),
            ("held-out A\n(shards 4-7)", load(RES / "wrongness_repl.json")),
            ("held-out B\n(shards 8-11)", load(RES / "wrongness_repl2.json"))]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5), sharey=True)
    for ax, (key, title) in zip(axes, [("pooled_on_target_self", "measured against the run's own patch"),
                                       ("pooled_on_target_gold", "measured against an independent gold patch")]):
        x = np.arange(len(sets))
        solved = [s[1]["corpora"]["nebius"][key]["solved"] for s in sets]
        failed = [s[1]["corpora"]["nebius"][key]["failed"] for s in sets]
        ax.bar(x - 0.19, solved, 0.36, color=C["good"], label="solved")
        ax.bar(x + 0.19, failed, 0.36, color=C["bad"], label="failed")
        for xi, (s, f) in enumerate(zip(solved, failed)):
            hi = max(s, f)
            ax.text(xi - 0.19, s + 0.012, f"{s:.3f}", ha="center", fontsize=7.5)
            ax.text(xi + 0.19, f + 0.012, f"{f:.3f}", ha="center", fontsize=7.5,
                    fontweight="bold" if (f > s) == (key.endswith("self")) else "normal")
        ax.set_xticks(x, [s[0] for s in sets], fontsize=7.5)
        ax.set_title(title, fontsize=8.5)
        ax.set_ylim(0, 0.82)
        tidy(ax)
    axes[0].set_ylabel("share of edits aimed at the target file")
    axes[0].legend(loc="upper left", fontsize=7.5, ncols=2)
    save(fig, "fig1_measurement_trap")


# ---------------------------------------------------------------------------------------
# 2. router vs the field
# ---------------------------------------------------------------------------------------


def fig2() -> None:
    d = load(RES / "route_modes_transfer.json")
    rows = []
    for tgt, label in (("y_fail", "will this run fail?"), ("y_wrong_fix", "LOST or WRONG-FIX?")):
        v = d["verdict"][tgt]
        loop, red = [], []
        for f in ("0.1", "0.2", "0.4", "0.6"):
            for cell in d["targets"][tgt][f]["cross"].values():
                loop.append(cell["ngram_loop"])
                red.append(cell["redundancy"])
        rows.append((label, [v["cross_own_rates_mean"], v["cross_position_mean"],
                             v["cross_agentstop_mean"], float(np.mean(loop)), float(np.mean(red))]))
    names = ["Route\n(this work)", "position\n(run length)", "AgentStop-style\noutput shape",
             "loop detection", "redundancy"]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.4), sharex=True)
    for ax, (label, vals) in zip(axes, rows):
        y = np.arange(len(vals))[::-1]
        cols = [C["router"]] + [C["baseline"]] * 4
        ax.barh(y, vals, 0.62, color=cols)
        for yi, v in zip(y, vals):
            ax.text(v + 0.008, yi, f"{v:.3f}", va="center", fontsize=7.5,
                    fontweight="bold" if v == vals[0] else "normal")
        ax.axvline(0.5, color=C["accent"], lw=0.8, ls=(0, (4, 2)))
        ax.text(0.506, len(vals) - 0.55, "chance", color=C["accent"], fontsize=7, va="center")
        ax.set_yticks(y, names if ax is axes[0] else [""] * len(names), fontsize=7.5)
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(0, 0.86)
        ax.set_title(label, fontsize=8.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.xaxis.grid(True, color=C["grid"], lw=0.6)
        ax.set_axisbelow(True)
    axes[0].set_xlabel("AUC, mean over 24 cross-set cells")
    save(fig, "fig2_router_vs_field")


# ---------------------------------------------------------------------------------------
# 3. transfer grid
# ---------------------------------------------------------------------------------------


def fig3() -> None:
    d = load(RES / "route_modes_transfer.json")
    fr = ("0.1", "0.2", "0.4", "0.6")
    pairs = sorted(d["targets"]["y_fail"]["0.2"]["cross"].keys())
    short = {"A": "0-3", "B": "4-7", "C": "8-11"}
    labels = [f"{short[p[0]]} → {short[p.split('->')[1][0]]}" for p in pairs]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5), sharey=True)
    for ax, (tgt, title) in zip(axes, (("y_fail", "failure prediction"), ("y_wrong_fix", "LOST vs WRONG-FIX"))):
        cross = [np.mean([d["targets"][tgt][f]["cross"][p]["own_rates"] for f in fr]) for p in pairs]
        within = [d["targets"][tgt][f]["within_" + k] for f in fr for k in
                  ("A_shards0_3", "B_shards4_7", "C_shards8_11")]
        y = np.arange(len(pairs))[::-1]
        ax.barh(y, cross, 0.6, color=C["router"], label="cross-set")
        for yi, v in zip(y, cross):
            ax.text(v + 0.008, yi, f"{v:.3f}", va="center", fontsize=7.5)
        ax.axvline(float(np.mean(within)), color=C["accent"], lw=1.0, ls=(0, (4, 2)))
        ax.text(float(np.mean(within)) + 0.004, len(pairs) - 0.6, "within-set\nmean", color=C["accent"],
                fontsize=7)
        ax.set_yticks(y, labels, fontsize=7.5)
        ax.set_xlim(0.5, 0.86)
        ax.set_title(title, fontsize=8.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.xaxis.grid(True, color=C["grid"], lw=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("trained on → tested on (shards)")
    axes[0].set_xlabel("AUC, mean over the four checkpoints")
    save(fig, "fig3_transfer_grid")


# ---------------------------------------------------------------------------------------
# 4. calibration
# ---------------------------------------------------------------------------------------


def fig4() -> None:
    d = load(RES / "route_modes.json")["calibration"]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5))
    for ax, mode, key in ((axes[0], "y_fail", "seq_threshold"), (axes[1], "y_mode", "seq_threshold")):
        alphas = [float(a) for a in d[mode]["alpha_levels"]]
        far = [d[mode]["by_alpha"][str(a)][key]["false_alarm_rate_mean"] for a in alphas]
        det = [d[mode]["by_alpha"][str(a)][key]["detection_rate_mean"] for a in alphas]
        ax.plot(alphas, alphas, color=C["accent"], lw=0.9, ls=(0, (4, 2)), label="requested = achieved")
        ax.plot(alphas, far, "o-", color=C["router"], lw=1.4, ms=4, label="achieved false-alarm rate")
        ax.plot(alphas, det, "s--", color=C["baseline"], lw=1.2, ms=4, label="detection rate")
        for a, f, t in zip(alphas, far, det):
            ax.annotate(f"{f:.3f}", (a, f), textcoords="offset points", xytext=(3, -8), fontsize=7)
            ax.annotate(f"{t:.3f}", (a, t), textcoords="offset points", xytext=(3, 2), fontsize=7,
                        color="#555555")
        ax.set_xlabel(r"requested $\alpha$")
        ax.set_xlim(0.02, 0.55)
        ax.set_ylim(-0.02, 0.6)
        ax.set_title("failure head" if mode == "y_fail" else "mode head (LOST vs WRONG-FIX)", fontsize=8.5)
        tidy(ax)
    axes[0].set_ylabel("rate")
    axes[0].legend(loc="upper left", fontsize=7)
    save(fig, "fig4_calibration")


# ---------------------------------------------------------------------------------------
# 5. decision curve
# ---------------------------------------------------------------------------------------


def fig5() -> None:
    d = load(RES / "route_modes.json")["decision_curve"]["conditional_on_failure"]
    fr = ["0.1", "0.2", "0.4", "0.6"]
    lambs = ["0.0", "0.25", "0.5"]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    series = {"detector": (C["router"], "o-", "Route"),
              "always_verify": (C["baseline"], "s--", "always VERIFY"),
              "random_routing": (C["accent"], "^--", "random"),
              "always_search": (C["bad"], "v--", "always SEARCH")}
    for key, (col, style, label) in series.items():
        vals = [np.mean([d[f]["by_lambda"][l][key] for f in fr]) for l in lambs]
        ax.plot([float(l) for l in lambs], vals, style, color=col, lw=1.4, ms=4, label=label)
    ax.set_xlabel(r"cost of a wrong route, $\lambda$")
    ax.set_ylabel("mean policy value on failing runs")
    ax.set_xticks([0.0, 0.25, 0.5])
    tidy(ax)
    ax.legend(loc="lower left", fontsize=7)
    save(fig, "fig5_decision_curve")


# ---------------------------------------------------------------------------------------
# 6. cross-scaffold negative
# ---------------------------------------------------------------------------------------


def fig6() -> None:
    d = load(RES / "router_xscaffold.json")
    names = {"openhands": "SWE-rebench / OpenHands\n67,074 runs",
             "thoughtworks": "thoughtworks agentic-coding\n15,000 runs",
             "swegym": "SWE-Gym / OpenHands\n6,055 runs"}
    fig, ax = plt.subplots(figsize=(4.6, 2.4))
    y = np.arange(len(names))[::-1]
    for yi, (key, label) in zip(y, names.items()):
        v = d["corpora"][key]["variants"]["bridgeable"]["0.20"]
        inside, trans, base = v["in_target_oof_auc"], v["auc_router"], max(v["baselines"].values())
        ax.plot([trans, inside], [yi, yi], color="#cccccc", lw=2.2, zorder=1)
        ax.plot([trans], [yi], "o", color=C["bad"], ms=6, zorder=2,
                label="transferred from SWE-agent" if yi == y[0] else None)
        ax.plot([inside], [yi], "o", color=C["good"], ms=6, zorder=2,
                label="fitted inside that scaffold" if yi == y[0] else None)
        ax.plot([base], [yi], "|", color=C["baseline"], ms=11, mew=1.6, zorder=2,
                label="best fixed baseline" if yi == y[0] else None)
        ax.text(trans - 0.012, yi, f"{trans:.3f}", ha="right", va="center", fontsize=7.5,
                color=C["bad"])
        ax.text(inside + 0.012, yi, f"{inside:.3f}", ha="left", va="center", fontsize=7.5,
                color=C["good"])
    ax.axvline(0.5, color=C["accent"], lw=0.8, ls=(0, (4, 2)))
    ax.text(0.506, len(names) - 0.35, "chance", color=C["accent"], fontsize=7, va="center")
    ax.set_yticks(y, list(names.values()), fontsize=7)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0.25, 0.85)
    ax.set_ylim(-0.6, len(names) - 0.2)
    ax.set_xlabel("AUC at the 20% checkpoint")
    tidy(ax)
    ax.xaxis.grid(True, color=C["grid"], lw=0.6)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0, 1.0, 0.15), ncols=3, fontsize=6.8,
              handletextpad=0.4, columnspacing=1.0)
    save(fig, "fig6_cross_scaffold")


# ---------------------------------------------------------------------------------------
# 7. live conditions
# ---------------------------------------------------------------------------------------


def fig7() -> None:
    d = load(LIVE / "live_arms_valid.json")["per_arm"]
    # NB the artifact key is "unhinted"; the report calls the same condition "unmasked"
    order = ["masked", "unhinted", "nudge", "hinted", "verify"]
    label = {"masked": "masked — only “N failed, M passed”",
             "unhinted": "unmasked — full pytest output (baseline)",
             "nudge": "nudge — content-free runtime message",
             "hinted": "hinted — file + function handed over",
             "verify": "verify — runtime says re-check the diagnosis"}
    fig, ax = plt.subplots(figsize=(5.4, 2.5))
    y = np.arange(len(order))[::-1]
    for yi, k in zip(y, order):
        v = d[k]
        lo, hi = v["success_ci95"]
        col = C["baseline"] if k == "unhinted" else (C["bad"] if k == "masked" else C["router"])
        ax.plot([lo, hi], [yi, yi], color=col, lw=2.0, alpha=0.55, solid_capstyle="round")
        ax.plot([v["success"]], [yi], "o", color=col, ms=6)
        ax.text(hi + 0.012, yi, f"{v['success']:.3f}  (n={v['n']})", va="center", fontsize=7.5)
    ax.set_yticks(y, [label[k] for k in order], fontsize=7.2)
    ax.set_xlim(0.0, 0.92)
    ax.set_xlabel("task success (95% Wilson interval)")
    tidy(ax)
    ax.xaxis.grid(True, color=C["grid"], lw=0.6)
    save(fig, "fig7_live_conditions")


def main() -> None:
    print(f"writing figures to {OUT}")
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    fig6()
    fig7()
    print("done")


if __name__ == "__main__":
    main()
