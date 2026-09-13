"""Recompute the live causal experiment on VALID episodes only, for every arm, honestly.

Two issues found by auditing the raw episode records rather than the summary:

1. `fail_before` was False in some episodes, i.e. the mutated package did not actually fail its
   suite at episode start (the mutation did not break the invoked tests, or the collection errored).
   Success is meaningless for those runs, so they are excluded rather than averaged in.  The filter
   *lowers* every arm, which is the signature of a real data problem: an unbroken task is a free
   "success".

2. Every hinted-vs-unhinted difference is NOT statistically significant at this sample size.  The
   pre-registered prediction P1 is an *inequality* about the size of the effect -- "the failure-rate
   drop is smaller than the 30.9% of failures attributable to never reaching the file" -- which
   holds, but a reader must not be left thinking a significant improvement has been shown.  Both
   facts are reported, for every pair of arms, with Fisher exact tests.

    python scripts/analyse_live_arms_valid.py \
        --episodes results/live/episodes48.jsonl results/live/episodes_masked.jsonl \
        --out results/live/live_arms_valid.json
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LOST_FRACTION_OBSERVED = 0.309


def load(p: Path) -> List[Dict[str, Any]]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def rate(rows: List[Dict[str, Any]], field: str = "success"):
    if not rows:
        return float("nan"), 0
    return sum(1 for r in rows if r.get(field)) / len(rows), len(rows)


def ci(rows: List[Dict[str, Any]], n: int = 5000, seed: int = 0) -> tuple:
    x = np.array([1.0 if r.get("success") else 0.0 for r in rows])
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    bs = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def fisher(a: int, b: int, c: int, d: int) -> float:
    from scipy.stats import fisher_exact
    return float(fisher_exact([[a, b], [c, d]])[1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", nargs="+", required=True)
    ap.add_argument("--out", default="results/live/live_arms_valid.json")
    args = ap.parse_args()

    recs: List[Dict[str, Any]] = []
    for e in args.episodes:
        p = Path(e)
        if not p.is_absolute():
            p = ROOT / p
        got = load(p)
        print(f"  {p.name}: {len(got)} episodes")
        recs.extend(got)

    valid = [r for r in recs if r.get("fail_before")]
    dropped = len(recs) - len(valid)
    arms = sorted({r["arm"] for r in valid})

    out: Dict[str, Any] = {
        "n_raw": len(recs), "n_dropped_fail_before_false": dropped, "n_valid": len(valid),
        "n_tasks": len({r["task_id"] for r in valid}), "arms": arms,
        "total_usd": round(sum(r.get("usd", 0.0) or 0.0 for r in recs), 4),
        "per_arm": {}, "pairwise": {},
    }
    for arm in arms:
        rows = [r for r in valid if r["arm"] == arm]
        s, n = rate(rows)
        lo, hi = ci(rows)
        g = [r for r in rows if r.get("reached_gold")]
        sg = rate(g, "success")[0] if g else float("nan")
        out["per_arm"][arm] = {
            "n": n, "success": round(s, 4), "success_ci95": [round(lo, 4), round(hi, 4)],
            "reached_gold": round(sum(1 for r in rows if r.get("reached_gold")) / max(n, 1), 4),
            "n_reached_gold": len(g), "success_given_reached_gold": round(sg, 4),
            "mean_turns": round(float(np.mean([r.get("n_turns") or 0 for r in rows])), 2),
            "test_files_removed": sum(r.get("test_files_removed", 0) for r in rows),
            "usd": round(sum(r.get("usd", 0.0) or 0.0 for r in rows), 4),
            "errors": sum(1 for r in rows if r.get("error")),
        }

    # every pair, so no comparison is left implicit
    for a, b in itertools.combinations(arms, 2):
        ra, rb = out["per_arm"][a], out["per_arm"][b]
        sa, sb = round(ra["success"] * ra["n"]), round(rb["success"] * rb["n"])
        out["pairwise"][f"{a}_vs_{b}"] = {
            "table": [[sa, ra["n"] - sa], [sb, rb["n"] - sb]],
            "success_diff": round(ra["success"] - rb["success"], 4),
            "p_fisher_two_sided": fisher(sa, ra["n"] - sa, sb, rb["n"] - sb),
            "significant_at_0.05": bool(fisher(sa, ra["n"] - sa, sb, rb["n"] - sb) < 0.05),
        }

    if "unhinted" in out["per_arm"] and "hinted" in out["per_arm"]:
        u, h = out["per_arm"]["unhinted"], out["per_arm"]["hinted"]
        drop = (1 - u["success"]) - (1 - h["success"])
        out["P1_failure_rate_drop"] = {
            "drop": round(drop, 4), "pre_registered_ceiling": LOST_FRACTION_OBSERVED,
            "holds": bool(drop < LOST_FRACTION_OBSERVED),
        }
    out["behaviour"] = {
        "episodes_where_agent_modified_the_test_files": sum(
            1 for r in valid if r.get("test_files_removed", 0) > 0),
        "total_test_files_removed": sum(r.get("test_files_removed", 0) for r in valid),
        "note": ("the verifier is restored before grading, so an agent that edits tests to pass is "
                 "still scored as failing; the count is a behavioural measurement, not a validity "
                 "threat"),
    }

    p = Path(args.out)
    if not p.is_absolute():
        p = ROOT / p
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nraw {out['n_raw']} -> valid {out['n_valid']} "
          f"(dropped {dropped} where the task was not actually broken at episode start)")
    for a, v in out["per_arm"].items():
        print(f"  {a:9s} n={v['n']:2d} success={v['success']:.3f} "
              f"CI[{v['success_ci95'][0]:.3f},{v['success_ci95'][1]:.3f}] "
              f"gold={v['reached_gold']:.3f} s|gold={v['success_given_reached_gold']:.3f} "
              f"turns={v['mean_turns']}")
    for k, v in out["pairwise"].items():
        print(f"  {k}: diff={v['success_diff']:+.3f} p={v['p_fisher_two_sided']:.3f} "
              f"{'SIGNIFICANT' if v['significant_at_0.05'] else 'not significant'}")
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
