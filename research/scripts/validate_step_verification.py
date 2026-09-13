"""Validate the extraction: is the low coverage a parser gap or genuinely absent data?

Three checks, all on the raw corpus:

1. **Miss audit.**  Stream observations, run the parser, and look for any *unresolved*
   step (`exit_signal == unknown`) that nevertheless contains a count-shaped phrase
   (`12 passed`, `3 failed`, `Ran 54 tests`, `OK (skipped=..)`).  Each hit is a real
   parser miss and is printed.
2. **Ceiling.**  Of the observations that prove tests ran (a pytest session header or
   unittest's `Ran N tests`), what fraction carry a recoverable verdict?  That is the
   data's ceiling, independent of this parser.
3. **False-positive audit.**  Print a sample of resolved steps with their matched raw
   string so the reading can be eyeballed against the observation.

Run::

    python scripts/validate_step_verification.py --max-runs 3000
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import extract_step_verification as EX  # noqa: E402
from agentstall import verify as V  # noqa: E402

RAW_GLOB = "data/raw/nebius/train-*.parquet"

# any phrase that *looks like* a test verdict, whether or not the parser caught it.
# Deliberately anchored so that curl/wget progress tables (`100  915  100  915`) and
# `--:--:--` clock columns cannot masquerade as test counts.
VERDICT_SHAPED = re.compile(
    r"(?:^\s*=+[^\n=]*?\b\d+\s+(?:failed|passed|errors?|skipped|deselected)\b[^\n=]*?=+\s*$"
    r"|^\s*\d+\s+(?:failed|passed|errors?|skipped)(?:,|$)"
    r"|^\s*no tests ran\b"
    r"|^\s*Ran\s+\d+\s+tests?\b"
    r"|^\s*OK(?:\s*\([^)]*\))?\s*$"
    r"|^\s*FAILED\s*\([^)]*\)\s*$"
    r"|collected\s+\d+\s+items?\s*/\s*\d+\s+errors?"
    r"|Interrupted:\s*\d+\s+errors?\s+during\s+collection"
    r"|^\s*=+\s*\d+\s+errors?\s+in\s+\d)",
    re.M | re.I,
)
PROVES_TESTS_RAN = re.compile(
    r"(?:=+ test session starts =+"
    r"|^Ran\s+\d+\s+tests?\s+in\s+\d"
    r"|^={3,}.*\d+\s+(?:passed|failed)\b)",
    re.M | re.I,
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-runs", type=int, default=3000)
    ap.add_argument("--all-raw", action="store_true",
                    help="scan every raw trajectory, not just the published study universe")
    args = ap.parse_args(argv)

    paths = sorted(ROOT.glob(RAW_GLOB))
    universe = universe_keys = None
    if not args.all_raw:
        universe, universe_keys = EX.load_published_universe(ROOT / EX.PUBLISHED_RUNS)
    n_runs = n_obs = 0
    n_ran = n_resolved = 0
    n_shaped = 0
    misses: List[Tuple[str, str]] = []
    fp_samples: List[Tuple[str, str, str]] = []
    unknown_with_ids = 0
    t0 = time.time()

    for path in paths:
        if n_runs >= args.max_runs:
            break
        for row in EX.iter_runs([path], args.max_runs - n_runs, universe, universe_keys):
            n_runs += 1
            iid = row["instance_id"]
            for obs in EX.observation_texts(row["trajectory"]):
                if not obs:
                    continue
                n_obs += 1
                p = V.parse_observation(obs)
                if PROVES_TESTS_RAN.search(obs):
                    n_ran += 1
                    if p.resolved:
                        n_resolved += 1
                if VERDICT_SHAPED.search(obs):
                    n_shaped += 1
                    if not p.resolved and len(misses) < 40:
                        misses.append((iid, _context(obs)))
                if not p.resolved and p.failure_ids:
                    unknown_with_ids += 1
                if p.resolved and len(fp_samples) < 60:
                    fp_samples.append((iid, p.exit_signal, p.raw_matches[0] if p.raw_matches else ""))

    print(f"scanned {n_runs} runs / {n_obs} observations in {time.time()-t0:.0f}s")
    print(f"observations proving tests ran : {n_ran}")
    print(f"  ...with a recovered verdict  : {n_resolved} ({n_resolved/max(n_ran,1):.2%})  <- data ceiling")
    print(f"observations with a verdict-shaped phrase: {n_shaped}")
    print(f"  ...that the parser did NOT resolve    : {len(misses)} (sampled, cap 40)")
    print(f"unknown-but-has-failure-ids events      : {unknown_with_ids}")
    print()
    if misses:
        print("### PARSER MISSES (verdict-shaped text that stayed `unknown`)")
        for iid, ctx in misses[:12]:
            print("=" * 100)
            print("instance", iid)
            print(ctx)
    else:
        print("### No parser misses found: every verdict-shaped observation resolved.")
    print()
    print("### resolved-step sample (raw matched substring)")
    for iid, sig, raw in fp_samples[:25]:
        print(f"  {sig:17s} {iid:45s} {raw[:120]}")
    return 0


def _context(obs: str, width: int = 700) -> str:
    m = VERDICT_SHAPED.search(obs)
    if not m:
        return obs[:width]
    lo = max(m.start() - width // 2, 0)
    return obs[lo:lo + width]


if __name__ == "__main__":
    raise SystemExit(main())
