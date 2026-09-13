"""Throwaway: inspect real new_failure_ids sequences on the published universe."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\Gavania\Academic\Competitions\Agent_Correction\research")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import extract_step_verification as EX  # noqa: E402
from agentstall.verify import RunVerificationTracker  # noqa: E402


def main() -> None:
    universe, keys = EX.load_published_universe(ROOT / EX.PUBLISHED_RUNS)
    paths = sorted(ROOT.glob(EX.RAW_GLOB))
    shown = 0
    for row in EX.iter_runs(paths, None, universe, keys):
        obs_list = EX.observation_texts(row["trajectory"])
        if not obs_list:
            continue
        t = RunVerificationTracker()
        recs = [t.add(i, o) for i, o in enumerate(obs_list)]
        if not any(r.new_failure_ids for r in recs):
            continue
        shown += 1
        print("=" * 110)
        print(f"{row['run_id']}  steps={len(recs)}")
        for r in recs:
            if not r.has_test_obs and not r.failure_ids:
                continue
            print(f"  step {r.step:3d} {r.test_exit_signal:17s} "
                  f"pass={r.n_tests_passed} fail={r.n_tests_failed} err={r.n_tests_errored} "
                  f"collected={r.n_collected}")
            if r.failure_ids:
                print(f"           failing ids : {r.failure_ids}")
            if r.new_failure_ids:
                print(f"           NEW vs prev : {r.new_failure_ids}")
        if shown >= 14:
            break
    print("shown", shown)


if __name__ == "__main__":
    main()
