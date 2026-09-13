"""Integrity check: does ``step_verification.parquet`` line up with the study tables?

This is the guard that makes the per-step verification records usable.  If the run
universe, the step counts or the ``(run_id, step)`` keys drifted from
``data/processed/steps/nebius/``, every downstream join would be silently wrong --
an inner join would just return fewer rows and look fine.

Run::

    python scripts/check_step_verification.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SV = ROOT / "results/rebuild/step_verification.parquet"
PUB_RUNS = ROOT / "data/processed/steps/nebius/runs.parquet"
PUB_STEPS = ROOT / "data/processed/steps/nebius/steps.parquet"


def main() -> int:
    if not SV.exists():
        raise SystemExit(f"{SV} not built yet")
    sv = pd.read_parquet(SV)
    pub = pd.read_parquet(PUB_RUNS)
    psteps = pd.read_parquet(PUB_STEPS, columns=["run_id", "step", "n_steps"])

    checks = {}

    print(f"step_verification : {len(sv):,} rows / {sv['run_id'].nunique():,} runs")
    print(f"published runs    : {len(pub):,} rows / {pub['run_id'].nunique():,} runs")
    print(f"published steps   : {len(psteps):,} rows")

    checks["run_ids_equal_runs_table"] = set(sv["run_id"]) == set(pub["run_id"])
    checks["run_ids_equal_steps_table"] = set(sv["run_id"]) == set(psteps["run_id"])
    checks["per_run_step_counts_equal"] = sv.groupby("run_id").size().sort_index().equals(
        psteps.groupby("run_id").size().sort_index())
    # per-run comparison, because a global sort is not stable across tables and
    # pandas' equals() would then report a false mismatch on identical content
    js = sv.groupby("run_id")["step"].apply(lambda s: tuple(sorted(s)))
    jp = psteps.groupby("run_id")["step"].apply(lambda s: tuple(sorted(s)))
    n_bad = int((js != jp).sum())
    checks["run_id_step_keys_identical"] = n_bad == 0
    if n_bad:
        print(f"  note: {n_bad} runs differ in their (run_id, step) sets")

    m = sv.merge(pub[["run_id", "n_steps", "reward", "model"]], on="run_id",
                 suffixes=("", "_pub"))
    checks["n_steps_agrees"] = bool((m["n_steps"] == m["n_steps_pub"]).all())
    checks["reward_agrees"] = bool((m["reward"] == m["reward_pub"]).all())
    checks["model_agrees"] = bool((m["model"] == m["model_pub"]).all())

    for k, v in checks.items():
        print(f"  {'OK  ' if v else 'FAIL'}  {k}")

    print()
    print("outcome signals :", sv["test_exit_signal"].value_counts().to_dict())
    print("verify_source   :", sv["verify_source"].value_counts().to_dict())
    print(f"steps with a recovered outcome : {int(sv['has_test_obs'].sum()):,} "
          f"({sv['has_test_obs'].mean():.4%})")
    print(f"steps truncated before a verdict: {int(sv['truncated_obs'].sum()):,}")
    print(f"steps naming failing test ids   : {int((sv['n_failing_ids'] > 0).sum()):,}")
    print(f"steps with a NEW failing id      : {int((sv['n_new_failures'] > 0).sum()):,}")

    failed = [k for k, v in checks.items() if not v]
    print()
    print("ALL CHECKS PASSED" if not failed else f"FAILED CHECKS: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
