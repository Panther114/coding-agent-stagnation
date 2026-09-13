"""What the per-step verification signal actually says, vs the evaluator's verdict.

This is the falsification probe the study needs: if per-step test outcomes were a
strong, always-available signal, the "waste is unpredictable from the observable
channel" claim would be in trouble.  This script quantifies how available the signal
is and how it lines up with the final evaluator outcome.

Run::

    python scripts/analyse_step_verification.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "results/rebuild/step_verification.parquet"
# NOTE: results/rebuild is reserved for pre-existing study artefacts plus
# step_verification.{parquet,json}, so this analysis lands under exploratory/.
OUT = ROOT / "results/exploratory/step_verification_signal.json"


def main() -> int:
    if not PARQUET.exists():
        raise SystemExit(f"{PARQUET} not built yet")
    df = pd.read_parquet(PARQUET)
    print(f"rows={len(df):,} runs={df['run_id'].nunique():,}")

    per_run = df.groupby("run_id", sort=False).agg(
        model=("model", "first"),
        reward=("reward", "first"),
        n_steps=("n_steps", "first"),
        n_obs=("has_test_obs", "sum"),
        n_pass_steps=("has_pass", "sum"),
        n_fail_steps=("has_failure", "sum"),
        n_new_failure_events=("n_new_failures", lambda s: int((s > 0).sum())),
        n_collection_err=("test_exit_signal", lambda s: int((s == "collection_error").sum())),
        ev_ran=("ev_ran", "first"),
        ev_pass=("ev_pass", "first"),
        ev_fail=("ev_fail", "first"),
        ev_error=("ev_error", "first"),
    )
    per_run["has_signal"] = per_run["n_obs"] > 0
    per_run["saw_pass"] = per_run["n_pass_steps"] > 0
    per_run["saw_fail"] = per_run["n_fail_steps"] > 0

    out: Dict[str, object] = {
        "n_steps": int(len(df)),
        "n_runs": int(len(per_run)),
        "runs_with_a_signal": int(per_run["has_signal"].sum()),
        "runs_with_a_signal_frac": float(per_run["has_signal"].mean()),
        "runs_where_agent_saw_a_pass": int(per_run["saw_pass"].sum()),
        "runs_where_agent_saw_a_failure": int(per_run["saw_fail"].sum()),
        "runs_with_new_failure_event": int((per_run["n_new_failure_events"] > 0).sum()),
        "steps_with_a_signal": int(df["has_test_obs"].sum()),
        "steps_with_a_signal_frac": float(df["has_test_obs"].mean()),
        "steps_truncated_before_a_verdict": int(df["truncated_obs"].sum()),
        "steps_with_progress_no_verdict": int((df["has_progress"] & ~df["has_test_obs"]).sum()),
    }

    # Evaluator cross-check on runs where the evaluator actually ran tests.  NOTE:
    # ev_pass/ev_fail/ev_error use -1 as "not reported", so a run is only judged from
    # them when ev_ran == 1; treating -1 as a failure count would mark every
    # un-evaluated run as broken.
    ev = per_run[(per_run["ev_ran"] == 1) & (per_run["ev_fail"] >= 0)].copy()
    out["runs_with_evaluator_verdict"] = int(len(ev))
    if len(ev):
        ev["ev_ok"] = (ev["ev_fail"] == 0) & (ev["ev_error"] <= 0)
        tab = pd.crosstab(ev["saw_fail"], ev["ev_ok"])
        out["evaluator_vs_agent_saw_failure"] = {
            f"agent_saw_fail={bool(a)}|evaluator_ok={bool(b)}": int(tab.loc[a, b])
            for a in tab.index for b in tab.columns
        }
        seen_any = ev[ev["has_signal"]]
        out["among_runs_where_the_agent_saw_a_step_outcome"] = {
            "n": int(len(seen_any)),
            "evaluator_ok_frac": float(seen_any["ev_ok"].mean()) if len(seen_any) else None,
            "no_step_ever_showed_a_failure_frac": float((seen_any["n_fail_steps"] == 0).mean())
            if len(seen_any) else None,
        }
        out["among_runs_without_any_step_outcome"] = {
            "n": int((~ev["has_signal"]).sum()),
            "evaluator_ok_frac": float(ev.loc[~ev["has_signal"], "ev_ok"].mean())
            if (~ev["has_signal"]).any() else None,
        }
    out["per_model"] = {
        str(m): {
            "n_runs": int(len(g)),
            "runs_with_a_signal_frac": float(g["has_signal"].mean()),
            "evaluator_ok_frac": float(g.loc[g["ev_ran"] == 1, "ev_fail"].eq(0).mean())
            if (g["ev_ran"] == 1).any() else None,
        }
        for m, g in per_run.groupby("model")
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
