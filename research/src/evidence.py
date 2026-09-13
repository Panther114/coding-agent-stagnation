"""Evidence and verification extraction from observations.

Two different things are extracted from the observable prefix:

``entities``
    Named things the agent has *seen*: files, functions, error classes, exception
    messages, test names, traceback frames.  An entity is a string plus a type; the
    monitor tracks *when each entity was first observed*, which lets it measure how
    much of a window's information was already known.

``state``
    Objective state variables read out of tool output: exit codes, test-failure
    counts, success markers, error signatures, build status.  Comparing states gives
    a *verification delta*, which is independent of how novel the text looks.

Everything here is deterministic, cheap and reference-free: it never consults the
reference patch, the hidden tests or the final reward.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# --------------------------------------------------------------------------------------
# Regex bank
# --------------------------------------------------------------------------------------

RE_PY_FRAME = re.compile(r'File "([^"]+)", line (\d+), in ([\w<>_.]+)')
RE_PY_EXC = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit|Interrupt|Fault))\b[:\s]*(.*)$", re.M)
RE_PY_EXC_LAST = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception))\b:\s*(.*)$", re.M)
RE_TRACEBACK_HEAD = re.compile(r"^Traceback \(most recent call last\)", re.M)
RE_TEST_FILE_LINE = re.compile(r"^\s*([~_A-Za-z0-9/.\-]+\.(?:py|js|ts|rb|go|rs|java|c|cpp|r)):(\d+):\s*(.*)$", re.M)
RE_PYTEST_TESTID = re.compile(r"^([\w./\-]+\.py)::([\w\[\]\-\.]+)", re.M)
RE_FAILED_LINE = re.compile(r"^(FAILED|ERROR)\s+(\S+)", re.M)
RE_ASSERTION = re.compile(r"^E\s+(?:assert|AssertionError)(.*)$", re.M)
RE_FILE_HEADER = re.compile(r"^\[File:\s*([^\s\]]+)(?:\s*\((\d+)\s+lines?\s+total\))?\]", re.M)
RE_OPEN_FILE = re.compile(r"\(Open file:\s*([^\)]+)\)")
RE_CURRENT_DIR = re.compile(r"\(Current directory:\s*([^\)]+)\)")
RE_PY_M = re.compile(r"^\s*([A-Za-z_][\w.]*)\((.*)\)\s*$", re.M)

RE_EXIT_CODE = re.compile(r"<returncode>(-?\d+)</returncode>")
RE_EXIT_CODE2 = re.compile(r"\bexit(?:\s+code|\s+status)?[:\s=]+(-?\d+)\b", re.I)
RE_CMD_NOT_FOUND = re.compile(r"(?:command not found|not found:|No such file or directory|Permission denied)", re.I)

RE_TEST_TAIL_PYTEST = re.compile(
    r"=+\s*((?:\d+\s+\w+(?:,\s*)?)+)\s*in\s*[\d.]+s.*?=+", re.S)
RE_TEST_COUNT = re.compile(r"(\d+)\s+(passed|failed|error|errors|skipped|xfailed|xpassed|warnings?|deselected|warning)")
RE_NPM_TESTS = re.compile(r"Tests:\s*(.*)$", re.M)
RE_GO_TEST = re.compile(r"^(?:ok|FAIL|---)\s+(\S+)", re.M)
RE_JUNIT = re.compile(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)")

RE_BUILD_OK = re.compile(r"\b(?:Build succeeded|build successful|Successfully built|Compiled successfully|"
                         r"Done\.\s*\d+\s+files?|=== OK|All tests passed)\b", re.I)
RE_BUILD_FAIL = re.compile(r"\b(?:Build FAILED|build failed|error:|fatal error|undefined reference|"
                           r"compilation terminated|=== FAIL)\b", re.I)
RE_SEGFAULT = re.compile(r"\b(?:Segmentation fault|core dumped|SIGSEGV|SIGABRT|Aborted)\b")
RE_TIMEOUT = re.compile(r"\b(?:timed out|timeout|TimeoutError|Killed|deadline exceeded)\b", re.I)
RE_PASS_WORD = re.compile(r"\b(?:PASS|PASSED|passed|OK|SUCCESS|success)\b")
RE_FAIL_WORD = re.compile(r"\b(?:FAIL|FAILED|failed|ERROR|error|Error)\b")

RE_PLAIN_PATH = re.compile(
    r"(?<![\w/])((?:\.{0,2}/)?(?:[\w.+@\-]+/)*[\w.+@\-]+\.(?:py|pyi|r|R|js|mjs|cjs|ts|tsx|jsx|go|rs|c|h|cc|cpp|hpp|"
    r"java|kt|rb|sh|bash|zsh|json|jsonl|ya?ml|toml|ini|cfg|conf|md|rst|txt|csv|tsv|parquet|pkl|npy|npz|sql|html|css|"
    r"xml|proto|ipynb|tex|bib|lock|patch|diff|log|out|err|env|service|mk|cmake|gradle|mod|sum|tpl|j2))(?::(\d+))?")

RE_NUM_METRIC = re.compile(r"\b([\w.\- ]{2,40}?)\s*[:=]\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*%?")

RE_IDENT_BACKTICK = re.compile(r"`([A-Za-z_][\w.]{2,60})`")
RE_IDENT_CALL = re.compile(r"\b([a-z_][a-z0-9_]{2,40})\s*\(")
RE_IDENT_DEF = re.compile(r"^\s*(?:def|class|function|func|fn)\s+([A-Za-z_][\w]{1,60})", re.M)

# --------------------------------------------------------------------------------------
# Entity extraction
# --------------------------------------------------------------------------------------

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "not", "but", "you",
    "your", "are", "was", "were", "will", "would", "should", "could", "can", "may", "might",
    "use", "used", "using", "make", "made", "get", "got", "set", "see", "seen", "let", "lets",
    "file", "files", "line", "lines", "code", "type", "value", "name", "test", "tests",
    "error", "errors", "true", "false", "none", "null", "print", "return", "self", "str",
    "int", "float", "list", "dict", "len", "range", "open", "read", "write", "add",
}


@dataclass
class Entity:
    kind: str      # path | symbol | exception | testid | message | metric
    value: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.value}"


def _norm_path(p: str) -> str:
    p = p.strip().strip("'\"`,;:()[]")
    p = re.sub(r"^\./+", "", p)
    p = re.sub(r"^(/app|/repo|/testbed|/workspace|/home/\w+|/root|/tmp)+/", "", p)
    return p


def _norm_msg(m: str) -> str:
    m = m.strip()
    m = re.sub(r"0x[0-9a-fA-F]+", "0x#", m)
    m = re.sub(r"\b\d+\b", "#", m)
    m = re.sub(r"'[^']*'", "'#'", m)
    m = re.sub(r'"[^"]*"', '"#"', m)
    m = re.sub(r"\s+", " ", m)
    return m[:160]


def extract_entities(text: str, source: str, limit: int = 400) -> List[Entity]:
    """Pull typed entities out of one observation or agent message."""
    if not text:
        return []
    ents: List[Entity] = []
    seen: Set[str] = set()

    def add(kind: str, value: str) -> None:
        if not value:
            return
        e = Entity(kind, value)
        if e.key in seen:
            return
        seen.add(e.key)
        ents.append(e)

    if source == "obs":
        for m in RE_PY_FRAME.finditer(text):
            add("path", _norm_path(m.group(1)))
            add("symbol", m.group(3))
        for m in RE_TEST_FILE_LINE.finditer(text):
            add("path", _norm_path(m.group(1)))
            add("message", _norm_msg(m.group(3)))
        for m in RE_FILE_HEADER.finditer(text):
            add("path", _norm_path(m.group(1)))
        for m in RE_OPEN_FILE.finditer(text):
            v = _norm_path(m.group(1))
            if v and v != "n/a":
                add("path", v)
        for m in RE_CURRENT_DIR.finditer(text):
            add("path", _norm_path(m.group(1)))
        for m in RE_PYTEST_TESTID.finditer(text):
            add("path", _norm_path(m.group(1)))
            add("testid", f"{_norm_path(m.group(1))}::{m.group(2)}")
        for m in RE_FAILED_LINE.finditer(text):
            add("testid", m.group(2)[:120])
        for m in RE_PY_EXC_LAST.finditer(text):
            add("exception", m.group(1).split(".")[-1])
            add("message", _norm_msg(m.group(2))[:120])
        for m in RE_ASSERTION.finditer(text):
            add("message", _norm_msg(m.group(1))[:120])
        for m in RE_GO_TEST.finditer(text):
            add("testid", m.group(1))
        for m in RE_NUM_METRIC.finditer(text):
            k = m.group(1).strip().lower()
            if 2 < len(k) < 40 and not k.isdigit():
                add("metric", f"{k}={m.group(2)}")

    if source in {"obs", "action"}:
        for m in RE_PLAIN_PATH.finditer(text):
            add("path", _norm_path(m.group(1)))

    if source == "action":
        for m in RE_IDENT_DEF.finditer(text):
            add("symbol", m.group(1))

    if source == "agent":
        for m in RE_IDENT_BACKTICK.finditer(text):
            v = m.group(1)
            if len(v) > 2 and not v.isdigit():
                add("symbol", v.split(".")[-1])
        for m in RE_IDENT_DEF.finditer(text):
            add("symbol", m.group(1))

    return ents[:limit]


# --------------------------------------------------------------------------------------
# State extraction
# --------------------------------------------------------------------------------------


@dataclass
class ObsState:
    """Objective state variables read out of one observation."""

    exit_code: Optional[int] = None
    n_passed: Optional[int] = None
    n_failed: Optional[int] = None
    n_error: Optional[int] = None
    n_skipped: Optional[int] = None
    build_ok: Optional[bool] = None
    timed_out: bool = False
    crashed: bool = False
    cmd_missing: bool = False
    error_sig: Optional[str] = None          # normalized terminal exception signature
    failed_ids: Tuple[str, ...] = ()
    passed_ok_marker: bool = False

    def summary(self) -> Dict[str, object]:
        return {
            "exit_code": self.exit_code, "n_passed": self.n_passed, "n_failed": self.n_failed,
            "n_error": self.n_error, "build_ok": self.build_ok, "timed_out": self.timed_out,
            "crashed": self.crashed, "error_sig": self.error_sig, "n_failed_ids": len(self.failed_ids),
        }


def _int_or_none(x) -> Optional[int]:
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def extract_state(obs: str) -> ObsState:
    st = ObsState()
    if not obs:
        return st
    tail = obs[-4000:]

    m = RE_EXIT_CODE.search(tail) or RE_EXIT_CODE2.search(tail)
    if m:
        st.exit_code = _int_or_none(m.group(1))

    # pytest-style summary: "== 3 failed, 10 passed, 1 warning in 2.31s =="
    counts = {k.lower(): int(v) for v, k in RE_TEST_COUNT.findall(tail)}
    if counts:
        st.n_passed = counts.get("passed")
        st.n_failed = (counts.get("failed") or 0) + (counts.get("error") or 0) + (counts.get("errors") or 0) or None
        st.n_error = (counts.get("error") or 0) + (counts.get("errors") or 0) or None
        st.n_skipped = counts.get("skipped")

    m = RE_JUNIT.search(tail)
    if m:
        st.n_passed = _int_or_none(m.group(1))
        st.n_failed = _int_or_none(m.group(2))
        st.n_error = _int_or_none(m.group(3))

    m = re.search(r"(\d+)\s+passing", tail)
    if m and st.n_passed is None:
        st.n_passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failing", tail)
    if m and st.n_failed is None:
        st.n_failed = int(m.group(1))

    failed = [mm.group(2) for mm in RE_FAILED_LINE.finditer(tail)]
    if not failed:
        failed = [f"{mm.group(1)}::{mm.group(2)}" for mm in RE_PYTEST_TESTID.finditer(tail)][:20]
    st.failed_ids = tuple(sorted(set(failed))[:20])

    st.build_ok = True if RE_BUILD_OK.search(tail) else (False if RE_BUILD_FAIL.search(tail) else None)
    st.timed_out = bool(RE_TIMEOUT.search(tail))
    st.crashed = bool(RE_SEGFAULT.search(tail))
    st.cmd_missing = bool(RE_CMD_NOT_FOUND.search(tail))

    excs = RE_PY_EXC_LAST.findall(tail)
    if excs:
        cls, msg = excs[-1]
        st.error_sig = f"{cls.split('.')[-1]}:{_norm_msg(msg)[:80]}"
    elif st.crashed:
        st.error_sig = "SIGSEGV"
    elif st.timed_out:
        st.error_sig = "TIMEOUT"

    # R / JS / shell failure markers
    if st.error_sig is None:
        m = re.search(r"^\s*(?:Error in|Error):\s*(.*)$", tail, re.M)
        if m:
            st.error_sig = "Error:" + _norm_msg(m.group(1))[:80]

    st.passed_ok_marker = bool(
        re.search(r"\b(?:ALL TESTS PASSED|all tests passed|Test.*PASS|PASS\b|OK\b)\b", tail)
        and not re.search(r"\b(?:FAIL|failed|Error)\b", tail)
    )
    return st


# --------------------------------------------------------------------------------------
# Relevance
# --------------------------------------------------------------------------------------


def task_terms(statement: str) -> Set[str]:
    """Content words of the task statement, used as the reference-free relevance prior."""
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", (statement or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def relevance(values: Iterable[str], terms: Set[str], idf: Optional[Dict[str, float]] = None) -> float:
    """Fraction of an entity's tokens that appear in the task statement (0..1)."""
    tot, hit = 0.0, 0.0
    for v in values:
        toks = [t for t in re.split(r"[^A-Za-z0-9_]+", v.lower()) if t]
        for t in toks:
            if len(t) < 3:
                continue
            w = 1.0 if idf is None else (1.0 + idf.get(t, 0.0))
            tot += w
            if t in terms:
                hit += w
    return (hit / tot) if tot > 0 else 0.0
