"""Per-step test-outcome extraction from agent observations.

Motivation
----------
The study's central claim is that an edit's eventual wastefulness is *not* visible
in the observable channel.  The one channel that could falsify that claim is
**per-step test outcomes**: if every step told us whether the project's suite
passed, the monitor would have a direct signal and the claim would be dead.

This module recovers that signal from raw observation text, or reports honestly
that it is not there.  It never guesses an outcome it cannot read.

What the corpus actually contains
---------------------------------
Every pattern below was derived from literal observations of
``data/raw/nebius/train-*.parquet`` (see ``docs/VERIFY_PARSER_EVIDENCE.md``).
Two scaffold behaviours dominate and both bound what is recoverable:

1. **SWE-agent observations are head-truncated.**  The harness keeps the *first*
   N characters and discards the tail.  pytest writes its terminal summary
   (``===== 3 failed, 12 passed in 0.42s =====``) at the *very end* of the run,
   so a large suite's verdict is frequently cut off.  unittest is luckier: it
   prints ``Ran 54 tests in 1.038s`` / ``OK (skipped=6)`` to stderr, which often
   survives.  Legitimate recovery rate is therefore much higher for unittest
   runs than for pytest runs, and that asymmetry is a finding, not a bug.
2. **A truncated pytest run still shows progress.**  Lines like
   ``tests/x_test.py ..FF....    [ 51%]`` prove tests ran but carry no verdict.
   These are reported as ``exit_signal="unknown"`` with ``has_progress=True``
   and are *not* counted toward coverage.

Design rules
------------
* Regex derivation only -- no model calls, no heuristics that invent a number.
* ``unknown`` is a first-class answer and is never silently upgraded.
* The matched substring is always returned in ``raw_matches`` for auditability.
* ``new_failure_ids`` separates "my edit broke this test" from "this test was
  already failing": the same node id failing twice is not a new regression.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

__all__ = [
    "EXIT_ALL_PASS",
    "EXIT_SOME_FAIL",
    "EXIT_ERROR",
    "EXIT_COLLECTION_ERROR",
    "EXIT_NO_TESTS",
    "EXIT_UNKNOWN",
    "EXIT_SIGNALS",
    "StepVerification",
    "canonical_test_id",
    "extract_failure_ids",
    "ObservationParse",
    "parse_observation",
    "RunVerificationTracker",
]

# --------------------------------------------------------------------------------------
# exit signals
# --------------------------------------------------------------------------------------

EXIT_ALL_PASS = "all_pass"
EXIT_SOME_FAIL = "some_fail"
EXIT_ERROR = "error"
EXIT_COLLECTION_ERROR = "collection_error"
EXIT_NO_TESTS = "no_tests"
EXIT_UNKNOWN = "unknown"

EXIT_SIGNALS = (
    EXIT_ALL_PASS,
    EXIT_SOME_FAIL,
    EXIT_ERROR,
    EXIT_COLLECTION_ERROR,
    EXIT_NO_TESTS,
    EXIT_UNKNOWN,
)

# severity order used to reconcile two independent readings of one observation
_SEVERITY = {
    EXIT_UNKNOWN: 0,
    EXIT_NO_TESTS: 1,
    EXIT_ALL_PASS: 2,
    EXIT_COLLECTION_ERROR: 3,
    EXIT_ERROR: 4,
    EXIT_SOME_FAIL: 5,
}

# --------------------------------------------------------------------------------------
# Count-vocabulary
#
# Real terminal lines observed verbatim in the corpus:
#
#   ========================= 1 failed, 17 passed in 0.23s =========================
#   ======================== 1 passed, 4 warnings in 0.15s =========================
#   ================= 1 passed, 54 deselected, 4 warnings in 0.64s =================
#   =============== 1 failed, 3 passed, 3 warnings in 0.25s ====================
#   ============================== 1 skipped in 0.16s ==============================
#   ================ 3 passed, 12 deselected, 3 warnings in 0.09s ==================
#   =============================== 1 error in 0.64s ===============================
#   =========================== no tests ran in 0.01s ==============================
#   ========================= 1 failed, 12 passed, 4 warnings in 0.51s =============
#   FAILED (failures=4, errors=9, skipped=3, expected failures=1)
#   OK (skipped=6)
#   Ran 54 tests in 1.038s
#   ERROR tests/providers/test_memset.py
#   collected 0 items / 1 error
#   !!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
#   FAILED tests/test_setup_profile.py::test_no_keypair_provided - RuntimeError: ...
#   ERROR: test_mock.TestMock.test_foo (nose2.loader.LoadTestsFailure)
# --------------------------------------------------------------------------------------

# pytest counts, longest phrase first so `expected failures` cannot be read as `failures`
_PYTEST_PHRASE = re.compile(
    r"\d+\s+(?:expected\s+failures?|xfails?|xpasses?|unexpected\s+passes?"
    r"|failed|failures?|errors?|passed|passes|skipped|deselected|warnings?|warning)",
    re.I,
)

# A pytest terminal block is a fully-separated line: `===== <outcome> =====`.  The
# separator must balance, which is what keeps ordinary output containing the word
# `failed` from ever being read as a summary.  Both the timed form
# (`2 failed, 18 passed in 0.74s`) and the bare form (`1 failed, 5 passed`) occur.
_PYTEST_TERMINAL = re.compile(
    r"^(?P<line>=+)\s*(?P<body>[^\n=][^\n=]*?)\s*(?P=line)\s*$",
    re.M,
)
_PYTEST_IN_TIME_OR_BARE = re.compile(
    r"(?:\bin\s+\d+(?:\.\d+)?s\b"
    r"|\bno tests ran\b"
    r"|\A\s*\d+\s+[A-Za-z]"
    r"|(?<=\n)\s*\d+\s+[A-Za-z])", re.I)
_PYTEST_SUMMARY_TAIL = re.compile(
    r"^=+ .*?(?:\bin\s+\d+(?:\.\d+)?s\b|no tests ran).*? =+$", re.I | re.M)
_PYTEST_SUMMARY_NOSTAR = re.compile(
    r"^[=!]{2,} [^\n=]*?\b(?:\d+\s+(?:passed|failed|errors?|skipped)|no tests ran)\b"
    r"[^\n=]*? in \d+(?:\.\d+)?s[^\n=]*$",
    re.I | re.M)
# `=== short test summary info ===` header, used only as an evidence marker
_PYTEST_SHORT_HDR = re.compile(r"^=+ short test summary info =+$", re.M)

_COUNT_WORDS: Tuple[Tuple[str, str], ...] = (
    ("expected failures", "xfail"),
    ("expected failure", "xfail"),
    ("unexpected passes", "xpass"),
    ("unexpected pass", "xpass"),
    ("xfails", "xfail"),
    ("xpasses", "xpass"),
    ("failures", "failed"),
    ("failure", "failed"),
    ("failed", "failed"),
    ("errors", "error"),
    ("error", "error"),
    ("passed", "passed"),
    ("passes", "passed"),
    ("skipped", "skipped"),
    ("deselected", "deselected"),
    ("warnings", "warning"),
    ("warning", "warning"),
)
_PYTEST_COUNT = re.compile(r"(\d+)\s+([A-Za-z][A-Za-z ]*?)(?=,|$|\s+in\s)", re.I)

# unittest counts
_UNITTEST_OK = re.compile(r"^OK(?: \((?P<body>[^)]*)\))?\s*$", re.M)
_UNITTEST_FAILED = re.compile(r"^FAILED \((?P<body>[^)]*)\)\s*$", re.M)
_UNITTEST_RAN = re.compile(r"^Ran (?P<n>\d+) tests? in (?P<secs>\d+(?:\.\d+)?)s\s*$", re.M)
_UNITTEST_OUTCOME_WORD = r"failures?|errors?|skipped|expected\s+failures?|unexpected\s+successes?"
# unittest writes its counts as `kind=N` inside the parentheses of `FAILED (...)`,
# which is the opposite order from pytest's `N failed`.  Both are tried, keyword
# first, so that `failures=4` is never mistaken for a pytest-style count.
_UNITTEST_KV = re.compile(
    r"(?:(?P<kw>" + _UNITTEST_OUTCOME_WORD + r")\s*=\s*(?P<n1>\d+))"
    r"|(?:(?P<n2>\d+)\s+(?P<num>" + _UNITTEST_OUTCOME_WORD + r"))",
    re.I,
)
# --------------------------------------------------------------------------------------
# harness-level failure signals
# --------------------------------------------------------------------------------------

# `collected 0 items / 1 error`, `collected 3 items / 2 errors`
_COLLECTED_WITH_ERR = re.compile(r"collected\s+(?P<n>\d+)\s+items?\s*/\s*(?P<e>\d+)\s+errors?", re.I)
# `collected 20 items`
_COLLECTED = re.compile(r"collected\s+(?P<n>\d+)\s+items?\b", re.I)
# `!!!!!!!! Interrupted: 1 error during collection !!!!!!!!`
_INTERRUPTED = re.compile(r"!{3,}\s*Interrupted:\s*(?P<n>\d+)\s+errors?\s+during\s+collection", re.I)
# `============== 1 error in 0.64s ==============` (pytest, non-collection form)
_ERROR_IN_TIME = re.compile(r"\b(?P<n>\d+)\s+errors?\s+in\s+\d+(?:\.\d+)?s\b", re.I)
_NO_TESTS_RAN = re.compile(r"\bno tests ran\b", re.I)
_PYTEST_SESSION_HDR = re.compile(r"=+ test session starts =+", re.I)

# module-level collection failures reported by the short summary
_SHORT_SUMMARY_ERROR = re.compile(r"^ERROR\s+(?P<nid>[^\s(][^\s]*)\s*$", re.M)
# nose2's loader failure: `ERROR: <broken module> (nose2.loader.LoadTestsFailure)`.
# The parenthesised part is a *loader* class, never a test path, so the name is the
# only usable identifier.
_NOSE2_FAILEDTEST = re.compile(
    r"^ERROR:\s+(?P<what>[A-Za-z_][\w.]*)\s+\((?P<cls>[^)]*[Ll]oader[^)]*|[^)]*_FailedTest[^)]*)\)\s*$",
    re.M,
)
# `ERROR: <name> (<dotted.test.path>)` -- a unittest/nose2 test-level error banner
_UNITTEST_ERROR_ID = re.compile(r"^ERROR:\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<path>[^)]*)\)\s*$", re.M)

# --------------------------------------------------------------------------------------
# test identifiers (node ids)
# --------------------------------------------------------------------------------------

# pytest short-summary prefixes.  The node id that follows may contain spaces and
# ` - ` inside a parametrisation (`[with spaces-in id]`, `['a', 'b']`), so it is
# extracted by a scanner rather than a single regex -- see ``_short_summary_id``.
_FAILED_PREFIX = re.compile(r"^(?:FAILED|ERROR)[ \t]+(?P<rest>\S.*)$")
# unittest failure banners: `FAIL: test_all (tests.test_x.TestX)`
_UNITTEST_FAIL_ID = re.compile(r"^(?:FAIL|ERROR):\s+(?P<name>\S+)\s*\((?P<path>[^)]*)\)\s*$", re.M)
# the same `name (dotted.path)` pair with the banner prefix already stripped
_UNITTEST_BARE_ID = re.compile(r"^(?P<name>[A-Za-z_]\w*)\s*\((?P<path>[A-Za-z_][\w.]*)\)\s*$")
# pytest collection header: `______ ERROR collecting tests/providers/test_memset.py ______`
_COLLECTING_ID = re.compile(r"^_+\s*ERROR collecting\s+(?P<nid>\S+?)\s*_+\s*$", re.M)

# a node-id *prefix* is a path-like token; used to validate split points
_ID_PREFIX_OK = re.compile(r"^[\w./\\\-]+$")
# a node id must look like a path, not prose
_ID_OK = re.compile(r"(?:[/\\]|::|\.py\b|\.js\b|\.go\b|\.rb\b|\.java\b|\.ts\b)")
# pytest-style parameters appended to a node id: [1], [add_repeated], [with spaces-in id]
_PARAM = re.compile(r"\[[^\[\]\n]{1,80}\]\s*$")


def _short_summary_id(line: str) -> Optional[str]:
    """Pull the node id out of one `FAILED <id> - <message>` / `ERROR <id>` line.

    The id is read left-to-right and stops at the first `" - "` that is *outside* a
    parameter bracket.  That keeps ``...::test_x[with spaces-in id]`` whole while
    still dropping `` - AssertionError: ...`` from ``...::test_one - AssertionE...``.
    """
    m = _FAILED_PREFIX.match(line.strip())
    if not m:
        return None
    rest = m.group("rest").strip()
    if not rest:
        return None
    depth = 0
    i = 0
    n = len(rest)
    while i < n:
        ch = rest[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(depth - 1, 0)
        elif depth == 0 and rest.startswith(" - ", i):
            return rest[:i].strip() or None
        i += 1
    return rest



def canonical_test_id(raw: str) -> Optional[str]:
    """Normalise a raw test identifier to one comparable form.

    ``FAIL: test_all (tests.test_aggregations.TestBooleanAggregation)`` and
    ``tests/test_aggregations.py::TestBooleanAggregation::test_all`` are the same
    test reported by unittest and by pytest.  Both become the latter so that
    ``new_failure_ids`` does not count a change of reporter as a new regression.

    Returns ``None`` when the text is not an identifier (prose, a bare word).
    """
    if not raw:
        return None
    s = raw.strip().strip("_-").strip()
    s = re.sub(r"^[|`'\"\s]+|['\"\s]+$", "", s)
    if not s:
        return None

    m = _UNITTEST_FAIL_ID.match(s) or _UNITTEST_BARE_ID.match(s) or _NOSE2_FAILEDTEST.match(s)
    if m:
        name = m.group("name")
        path = m.group("path")
        # for nose2 the parenthesis holds a loader class, not a test path
        if "." in path or "/" in path:
            parts = [p for p in path.split(".") if p]
            if len(parts) >= 2:
                module = ".".join(parts[:-1])
                cls = parts[-1]
                if cls[:1].isupper():
                    return f"{module.replace('.', '/')}.py::{cls}::{name}"
                return f"{module.replace('.', '/')}.py::{name}"
            return f"{parts[0].replace('.', '/')}.py::{name}" if parts else None
        return None

    if not _ID_OK.search(s):
        return None
    s = re.sub(r"\s*[({\[]\d+[%)}\]]\s*$", "", s)
    s = re.sub(r"^[|`'\"\s]+|['\"\s]+$", "", s)
    s = re.sub(r"\s*-\s*$", "", s)
    # keep the whole id: only trim a trailing parenthesised *note*, and only when
    # nothing that could belong to the id follows it
    s = re.sub(r"\s*\([^()]*\)\s*$", "", s) if "::" not in s else s
    s = s.strip(": ")
    if not s:
        return None
    if not s:
        return None
    # a bare dotted path like `tests.unittests.test_dispatcher` is a module, not a test
    if "/" not in s and "::" not in s and "." in s and not s.endswith(".py"):
        head = s.split(".")[0]
        if head not in ("test", "tests"):
            return None
    return s


def extract_failure_ids(obs: str) -> List[str]:
    """Every test node id that an observation reports as failing or erroring.

    Order-preserving and de-duplicated.  pytest ids and unittest banners are read
    independently because a single observation can legitimately contain both (a
    suite run through both reporters, or a truncated section of each).
    """
    out: List[str] = []
    seen: Set[str] = set()

    def push(id_raw: str) -> None:
        cid = canonical_test_id(id_raw)
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)

    short_summary = False
    for line in obs.splitlines():
        if not _FAILED_PREFIX.match(line.strip()):
            continue
        nid = _short_summary_id(line)
        if not nid:
            continue
        cid = canonical_test_id(nid)
        if cid is None:
            continue
        # `FAIL: test_x (tests.a.b.C)` also starts with the FAILED/ERROR prefix; requiring
        # a path-like id keeps it out of the pytest branch
        short_summary = True
        if cid not in seen:
            seen.add(cid)
            out.append(cid)

    for m in _COLLECTING_ID.finditer(obs):
        push(m.group("nid"))

    # unittest/nose2 banners are always read: an `ERROR: test_x (path)` line is a real
    # failing test even when the same observation also carries a pytest short summary,
    # and `ERROR: x (Loader)` lines are filtered out by the loader check below.
    loader_lines = {m.group(0).strip() for m in _NOSE2_FAILEDTEST.finditer(obs)}
    for m in _UNITTEST_FAIL_ID.finditer(obs):
        if m.group(0).strip() in loader_lines:
            continue              # `tests (unittest.loader._FailedTest)`: a loader, not a test
        if not m.group("name").startswith("test_"):
            continue
        push(m.group("name") + " (" + m.group("path") + ")")
    return out


# --------------------------------------------------------------------------------------
# parse result
# --------------------------------------------------------------------------------------


@dataclass
class ObservationParse:
    """What one observation says about test outcomes."""

    n_tests_passed: Optional[int] = None
    n_tests_failed: Optional[int] = None
    n_tests_errored: Optional[int] = None
    n_tests_skipped: Optional[int] = None
    n_collected: Optional[int] = None
    exit_signal: str = EXIT_UNKNOWN
    source: str = "none"          # pytest | unittest | none
    raw_matches: List[str] = field(default_factory=list)
    failure_ids: List[str] = field(default_factory=list)
    has_progress: bool = False    # progress dots/fractions prove tests ran, no verdict
    has_test_evidence: bool = False
    truncated: bool = False

    @property
    def has_failure(self) -> bool:
        return bool(self.n_tests_failed) or bool(self.n_tests_errored)

    @property
    def has_pass(self) -> bool:
        return bool(self.n_tests_passed)

    @property
    def resolved(self) -> bool:
        """True when a verdict was recovered (i.e. the step counts toward coverage)."""
        return self.exit_signal != EXIT_UNKNOWN

    @property
    def n_tests_total(self) -> Optional[int]:
        """Observed denominator: pytest prints one, unittest only prints a count."""
        if self.n_collected is not None:
            return self.n_collected
        parts = [self.n_tests_passed, self.n_tests_failed, self.n_tests_errored]
        if any(p is not None for p in parts):
            return sum(p or 0 for p in parts)
        return None


_PROGRESS_PCT = re.compile(r"\[\s*\d+%\]")
# pytest prints `file.py ....F..` next to the path.  A bare line of dots is not enough:
# ordinary command output (a file listing, a directory tree) also ends in `.py` or `.sh`,
# so the test-result glyphs must be the whole rest of the line.
_PROGRESS_LINE = re.compile(r"^\s*\S*(?:\.py|\.js|\.ts|\.go|\.rb|\.java|\.rs|\.c|\.cpp)\b"
                            r"[ \t]+[.sSxXFE]{2,}\s*(?:\[\s*\d+%\]\s*)?$", re.M)


def _read_progress(obs: str) -> bool:
    """Evidence that tests ran even though no verdict is present.

    `[ 51%]` is pytest's own progress meter and cannot come from anything else; a
    `<test file> ....F..` line is the other shape.  Deliberately narrow -- this flag
    is what makes `unknown` interpretable, so a false positive would overstate how
    much the corpus actually knows.
    """
    if _PROGRESS_PCT.search(obs):
        return True
    return bool(_PROGRESS_LINE.search(obs))


def _unittest_counts(body: str) -> Dict[str, int]:
    """`failures=4, errors=9, skipped=3, expected failures=1` -> canonical counts."""
    out: Dict[str, int] = {}
    for m in _UNITTEST_KV.finditer(body):
        kind = (m.group("kw") or m.group("num") or "").lower()
        n = int(m.group("n1") or m.group("n2"))
        kind = re.sub(r"\s+", " ", kind)
        if kind.startswith("failure"):
            key = "failed"
        elif kind.startswith("error"):
            key = "error"
        elif kind.startswith("expected"):
            key = "xfail"
        elif kind.startswith("unexpected"):
            key = "xpass"
        else:
            key = "skipped"
        out[key] = out.get(key, 0) + n
    return out


def _parse_counts(body: str) -> Dict[str, int]:
    """`1 failed, 17 passed, 4 warnings` -> {'failed': 1, 'passed': 17, 'warning': 4}."""
    out: Dict[str, int] = {}
    for m in _PYTEST_COUNT.finditer(body):
        n = int(m.group(1))
        phrase = re.sub(r"\s+", " ", m.group(2).strip().lower())
        kind = None
        for word, canon in _COUNT_WORDS:
            if phrase == word or phrase == word + "s" or phrase.rstrip("s") == word.rstrip("s"):
                kind = canon
                break
        if kind is None:
            # tolerate trailing adjectives, e.g. `4 warnings`
            for word, canon in _COUNT_WORDS:
                if phrase.endswith(word):
                    kind = canon
                    break
        if kind is None:
            continue
        out[kind] = out.get(kind, 0) + n
    return out


def _read_pytest(obs: str) -> Optional[ObservationParse]:
    """Read a pytest terminal summary.  Returns None when there is no verdict."""
    candidates: List[Tuple[str, str]] = []
    for m in _PYTEST_TERMINAL.finditer(obs):
        body = m.group("body")
        if not body:
            continue
        if _PYTEST_IN_TIME_OR_BARE.search(body):
            if _PYTEST_PHRASE.search(body) or _NO_TESTS_RAN.search(body):
                candidates.append((m.group(0), body))
    if not candidates:
        for m in _PYTEST_SUMMARY_TAIL.finditer(obs):
            candidates.append((m.group(0), m.group(0).strip("= ")))
        for m in _PYTEST_SUMMARY_NOSTAR.finditer(obs):
            candidates.append((m.group(0), m.group(0)))
    if not candidates:
        return None

    # the terminal block is the last thing pytest prints; if several appear, use the last
    line, body = candidates[-1]
    counts = _parse_counts(body)
    p = ObservationParse(source="pytest")
    p.raw_matches.append(line.strip())
    p.n_tests_passed = counts.get("passed")
    p.n_tests_failed = counts.get("failed")
    p.n_tests_errored = counts.get("error")
    p.n_tests_skipped = counts.get("skipped")
    p.has_test_evidence = True

    n_collected, n_coll_err = _read_collected(obs)
    p.n_collected = n_collected

    if n_coll_err:
        p.exit_signal = EXIT_COLLECTION_ERROR
    elif _NO_TESTS_RAN.search(body):
        p.exit_signal = EXIT_NO_TESTS
    elif n_collected == 0 and not (p.n_tests_passed or p.n_tests_failed or p.n_tests_errored):
        p.exit_signal = EXIT_NO_TESTS
    elif p.n_tests_failed:
        p.exit_signal = EXIT_SOME_FAIL
    elif p.n_tests_errored:
        # pytest reports a module-level error as `1 error` -- that is a collection error
        p.exit_signal = EXIT_COLLECTION_ERROR if _is_collection_style(obs) else EXIT_ERROR
    elif p.n_tests_passed:
        p.exit_signal = EXIT_ALL_PASS
    elif p.n_tests_skipped and not p.n_tests_failed and not p.n_tests_errored:
        # `1 skipped in 0.16s` -- nothing ran; not a pass in any useful sense
        p.exit_signal = EXIT_NO_TESTS
    else:
        p.exit_signal = EXIT_UNKNOWN
    return p


def _is_collection_style(obs: str) -> bool:
    return bool(_INTERRUPTED.search(obs) or _COLLECTING_ID.search(obs)
                or re.search(r"^=+ ERRORS =+$", obs, re.M))


def _read_collected(obs: str) -> Tuple[Optional[int], bool]:
    """`collected N items[/ M errors]` -> (N, had_errors)."""
    m = _COLLECTED_WITH_ERR.search(obs)
    if m:
        return int(m.group("n")), int(m.group("e")) > 0
    m = _COLLECTED.search(obs)
    if m:
        return int(m.group("n")), False
    return None, False


def _read_unittest(obs: str) -> Optional[ObservationParse]:
    """Read `Ran N tests` + `OK`/`FAILED (...)` from unittest/tox output."""
    ran = _UNITTEST_RAN.search(obs)
    ok = _UNITTEST_OK.search(obs)
    failed = _UNITTEST_FAILED.search(obs)
    progress = _read_progress(obs)

    if ran is None and ok is None and failed is None:
        return None

    p = ObservationParse(source="unittest")
    p.has_test_evidence = True
    n_ran = int(ran.group("n")) if ran else None
    p.n_collected = n_ran

    body = ""
    verdict_ok = False
    verdict_failed = False
    if ok is not None:
        verdict_ok = True
        body = ok.group("body") or ""
        p.raw_matches.append(ok.group(0).strip())
    elif failed is not None:
        verdict_failed = True
        body = failed.group("body") or ""
        p.raw_matches.append(failed.group(0).strip())
    if ran is not None:
        p.raw_matches.append(ran.group(0).strip())

    counts = _unittest_counts(body)

    p.n_tests_failed = counts.get("failed", 0) if verdict_failed else 0
    p.n_tests_errored = counts.get("error", 0) if verdict_failed else 0
    p.n_tests_skipped = counts.get("skipped", 0) or None

    if verdict_ok:
        # OK with no counts and Ran 0 tests is not a pass
        if n_ran == 0:
            p.exit_signal = EXIT_NO_TESTS
        else:
            n_bad = p.n_tests_failed + p.n_tests_errored
            n_skip = counts.get("skipped", 0)
            p.n_tests_passed = max((n_ran or 0) - n_bad - n_skip, 0) if n_ran is not None else None
            if p.n_tests_passed == 0 and n_ran is None:
                p.exit_signal = EXIT_UNKNOWN
            else:
                p.exit_signal = EXIT_ALL_PASS
    elif verdict_failed:
        p.n_tests_passed = None
        p.exit_signal = EXIT_SOME_FAIL
        if _NOSE2_FAILEDTEST.search(obs) and p.n_tests_failed == 0 and p.n_tests_errored == 0:
            p.exit_signal = EXIT_ERROR
    elif progress:
        # `Ran N tests` with the verdict line truncated away: tests DID run, but the
        # outcome is not in the observation.  Report honestly.
        p.exit_signal = EXIT_UNKNOWN
        p.has_progress = True
    else:
        p.exit_signal = EXIT_UNKNOWN
    return p


def _read_errors_only(obs: str) -> Optional[ObservationParse]:
    """Signals with no count line but a definite failure: short-summary ERROR lines,
    nose2 `_FailedTest`, `Interrupted: N errors during collection`."""
    p = ObservationParse()
    n_collected, n_coll_err = _read_collected(obs)
    interrupted = _INTERRUPTED.search(obs)
    short_err = _SHORT_SUMMARY_ERROR.search(obs)
    nose2 = _NOSE2_FAILEDTEST.search(obs)
    unitt_err = _UNITTEST_ERROR_ID.search(obs)

    if n_coll_err or interrupted or (short_err and _is_collection_style(obs)):
        p.source = "pytest"
        p.exit_signal = EXIT_COLLECTION_ERROR
        p.n_collected = n_collected
        p.has_test_evidence = True
        for m in (_COLLECTED_WITH_ERR.search(obs), interrupted):
            if m:
                p.raw_matches.append(m.group(0).strip())
        return p
    if short_err:
        p.source = "pytest"
        p.exit_signal = EXIT_ERROR
        p.n_collected = n_collected
        p.has_test_evidence = True
        p.raw_matches.append(short_err.group(0).strip())
        return p
    if nose2:
        p.source = "unittest"
        p.exit_signal = EXIT_ERROR
        p.n_tests_errored = 1
        p.has_test_evidence = True
        p.raw_matches.append(nose2.group(0).strip())
        return p
    if unitt_err and unitt_err.group("name").startswith("test_") and "." not in unitt_err.group("name"):
        p.source = "unittest"
        p.exit_signal = EXIT_SOME_FAIL
        p.n_tests_errored = 1
        p.has_test_evidence = True
        p.raw_matches.append(unitt_err.group(0).strip())
        return p
    m = _ERROR_IN_TIME.search(obs)
    if m and _PYTEST_SESSION_HDR.search(obs):
        p.source = "pytest"
        p.exit_signal = EXIT_COLLECTION_ERROR
        p.n_collected = n_collected
        p.has_test_evidence = True
        p.raw_matches.append(m.group(0).strip())
        return p
    return None


_FOOTER = re.compile(r"\n?\((?:Open|Current) (?:file|directory):[^\n]*\)\s*")
_BASHPROMPT = re.compile(r"\n?bash-\$\s*$")


def _verdict_present(body: str) -> bool:
    """Cheap check for any terminal summary; used only by ``_is_truncated``.

    Delegates to the real readers rather than a separate regex, so "is there a
    verdict" can never disagree with what ``parse_observation`` actually recovered.
    """
    if _read_pytest(body) is not None:
        return True
    uni = _read_unittest(body)
    if uni is not None and uni.resolved:
        return True
    return _read_errors_only(body) is not None


def _is_truncated(obs: str) -> bool:
    """Whether a test run is visible here but its verdict never is.

    SWE-agent appends its ``(Open file: ...)`` / ``bash-$`` footer *after* producing
    the text, so the footer proves nothing either way.  What does show through is the
    stopping point: the pytest progress stream and the terminal summary are written at
    different times, so an observation that shows progress *and* shows no summary had
    its tail withheld.

    This is the flag that makes ``unknown`` interpretable -- it separates "the harness
    did not show me the verdict" from "no tests were involved at all".  It is
    deliberately *not* a general "was this output clipped" flag: a clipped observation
    whose verdict survived further up is a perfectly good observation, so flagging it
    would confuse rather than inform.
    """
    if not obs:
        return False
    body = _BASHPROMPT.sub("", _FOOTER.sub("", obs))
    if _verdict_present(body):
        return False
    return _read_progress(body)


def parse_observation(obs: str) -> ObservationParse:
    """Read every recoverable test outcome from one observation string.

    pytest and unittest readings are merged by severity: an observation can contain
    a unittest run followed by a pytest run, or a truncated block of each.
    """
    if not obs:
        return ObservationParse(exit_signal=EXIT_UNKNOWN)

    parts = [p for p in (_read_pytest(obs), _read_unittest(obs), _read_errors_only(obs)) if p is not None]
    ids = extract_failure_ids(obs)
    progress = _read_progress(obs)
    if not parts:
        p = ObservationParse(exit_signal=EXIT_UNKNOWN)
        p.has_test_evidence = bool(_PYTEST_SESSION_HDR.search(obs)) or progress
        p.has_progress = progress
        p.truncated = _is_truncated(obs)
        p.n_collected = _read_collected(obs)[0]
        p.failure_ids = ids
        if ids:
            # failing ids with no summary at all: a definite failure is still a signal
            p.exit_signal = EXIT_SOME_FAIL
            p.n_tests_failed = len(ids)
        return p

    def _rank(q: ObservationParse) -> Tuple[int, int, int]:
        n_counts = sum(x is not None for x in
                       (q.n_tests_passed, q.n_tests_failed, q.n_tests_errored, q.n_tests_skipped))
        return (_SEVERITY[q.exit_signal], int(q.has_test_evidence), n_counts)

    best = max(parts, key=_rank)
    best.has_test_evidence = True
    for q in parts:
        if q is best:
            continue
        # merge counts only when they do not contradict
        if best.n_tests_passed is None:
            best.n_tests_passed = q.n_tests_passed
        if best.n_tests_failed is None:
            best.n_tests_failed = q.n_tests_failed
        if best.n_tests_errored is None:
            best.n_tests_errored = q.n_tests_errored
        if best.n_tests_skipped is None:
            best.n_tests_skipped = q.n_tests_skipped
        if best.n_collected is None:
            best.n_collected = q.n_collected
        for rm in q.raw_matches:
            if rm not in best.raw_matches:
                best.raw_matches.append(rm)

    for k, v in (("n_tests_failed", best.n_tests_failed),
                 ("n_tests_errored", best.n_tests_errored)):
        if not v and ids:
            # a verdict that says tests failed while naming none is a reading gap, not a
            # pass: fill the count from the named ids so `has_failure` stays consistent.
            setattr(best, k, len(ids))
            break
    best.failure_ids = ids
    best.has_progress = progress
    best.truncated = _is_truncated(obs)
    return best


# --------------------------------------------------------------------------------------
# per-run sequence tracking
# --------------------------------------------------------------------------------------


@dataclass
class StepVerification:
    """Result for one (run, step)."""

    step: int
    n_tests_passed: Optional[int]
    n_tests_failed: Optional[int]
    n_tests_errored: Optional[int]
    n_collected: Optional[int]
    has_failure: bool
    has_pass: bool
    test_exit_signal: str
    new_failure_ids: List[str]
    prev_failure_ids: List[str]
    failure_ids: List[str]
    raw_matches: List[str]
    n_tests_skipped: Optional[int] = None
    source: str = "none"
    has_test_evidence: bool = False
    has_progress: bool = False
    truncated: bool = False

    @property
    def has_test_obs(self) -> bool:
        """A recoverable outcome exists at this step."""
        return self.test_exit_signal != EXIT_UNKNOWN


class RunVerificationTracker:
    """Streaming state machine: feed one run's observations in step order.

    ``new_failure_ids`` is the set-theoretic difference between this step's failing
    ids and those of the **most recent step that reported any outcome**.  That is
    the quantity that separates "my edit broke a test" from "this test was already
    failing" -- a test that fails again at the next step is not news.
    """

    def __init__(self) -> None:
        self._prev_failure_ids: Set[str] = set()
        self._prev_resolved = False

    def reset(self) -> None:
        self._prev_failure_ids = set()
        self._prev_resolved = False

    def add(self, step: int, obs: str) -> StepVerification:
        p = parse_observation(obs)
        cur = set(p.failure_ids)
        if p.resolved or cur:
            if not self._prev_resolved:
                new_ids = cur
            else:
                new_ids = cur - self._prev_failure_ids
        else:
            new_ids = set()
        rec = StepVerification(
            step=step,
            n_tests_passed=p.n_tests_passed,
            n_tests_failed=p.n_tests_failed,
            n_tests_errored=p.n_tests_errored,
            n_collected=p.n_collected,
            has_failure=p.has_failure or (p.exit_signal == EXIT_COLLECTION_ERROR),
            has_pass=p.has_pass,
            test_exit_signal=p.exit_signal,
            new_failure_ids=sorted(new_ids),
            prev_failure_ids=sorted(self._prev_failure_ids if self._prev_resolved else ()),
            failure_ids=sorted(cur),
            raw_matches=p.raw_matches[:4],
            n_tests_skipped=p.n_tests_skipped,
            source=p.source,
            has_test_evidence=p.has_test_evidence,
            has_progress=p.has_progress,
            truncated=p.truncated,
        )
        if p.resolved or cur:
            self._prev_failure_ids = cur
            self._prev_resolved = True
        return rec

    def add_many(self, observations: Sequence[str]) -> List[StepVerification]:
        return [self.add(i, o) for i, o in enumerate(observations)]
