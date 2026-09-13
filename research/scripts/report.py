"""Compact table of the current results, for console review.

Usage: python scripts/report.py --run results/final/tb2_round1 --corpus tb2 [--w 10]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import paths  # noqa: E402


def f(x: Any, nd: int = 3) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "  --  "
    return "  nan " if v != v else f"{v:.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--ann", default=None)
    args = ap.parse_args()
    ann = args.ann or os.path.join(paths.DATA, "annotations", args.corpus)
    wl = json.load(open(os.path.join(args.run, "window_metrics.json"), encoding="utf-8"))
    fr = json.load(open(os.path.join(args.run, "alarm_frontier.json"), encoding="utf-8"))
    ag = json.load(open(os.path.join(ann, "agreement.json"), encoding="utf-8"))

    print("== annotation ==")
    print(f"windows {ag['n_cards']}  binary {ag['n_binary']}  pos rate {f(ag['positive_rate'])}  "
          f"cross-round agreement {f(ag.get('binary_agreement'))}  kappa {f(ag.get('cohen_kappa'),2)}  "
          f"positive Jaccard {f(ag.get('positive_jaccard'),2)}")
    print(f"label counts {ag['labels']}")
    print(f"subtypes {ag.get('details')}")
    print()
    print("== window level (w=%d) ==" % args.w)
    print(f"{'monitor':26}{'ROC':>7}{'PR':>7}{'F1':>7}{'thr':>6}{'P@.7':>7}{'R@.7':>7}")
    for name in sorted(wl):
        m = wl[name].get(str(args.w)) or wl[name].get(args.w)
        if not m:
            continue
        a7 = (m.get("at_thresholds") or {}).get("0.7", {})
        print(f"{name:26}{f(m['roc_auc']):>7}{f(m['pr_auc']):>7}{f(m['f1_best']):>7}"
              f"{f(m['thr_best'],2):>6}{f(a7.get('precision'),2):>7}{f(a7.get('recall'),2):>7}")
    print()
    print("== alarm level (annotated trajectories) ==")
    print(f"{'monitor':26}" + "".join(f"{'b='+format(b,'.2f'):>26}" for b in (0.01, 0.05, 0.10, 0.20)))
    print(f"{'':26}" + "".join(f"{'fs/det/saved/lat':>26}" for _ in range(4)))
    for name in sorted(fr):
        rows = fr[name].get(str(args.w)) or fr[name].get(args.w)
        if not rows:
            continue
        by = {round(r["budget"], 3): r for r in rows}
        cells = []
        for b in (0.01, 0.05, 0.10, 0.20):
            r = by.get(b, {})
            cells.append(f"{f(r.get('false_stop_rate'),2)}/{f(r.get('detection_rate'),2)}/"
                         f"{f(r.get('mean_saved_steps'),1)}/{f(r.get('median_latency'),0)}")
        print(f"{name:26}" + "".join(f"{c:>26}" for c in cells))
    print()
    desc = json.load(open(os.path.join(args.run, "descriptive.json"), encoding="utf-8"))
    print("== free-running alarms at threshold 0.7 ==")
    print(f"{'monitor':26}{'alarm rate':>12}{'median step':>13}{'median saved':>14}{'pass|alarm':>12}{'pass|all':>10}")
    for k in sorted(desc):
        d = desc[k]
        if not k.endswith("w%d" % args.w):
            continue
        print(f"{k.split('|')[0]:26}{f(d['alarm_rate'],3):>12}{str(d['median_alarm_step']):>13}"
              f"{str(d['median_steps_saved']):>14}{f(d['pass_rate_among_alarmed'],3):>12}"
              f"{f(d['pass_rate_all'],3):>10}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
