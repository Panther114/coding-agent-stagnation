"""Recompute the 48-task causal experiment on VALID episodes only, and report significance honestly.

Two issues found by auditing the raw episode records rather than the summary:

1. `fail_before` was False in some episodes, i.e. the mutated package did not actually fail its
   suite at episode start (the mutation did not break the invoked tests, or the collection errored).
   Success is meaningless for those runs, so they must be excluded rather than averaged in.

2. The hinted-vs-unhinted difference is NOT statistically significant at this sample size. The
   pre-registered prediction P1 is an *inequality* about the size of the effect ("the failure-rate
   drop is smaller than the 30.9% of failures attributable to never reaching the file"), which
   holds; but a reader must not be left thinking we have shown a significant improvement. Both
   facts are reported.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
recs = [json.loads(l) for l in (ROOT / "results/live/episodes48.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()]

valid = [r for r in recs if r.get("fail_before")]
dropped = len(recs) - len(valid)


def rate(rows, field="success"):
    if not rows:
        return float("nan"), 0
    return sum(1 for r in rows if r.get(field)) / len(rows), len(rows)


def ci(rows, n=5000, seed=0):
    x = np.array([1.0 if r.get("success") else 0.0 for r in rows])
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    bs = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def fisher(a, b, c, d):
    from scipy.stats import fisher_exact
    return float(fisher_exact([[a, b], [c, d]])[1])


out = {"n_raw": len(recs), "n_dropped_fail_before_false": dropped, "n_valid": len(valid),
       "arms": {}}
for arm in ("unhinted", "hinted"):
    rows = [r for r in valid if r["arm"] == arm]
    s, n = rate(rows)
    lo, hi = ci(rows)
    g = [r for r in rows if r.get("reached_gold")]
    sg, ng = rate(g) if g else (float("nan"), 0)
    out["arms"][arm] = {
        "n": n, "success": round(s, 4), "success_ci95": [round(lo, 4), round(hi, 4)],
        "reached_gold": round(sum(1 for r in rows if r.get("reached_gold")) / max(n, 1), 4),
        "success_given_reached_gold": round(sg, 4), "n_reached_gold": ng,
        "mean_turns": round(float(np.mean([r.get("n_turns") or 0 for r in rows])), 2),
        "test_files_removed": sum(r.get("test_files_removed", 0) for r in rows),
    }

u = out["arms"]["unhinted"]
h = out["arms"]["hinted"]
out["P1_failure_rate_drop"] = {
    "drop": round((1 - u["success"]) - (1 - h["success"]), 4),
    "pre_registered_ceiling": 0.309,
    "holds": bool(((1 - u["success"]) - (1 - h["success"])) < 0.309),
}
su, sh = round(u["success"] * u["n"]), round(h["success"] * h["n"])
out["significance_hinted_vs_unhinted"] = {
    "table": [[sh, h["n"] - sh], [su, u["n"] - su]],
    "p_fisher_two_sided": fisher(sh, h["n"] - sh, su, u["n"] - su),
    "note": "NOT significant at this sample size; reported so the effect is not over-read",
}
out["behaviour"] = {
    "episodes_where_agent_modified_the_test_files": sum(
        1 for r in valid if r.get("test_files_removed", 0) > 0),
    "total_test_files_removed": sum(r.get("test_files_removed", 0) for r in valid),
    "note": ("the verifier is restored before grading, so an agent that edits tests to pass is "
             "still scored as failing; the count is a behavioural measurement, not a validity "
             "threat"),
}

(ROOT / "results/live/live_experiment48_valid.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"raw {out['n_raw']} -> valid {out['n_valid']} (dropped {dropped} where the task was not "
      f"actually broken at episode start)")
for a, v in out["arms"].items():
    print(f"  {a:9s} n={v['n']:2d} success={v['success']:.3f} "
          f"CI[{v['success_ci95'][0]:.3f},{v['success_ci95'][1]:.3f}] "
          f"gold={v['reached_gold']:.3f} s|gold={v['success_given_reached_gold']:.3f} "
          f"turns={v['mean_turns']}")
print(f"  P1 drop={out['P1_failure_rate_drop']['drop']} holds="
      f"{out['P1_failure_rate_drop']['holds']}  fisher p="
      f"{out['significance_hinted_vs_unhinted']['p_fisher_two_sided']:.4f}")
print(f"  agent modified test files in {out['behaviour']['episodes_where_agent_modified_the_test_files']} "
      f"episodes ({out['behaviour']['total_test_files_removed']} files removed)")
