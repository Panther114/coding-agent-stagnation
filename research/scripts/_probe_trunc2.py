"""Throwaway: how often does _is_truncated fire on real test observations?"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\Gavania\Academic\Competitions\Agent_Correction\research")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import extract_step_verification as EX  # noqa: E402
from agentstall import verify as V  # noqa: E402


def main() -> None:
    universe, keys = EX.load_published_universe(ROOT / EX.PUBLISHED_RUNS)
    paths = sorted(ROOT.glob(EX.RAW_GLOB))
    c = Counter()
    tails = Counter()
    n = 0
    for row in EX.iter_runs(paths, None, universe, keys):
        n += 1
        for obs in EX.observation_texts(row["trajectory"]):
            if not obs:
                continue
            if not (V._PYTEST_SESSION_HDR.search(obs) or V._UNITTEST_RAN.search(obs)):
                continue
            c["testish"] += 1
            if V._is_truncated(obs):
                c["trunc"] += 1
                if len(tails) < 25:
                    tails[obs.strip().splitlines()[-1][:70]] += 1
            p = V.parse_observation(obs)
            if not p.resolved:
                c["unresolved"] += 1
        if n >= 2500:
            break
    print(dict(c))
    for t, k in tails.most_common(25):
        print(f"  {k:4d}  {t!r}")


if __name__ == "__main__":
    main()
