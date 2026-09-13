"""Analyse the live causal experiment against the pre-registered predictions.

Pre-registration (fixed in `run_live_experiment.py` before any episode ran):
  P1  hinting raises the success rate only MODESTLY -- the failure-rate drop unhinted -> hinted
      should be SMALLER than the 30.9% of failures attributed to never reaching the file.  If
      hinting removes most failures, the observational result is wrong.
  P2  the verify arm beats unhinted, and by more than hinted does, because the binding constraint
      is fix quality rather than location.
  P3  conditional on reaching the gold file at least once, success is still well below certainty.

Reported honestly either way: a pre-registered prediction that fails is a result, and the point of
fixing the thresholds in advance was to make that impossible to fudge afterwards.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "live"
LOST_FRACTION_OBSERVED = 0.309  # from the observational study: failed runs never touching gold


def load(p: Path) -> List[Dict[str, Any]]:
    recs = []
    if not p.exists():
        return recs
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                recs.append(json.loads(line))
            except Exception:
                pass
    return recs


def mean_ci(x: np.ndarray, n: int = 5000, seed: int = 0) -> tuple:
    x = np.asarray([v for v in x if v is not None and not (isinstance(v, float) and np.isnan(v))],
                   dtype=float)
    if len(x) == 0:
        return (float("nan"), float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    bs = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return float(x.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def fisher(a: int, b: int, c: int, d: int) -> float:
    try:
        from scipy.stats import fisher_exact

        return float(fisher_exact([[a, b], [c, d]])[1])
    except Exception:
        return float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", nargs="+",
                    default=["results/live/episodes.jsonl", "results/live/smoke2_episodes.jsonl"])
    ap.add_argument("--out", default="results/live/live_experiment.json")
    args = ap.parse_args()

    recs: List[Dict[str, Any]] = []
    for e in args.episodes:
        p = Path(e)
        if not p.is_absolute():
            p = ROOT / p
        got = load(p)
        if got:
            print(f"  loaded {len(got)} episodes from {p.name}")
        recs.extend(got)
    if not recs:
        raise SystemExit("no episodes found; run scripts/run_live_experiment.py first")

    arms = sorted({r["arm"] for r in recs})
    res: Dict[str, Any] = {
        "n_episodes": len(recs),
        "n_tasks": len({r["task_id"] for r in recs}),
        "arms": arms,
        "total_usd": round(sum(r.get("usd", 0.0) or 0.0 for r in recs), 4),
        "per_arm": {},
    }

    for a in arms:
        rows = [r for r in recs if r["arm"] == a]
        succ = np.array([1.0 if r.get("success") else 0.0 for r in rows])
        gold = np.array([1.0 if r.get("reached_gold") else 0.0 for r in rows])
        turns = np.array([r.get("n_turns", 0) for r in rows], dtype=float)
        err = sum(1 for r in rows if r.get("error"))
        m, lo, hi = mean_ci(succ)
        res["per_arm"][a] = {
            "n": len(rows), "success": round(m, 4),
            "success_ci95": [round(lo, 4), round(hi, 4)],
            "reached_gold": round(float(gold.mean()), 4) if len(gold) else None,
            "mean_turns": round(float(turns.mean()), 2) if len(turns) else None,
            "errors": err,
            "usd": round(sum(r.get("usd", 0.0) or 0.0 for r in rows), 4),
        }
        # P3 lives here: among episodes that reached the gold file, how often did they still fail?
        g = [r for r in rows if r.get("reached_gold")]
        if g:
            res["per_arm"][a]["success_given_reached_gold"] = round(
                float(np.mean([1.0 if r.get("success") else 0.0 for r in g])), 4)
            res["per_arm"][a]["n_reached_gold"] = len(g)

    # ---- pre-registered tests ------------------------------------------------------
    tests: Dict[str, Any] = {}
    if "unhinted" in res["per_arm"] and "hinted" in res["per_arm"]:
        u, h = res["per_arm"]["unhinted"], res["per_arm"]["hinted"]
        fail_u, fail_h = 1 - u["success"], 1 - h["success"]
        drop = fail_u - fail_h
        tests["P1_hint_gain_lt_lost_fraction"] = {
            "fail_rate_unhinted": round(fail_u, 4), "fail_rate_hinted": round(fail_h, 4),
            "failure_rate_drop": round(drop, 4),
            "pre_registered_lost_fraction": LOST_FRACTION_OBSERVED,
            "prediction": "drop < 0.309",
            "holds": bool(drop < LOST_FRACTION_OBSERVED),
            "p_fisher": fisher(int(u["success"] * u["n"]), u["n"] - int(u["success"] * u["n"]),
                               int(h["success"] * h["n"]), h["n"] - int(h["success"] * h["n"])),
        }
    if all(a in res["per_arm"] for a in ("unhinted", "hinted", "verify")):
        u, h, v = (res["per_arm"][a]["success"] for a in ("unhinted", "hinted", "verify"))
        tests["P2_verify_beats_unhinted_and_hint"] = {
            "unhinted": u, "hinted": h, "verify": v,
            "verify_minus_unhinted": round(v - u, 4),
            "hinted_minus_unhinted": round(h - u, 4),
            "prediction": "verify - unhinted > hinted - unhinted",
            "holds": bool((v - u) > (h - u)),
        }
    gvals = []
    for a in arms:
        pa = res["per_arm"][a]
        if pa.get("n_reached_gold"):
            gvals.append((a, pa["success_given_reached_gold"], pa["n_reached_gold"]))
    if gvals:
        tests["P3_success_given_reached_gold_below_certainty"] = {
            "by_arm": {a: {"success_given_reached_gold": s, "n": n} for a, s, n in gvals},
            "prediction": "all well below 1.0",
            "holds": bool(all(s < 0.9 for _, s, _ in gvals)),
        }
    res["pre_registered_tests"] = tests

    p = Path(args.out)
    if not p.is_absolute():
        p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=float), encoding="utf-8")

    print(f"\nepisodes {res['n_episodes']} over {res['n_tasks']} tasks  ${res['total_usd']}")
    print(f"{'arm':10s} {'n':>4} {'success':>8} {'ci95':>16} {'gold':>6} {'s|gold':>7} {'turns':>6}")
    for a, v in res["per_arm"].items():
        print(f"{a:10s} {v['n']:>4} {v['success']:>8.3f} "
              f"[{v['success_ci95'][0]:.3f},{v['success_ci95'][1]:.3f}] "
              f"{str(v.get('reached_gold'))[:5]:>6} "
              f"{str(v.get('success_given_reached_gold'))[:6]:>7} {v.get('mean_turns')}")
    for k, v in tests.items():
        print(f"  {k}: holds={v.get('holds')}")
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
