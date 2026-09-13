"""How wide does a label need to be, in points, with no axes involved?

Used to size an axis label so it cannot overrun its panel: render the string alone and measure it.
"""
from __future__ import annotations

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def text_width_pt(s: str, fontsize: float, family: str = "DejaVu Sans") -> float:
    fig = plt.figure(figsize=(8, 1), dpi=100)
    t = fig.text(0.01, 0.5, s, fontsize=fontsize, family=family)
    fig.canvas.draw()
    w = t.get_window_extent().width * 72.0 / fig.dpi
    plt.close(fig)
    return w


def main() -> None:
    strings = [
        "stagnant episode length (steps)",
        "stagnant episode length",
        "episode length (steps)",
        "episode length",
        "run's productive regions (mean)",
        "that run's stagnant episode",
        "episode - matched mean",
        "semantic\nmonitor",
        "position\nproxy",
        "annotated windows",
        "detection vs risk",
        "cost vs threshold",
    ]
    print(f"{'string':34} {'6.8pt':>8} {'7.0pt':>8} {'7.4pt':>8}")
    for s in strings:
        row = " ".join(f"{text_width_pt(s, f):8.1f}" for f in (6.8, 7.0, 7.4))
        print(f"{s.replace(chr(10), ' / '):34} {row}")
    print("\npanel width for reference: the third panel is 0.92/2.84 of about 6.2in usable,")
    print("i.e. roughly 145 pt wide; its y tick labels take about 10 pt of that.")


if __name__ == "__main__":
    main()
