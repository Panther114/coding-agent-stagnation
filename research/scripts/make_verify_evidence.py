"""Generate ``docs/VERIFY_PARSER_EVIDENCE.md`` from the real corpus.

This is the "proof ladder" for ``src/agentstall/verify.py``: every pattern in the
parser is listed against a literal string that was actually observed in
``data/raw/nebius/train-*.parquet``, with the count of observations it occurs in.

Run::

    python scripts/make_verify_evidence.py
    python scripts/make_verify_evidence.py --max-runs 6000 --out docs/VERIFY_PARSER_EVIDENCE.md
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import extract_step_verification as EX  # noqa: E402
from agentstall import verify as V  # noqa: E402

RAW_GLOB = "data/raw/nebius/train-*.parquet"
OUT = "docs/VERIFY_PARSER_EVIDENCE.md"

# (label, pattern, what it drives in verify.py)
PATTERNS: Sequence[Tuple[str, re.Pattern, str]] = (
    ("pytest session header", re.compile(r"=+ test session starts =+"),
     "context only: proves the observation is a pytest run"),
    ("pytest terminal summary", re.compile(
        r"^=+ [^\n=]*?\b(?:\d+\s+(?:failed|passed|errors?|skipped|deselected)|no tests ran)\b"
        r"[^\n=]*? in \d+(?:\.\d+)?s[^\n=]* =+$", re.M),
     "`_read_pytest` -> n_tests_passed/failed/errored, EXIT_* signal"),
    ("collected N items", re.compile(r"collected \d+ items?", re.I),
     "`_read_collected` -> n_collected"),
    ("collected N items / M errors", re.compile(r"collected \d+ items? / \d+ errors?"),
     "`_read_collected` -> n_collected + has_collection_errors"),
    ("Interrupted during collection", re.compile(
        r"!{3,}\s*Interrupted:\s*\d+\s+errors?\s+during\s+collection", re.I),
     "`_read_errors_only` -> EXIT_COLLECTION_ERROR"),
    ("pytest short summary info", re.compile(r"^=+ short test summary info =+$", re.M),
     "marks the block that carries `FAILED <nodeid>` lines"),
    ("pytest FAILED node id", re.compile(r"^FAILED[ \t]+\S", re.M),
     "`extract_failure_ids` -> failure_ids / new_failure_ids"),
    ("pytest ERROR line (module level)", re.compile(r"^ERROR\s+\S", re.M),
     "`_read_errors_only` -> EXIT_ERROR"),
    ("truncated FAILED message", re.compile(r"^FAILED \S+ - \S+.*\.\.\.$", re.M),
     "audit: the node id survives, the message does not"),
    ("unittest Run summary", re.compile(r"^Ran \d+ tests? in \d", re.M),
     "`_read_unittest` -> n_collected"),
    ("unittest OK verdict", re.compile(r"^OK( \(.*\))?$", re.M),
     "`_read_unittest` -> EXIT_ALL_PASS"),
    ("unittest FAILED verdict", re.compile(r"^FAILED \(.*\)$", re.M),
     "`_read_unittest` -> n_tests_failed / n_tests_errored"),
    ("unittest FAIL/ERROR banner", re.compile(r"^(?:FAIL|ERROR):\s+\S+\s*\([^)]*\)$", re.M),
     "`extract_failure_ids` -> unittest node ids, canonicalised"),
    ("nose2 loader failure", re.compile(r"^ERROR:\s+\S+\s+\([^)]*[Ll]oader[^)]*\)$", re.M),
     "`_read_errors_only` -> EXIT_ERROR (a whole module failed to load)"),
    ("no tests ran", re.compile(r"no tests ran", re.I),
     "`_read_pytest` -> EXIT_NO_TESTS"),
    ("progress but no verdict", re.compile(r"\[\s*\d+%\]"),
     "`_read_progress` -> has_progress; keeps EXIT_UNKNOWN honest"),
    ("timeout / kill", re.compile(r"\b(timed out|timeout|killed|took too long)\b", re.I),
     "audit only: a killed suite yields no verdict"),
)

# the tricky cases the parser must survive, and how to recognise them
TRICKY: Sequence[Tuple[str, re.Pattern, str]] = (
    ("parametrised node ids",
     re.compile(r"FAILED \S+\[[^\]]+\]"),
     "`[add_repeated]`, `[1-2-X]` and `[with spaces-in id]` must stay attached to the id"),
    ("warnings interleaved with results",
     re.compile(r"=+ warnings summary =+"),
     "`4 warnings` must never be counted as failures or as passes"),
    ("deselected tests",
     re.compile(r"\d+ deselected"),
     "`54 deselected` is not 54 tests"),
    ("truncated output",
     re.compile(r"=[= ]{0,40}(?:FA|FAIL|shor)\s*$", re.M),
     "the terminal summary is cut off; the step must stay `unknown`, not `all_pass`"),
    ("elided failure message",
     re.compile(r"^FAILED \S+ - \w+\s*\.\.\.$", re.M),
     "pytest's own truncation, not the harness's"),
    ("no tests collected",
     re.compile(r"collected 0 items"),
     "must be `no_tests`, distinct from a pass"),
    ("unittest with zero tests",
     re.compile(r"^Ran 0 tests in "),
     "unittest prints `OK` for a run that tested nothing"),
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-runs", type=int, default=3500)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--all-raw", action="store_true",
                    help="scan every raw trajectory, not just the published study universe")
    args = ap.parse_args(argv)

    paths = sorted(ROOT.glob(RAW_GLOB))
    universe = universe_keys = None
    if not args.all_raw:
        universe, universe_keys = EX.load_published_universe(ROOT / EX.PUBLISHED_RUNS)
    counts = Counter()
    examples: Dict[str, List[Tuple[str, str, str]]] = {}
    n_runs = n_obs = 0
    testish: List[Tuple[str, str, str]] = []
    seen_testish = 0
    t0 = time.time()

    stop = False
    for path in paths:
        if stop:
            break
        for row in EX.iter_runs([path], args.max_runs - n_runs, universe, universe_keys):
            n_runs += 1
            iid = row["instance_id"]
            for step_i, obs in enumerate(EX.observation_texts(row["trajectory"])):
                if not obs:
                    continue
                n_obs += 1
                for label, pat, _drives in list(PATTERNS) + list(TRICKY):
                    m = pat.search(obs)
                    if not m:
                        continue
                    counts[label] += 1
                    bucket = examples.setdefault(label, [])
                    if len(bucket) < 3:
                        bucket.append((iid, str(step_i), m.group(0)[:400]))
                if (seen_testish < 4000 and (
                        V._PYTEST_SESSION_HDR.search(obs)
                        or V._UNITTEST_RAN.search(obs)
                        or V._INTERRUPTED.search(obs)
                        or V._SHORT_SUMMARY_ERROR.search(obs))):
                    seen_testish += 1
                    p = V.parse_observation(obs)
                    testish.append((iid, f"parsed={p.exit_signal}", obs.strip()[:900]))
            if n_runs >= args.max_runs:
                stop = True
                break

    print(f"scanned {n_runs} runs / {n_obs} observations in {time.time()-t0:.0f}s", flush=True)
    snippets = pick_diverse(testish, 20)
    print("snippet signals:", Counter(t for _i, t, _o in snippets), flush=True)
    write_doc(args.out, counts, examples, testish, n_runs, n_obs, snippets)
    return 0


def pick_diverse(pool: List[Tuple[str, str, str]], n: int) -> List[Tuple[str, str, str]]:
    """Spread the printed examples across parse outcomes so coverage is visible."""
    by_signal: Dict[str, List[Tuple[str, str, str]]] = {}
    for item in pool:
        by_signal.setdefault(item[1], []).append(item)
    order = sorted(by_signal, key=lambda k: -len(by_signal[k]))
    out: List[Tuple[str, str, str]] = []
    i = 0
    while len(out) < n:
        added = False
        for sig in order:
            if i < len(by_signal[sig]) and len(out) < n:
                out.append(by_signal[sig][i])
                added = True
        if not added:
            break
        i += 1
    return out


def _fence(s: str) -> str:
    s = s.rstrip()
    if "```" in s:
        s = s.replace("```", "'''")
    return s


def write_doc(out: str, counts: Counter, examples: Dict[str, List[Tuple[str, str, str]]],
              testish: List[Tuple[str, str, str]], n_runs: int, n_obs: int,
              snippets: List[Tuple[str, str, str]]) -> None:
    L: List[str] = []
    A = L.append
    A("# Per-step verification parser: evidence from the real corpus")
    A("")
    A("Generated by `scripts/make_verify_evidence.py`; every string below is a literal")
    A("substring captured from `data/raw/nebius/train-*.parquet`.")
    A("")
    A(f"- **Corpus read:** `data/raw/nebius/train-*.parquet` (raw SWE-agent trajectories).")
    A(f"  `data/processed/steps_full/nebius/` was empty while this ran, so it was not used;")
    A(f"  `data/processed/steps/nebius/` has derived features only and carries no observation text.")
    A(f"- **Scan:** {n_runs:,} runs, {n_obs:,} observations.")
    A('- Regexes in `src/agentstall/verify.py` were written from these strings, not from')
    A('  recollection of what pytest/unittest "should" print.')
    A("")
    A("## 1. Patterns driving the parser")
    A("")
    A("| what it is | observations matched | drives |")
    A("|---|---:|---|")
    for label, _pat, drives in PATTERNS:
        A(f"| {label} | {counts.get(label, 0):,} | {drives} |")
    A("")
    A("## 2. Tricky cases the parser must survive")
    A("")
    A("| case | observations matched | why it matters |")
    A("|---|---:|---|")
    for label, _pat, why in TRICKY:
        A(f"| {label} | {counts.get(label, 0):,} | {why} |")
    A("")
    A("## 3. Literal examples per pattern")
    A("")
    for label, pat, drives in list(PATTERNS) + list(TRICKY):
        A(f"### {label}")
        A("")
        A(f"Drives: {drives}")
        A("")
        A(f"Regex: `{pat.pattern}`")
        A("")
        got = examples.get(label) or []
        if not got:
            A("_No occurrence in the scanned sample._")
            A("")
            continue
        for iid, step, piece in got[:2]:
            A(f"- `{iid}` step {step}:")
            A("")
            A("  ```text")
            for ln in _fence(piece).splitlines():
                A("  " + ln)
            A("  ```")
            A("")
    A("## 4. Twenty whole observations that contain test output")
    A("")
    for i, (iid, tag, obs) in enumerate(snippets):
        A(f"### {i+1}. `{iid}` ({tag})")
        A("")
        A("```text")
        A(_fence(obs))
        A("```")
        A("")
    (ROOT / out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(L)} lines)", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
