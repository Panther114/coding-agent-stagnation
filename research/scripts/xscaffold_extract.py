"""Extract a step table from each cross-scaffold corpus, using the *same* instrument
definitions as the frozen SWE-agent study.

Nothing here decides anything about the agent.  For every corpus it produces

* one row per agent step, with the fields the study's monitor uses
  (``obs`` shape, test outcome, exit code) plus the fields the three-class edit
  taxonomy needs (``file``, ``added_hashes``),
* one row per run, with the agent's own final patch reduced to
  (added-line hashes, touched basenames).

Conventions are copied from ``src/agentstall/corpus.py`` and
``scripts/analyse_alignment.py`` so the numbers are comparable:

* ``line_hash``  = blake2b(stripped, 6 bytes) -- identical to analyse_alignment
* an *added line* is a written line whose stripped form is at least 3 characters
* a *patch added line* is a ``+`` line (not ``+++``) of the final patch whose
  stripped form is at least 3 characters
* a *file identity* is the normalised repo-relative path (see ``norm_path``)

The one thing that genuinely differs between scaffolds is where an edit's target
file is written down, and that is recorded per corpus rather than assumed:

* SWE-agent (frozen study)  -> the ``[File: ...]`` footer of the *observation*
* OpenHands / PI / SWE-smith -> the tool-call arguments (the observation only
  says "The file X has been edited successfully.")

Writes ``data/processed/xscaffold/{corpus}_steps.parquet`` and ``_runs.parquet``,
plus ``results/rebuild/xscaffold_markers.json`` (the literal marker evidence).

    python scripts/xscaffold_extract.py --corpus swegym
    python scripts/xscaffold_extract.py            # all corpora
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall.corpus import _EXIT_CODE, _XML_RETCODE  # noqa: E402  (read-only reuse)

RAW = ROOT / "data" / "raw" / "xscaffold"
PROC = ROOT / "data" / "processed" / "xscaffold"
OUT = ROOT / "results" / "rebuild"

# --------------------------------------------------------------------------------------
# Shared instrument definitions
# --------------------------------------------------------------------------------------

# the frozen study's footer regex, verbatim (src/agentstall/corpus.py: _FILE_HDR)
FILE_HDR = re.compile(r"\[File:\s*([^\]\s]+?)\s*(?:\((\d+) lines total\))?\]")
LINES_TOTAL_ANY = re.compile(r"\((\d+)\s+lines?\s+total\)", re.I)
CATN_HEADER = re.compile(r"cat -n`\s+on\s+(\S+?):")
OH_EDIT_OBS = re.compile(r"(?:The file\s+(\S+?)\s+has been edited|File created successfully at:\s*(\S+))")
# OpenHands / SWE-agent-truncated numbered window: right-aligned number + TAB
NUMBERED_TAB = re.compile(r"^\s*(\d+)\t", re.M)
NUMBERED_COLON = re.compile(r"^(\d+):", re.M)
TRUNCATION = re.compile(
    r"<\.\.\.\s*\d+\s*lines? (?:hidden|omitted)\s*\.\.\.>"
    r"|\.\.\. \(\d+ more lines?"
    r"|output was too long"
    r"|\[Output truncated", re.I)

# pytest / unittest summaries (used only to *measure* coverage, never to judge).
TEST_SUMMARY = re.compile(
    r"(?<![\d.])(\d{1,6})\s+(passed|failed|error|errors|skipped|xfailed|xpassed)\b", re.I)
TEST_SESSION = re.compile(
    r"test session starts|collected \d+ items?|={3,}.*\bin \d+\.\d+s"
    r"|^\s*(?:PASSED|FAILED|ERROR)\b|^[ok]+\s+\S+\s+\d+\.\d+s|^FAIL\b", re.M)

ADDED = re.compile(r"^\+(?!\+\+)(.*)$", re.M)
DIFF_FILE = re.compile(r"^diff --git a/(\S+)", re.M)
PATCH_FILE_HDR = re.compile(r"^\+\+\+ [ab]/(\S+)", re.M)


def line_hash(s: str) -> str:
    """Identical to ``analyse_alignment.line_hash`` (6-byte blake2b of the stripped line)."""
    return hashlib.blake2b(s.strip().encode("utf-8", "ignore"), digest_size=6).hexdigest()


def added_hashes(lines: Iterable[str]) -> List[str]:
    out = []
    for ln in lines:
        s = ln.strip()
        if len(s) >= 3:
            out.append(line_hash(s))
    return out


def patch_hashes(patch: Optional[str]) -> Tuple[List[str], List[str]]:
    """(added-line hashes, touched file paths) of a unified diff."""
    if not patch:
        return [], []
    lines = [m.group(1) for m in ADDED.finditer(patch)]
    files = DIFF_FILE.findall(patch) or PATCH_FILE_HDR.findall(patch)
    return added_hashes(lines), files


_WS_ROOTS = ("/testbed/", "/workspace/", "/repo/", "/app/", "/home/user/")


def norm_path(p: str) -> str:
    """Repo-relative normalisation, so '/testbed/monai/x.py' == 'monai/x.py' == './monai/x.py'."""
    if not p:
        return ""
    p = p.strip().strip("'\"`")
    p = re.sub(r"^(/testbed|/workspace|/repo|/app|/home/user)/[^/]+/", "", p) \
        if re.match(r"^/(testbed|workspace|repo|app)/[^/]+/.", p) else p
    for r in _WS_ROOTS:
        if p.startswith(r):
            p = p[len(r):]
            break
    p = p.lstrip("./")
    return p


def _jsonish(x: Any) -> Any:
    if isinstance(x, str):
        s = x.strip()
        if s.startswith(("[", "{")):
            try:
                return json.loads(s)
            except Exception:
                return x
    return x


def fenced_bash(text: str) -> List[str]:
    return [b.strip() for b in re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text or "", re.S)]


_TESTY_HINTS = ("passed", "failed", "FAILED", "PASSED", "test session", "collected ",
                "pytest", "unittest", "ERROR", "error", "Exit code", "exit code",
                "returncode", "assert", "Assertion")
_TEST_MARKERS = ("test session starts", "collected ", "passed", "failed", "PASSED",
                 "FAILED", "ok\t", "== FAIL", "::", "pytest")
_TEST_SESSION_SAFE = re.compile(r"test session starts|collected \d+ items?|={5,} .{0,80}? in \d+\.\d+s")
_TRUNC_HINTS = ("...", "truncat", "too long", "hidden")


def obs_test_summary(obs: str) -> Dict[str, Any]:
    """Per-step test outcome, measured exactly.  Counts only, no judgement.

    The frozen ``agentstall.corpus.parse_obs_state`` is *not* called here.  Its
    ``_PYTEST_SHORT`` pattern, ``[=!]{3,}.*?(\\d+)\\s+(passed|failed|error).*?[=!]{3,}``,
    backtracks quadratically on a single long line, and the OpenHands observations in these
    corpora reach 100 kB -- a watchdog traceback put the whole run inside it.  The bounded
    pieces it is made of are reused directly (``_EXIT_CODE``, ``_XML_RETCODE``) and the test
    markers are matched with explicitly bounded patterns.

    Every check is also guarded by a plain substring test first: with millions of steps,
    running a dozen regexes over each observation is the difference between a minute and
    an hour.
    """
    o = obs or ""
    base = {"test_strict": 0, "test_loose": 0, "n_pass": None, "n_fail": None,
            "n_err": None, "exit_code": None, "has_footer": 0, "has_lines_total": 0,
            "has_catn": 0, "truncated": 0, "max_numbered": 0}
    if not o:
        return base

    head, tail = o[:8000], o[-8000:]
    exit_code = None
    m = _EXIT_CODE.search(tail) or _EXIT_CODE.search(head)
    if m:
        exit_code = int(m.group(1))
    m = _XML_RETCODE.search(head) or _XML_RETCODE.search(tail)
    if m:
        exit_code = int(m.group(1))

    n_pass = n_fail = n_err = None
    strict = 0
    if any(h in o for h in _TESTY_HINTS):
        last: Dict[str, int] = {}
        for m in TEST_SUMMARY.finditer(o):
            last[m.group(2).rstrip("s").lower()] = int(m.group(1))
        if last:
            strict = 1
            n_pass = last.get("passed")
            n_fail = last.get("failed")
            n_err = last.get("error")
    loose = int(bool(strict) or any(h in o for h in _TEST_MARKERS)
                or bool(_TEST_SESSION_SAFE.search(o)))

    nums = NUMBERED_TAB.findall(o) if "\t" in o else []
    return {
        "test_strict": strict, "test_loose": loose,
        "n_pass": n_pass, "n_fail": n_fail, "n_err": n_err,
        "exit_code": exit_code,
        "has_footer": int("[File:" in o and bool(FILE_HDR.search(o))),
        "has_lines_total": int("lines total" in o and bool(LINES_TOTAL_ANY.search(o))),
        "has_catn": int("cat -n` on" in o and bool(CATN_HEADER.search(o))),
        "truncated": int(any(h in o for h in _TRUNC_HINTS) and bool(TRUNCATION.search(o))),
        "max_numbered": (max(int(x) for x in nums) if nums else 0),
    }


# --------------------------------------------------------------------------------------
# Per-corpus extractors.  Each yields dicts:
#   {run_id, instance_id, model, resolved, patch, source, steps: [step dict]}
# where a step dict is {i, is_edit, file, added:[hashes], obs:str, tool:str, cmd:str}
# --------------------------------------------------------------------------------------


def _mk_step(i, is_edit, file, lines, obs, tool, cmd) -> Dict[str, Any]:
    return {"i": i, "is_edit": int(bool(is_edit)), "file": norm_path(file) if file else "",
            "added": added_hashes(lines) if is_edit else [], "obs": obs or "",
            "tool": tool or "", "cmd": (cmd or "")[:2000]}


EDITOR_EDIT_CMDS = {"create", "str_replace", "insert", "undo_edit"}


def ext_openhands_messages(msgs: Sequence[dict], *, obs_prefix: bool = False) -> List[Dict[str, Any]]:
    """OpenHands-style ``messages``: assistant turns carry ``tool_calls``, tool turns the result."""
    steps: List[Dict[str, Any]] = []
    pending: List[Tuple[str, dict]] = []          # (call_id, tool_call)
    for m in msgs:
        role = m.get("role")
        if role == "assistant":
            tcs = _jsonish(m.get("tool_calls")) or []
            if not isinstance(tcs, list):
                tcs = []
            for t in tcs:
                if not isinstance(t, dict):
                    continue
                pending.append((str(t.get("id") or ""), t))
        elif role == "tool":
            cid = str(m.get("tool_call_id") or "")
            obs = m.get("content") or ""
            if obs_prefix and obs.startswith("OBSERVATION:"):
                obs = obs[len("OBSERVATION:"):].lstrip("\n")
            if pending:
                # attach to the earliest still-unmatched call, else the first pending
                idx = next((k for k, (c, _t) in enumerate(pending) if c and c == cid), 0)
                cid2, tc = pending.pop(idx)
                steps.append(_step_from_tool_call(len(steps), tc.get("function") or {}, obs))
            else:
                steps.append(_mk_step(len(steps), False, "", [], obs, m.get("name") or "", ""))
    for cid, tc in pending:                        # a call whose result never arrived
        steps.append(_step_from_tool_call(len(steps), tc.get("function") or {}, ""))
    return steps


def _step_from_tool_call(i: int, fn: dict, obs: str) -> Dict[str, Any]:
    name = str(fn.get("name") or "")
    args = _jsonish(fn.get("arguments")) or {}
    if not isinstance(args, dict):
        args = {}
    cmd = ""
    is_edit = False
    target = ""
    lines: List[str] = []
    if name in ("str_replace_editor", "file_editor", "edit", "write", "write_file",
                "create", "str_replace", "insert", "undo_edit", "apply_patch"):
        sub = str(args.get("command") or name).lower()
        target = str(args.get("path") or args.get("file_path") or args.get("filename") or "")
        cmd = f"{name} {sub} {target}"
        if name in ("write", "write_file") or sub in ("create", "write"):
            is_edit = True
            lines = str(args.get("file_text") or args.get("content") or args.get("new_str") or "").splitlines()
        elif sub in ("str_replace", "insert", "edit"):
            is_edit = True
            lines = str(args.get("new_str") or args.get("new_string") or args.get("content") or "").splitlines()
            if not lines:
                # the PI agent's `edit` tool: {"path": ..., "edits": [{"oldText":…, "newText":…}]}
                # Every `newText` is text the step wrote, so all of its lines are new.
                for e in (args.get("edits") or []):
                    if isinstance(e, dict):
                        lines += str(e.get("newText") or e.get("new_text")
                                     or e.get("new_str") or "").splitlines()
        elif name == "apply_patch":
            is_edit = True
            lines = [l[1:] for l in str(args.get("patch") or args.get("input") or "").splitlines()
                     if l.startswith("+") and not l.startswith("+++")]
        elif sub == "undo_edit":
            is_edit = True          # an edit action that introduces no line (frozen study: same)
    elif name in ("bash", "execute_bash", "run", "terminal", "shell"):
        raw = str(args.get("command") or args.get("cmd") or args.get("input") or "")
        cmd = raw
        target, lines, is_edit = _bash_edit(raw)
    return _mk_step(i, is_edit, target, lines, obs, name, cmd)


_HEREDOC = re.compile(r"<<\s*'?\"?(\w+)'?\"?\s*\n(.*?)\n\1\s*$", re.S | re.M)
_REDIR = re.compile(r"(?:>|>>)\s*'?\"?([\w./\-]+\.\w+)")


def _pick_heredoc(body: str) -> Optional[Tuple[str, List[str]]]:
    """The heredoc that carries the *new* text, when a command contains several.

    mini-swe-agent edits as ``old=$(cat <<'OLD' … OLD) && new=$(cat <<'NEW' … NEW) &&
    python edit_via_str_replace f -- "$old" "$new"``.  Taking the first heredoc -- which is
    what a plain ``search`` does -- picks up the text being *replaced* and inverts the
    measurement, so a delimiter containing ``new`` wins and the last heredoc is the fallback.
    """
    cands = [(m.group(1), m.group(2)) for m in _HEREDOC.finditer(body)]
    if not cands:
        return None
    for name, text in cands:
        if "new" in name.lower():
            return name, text.splitlines()
    return cands[-1][0], cands[-1][1].splitlines()


def _bash_edit(raw: str) -> Tuple[str, List[str], bool]:
    """A bash command that writes a file: heredoc, ``sed -i``, python ``open(...,'w')``."""
    body = raw or ""
    hd = _pick_heredoc(body)
    if hd is not None:
        r = _REDIR.search(body)
        target = r.group(1) if r else ""
        if not target:
            m = re.search(r"edit_via_str_replace\s+(\S+)", body)
            if m:
                target = m.group(1)
        return target, hd[1], True
    if re.search(r"\bsed\s+-i|\btee\b\s|cat\s*>|printf\s*>|echo\s+.*>", body):
        r = _REDIR.search(body)
        return (r.group(1) if r else ""), [], True
    mm = re.search(r"open\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"][wa]", body)
    if mm:
        return mm.group(1), [], True
    return "", [], False


# SWE-smith / OpenHands-command transcripts pass the text inline as a single-quoted shell
# argument with the newlines written as literal ``\n``: 
#   str_replace_editor create /testbed/reproduce_error.py --file_text 'import os\nimport sys\n'
_SQ = r"'((?:[^'\\]|\\.)*)'"
_INLINE = {
    "file_text": re.compile(r"--file_text[\s=]+" + _SQ, re.S),
    "new_str": re.compile(r"--new_str[\s=]+" + _SQ, re.S),
    "new_string": re.compile(r"--new_string[\s=]+" + _SQ, re.S),
}
_ESC = re.compile(r"\\(.)")
_ESC_MAP = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "\\": "\\"}


def _unescape_shell(s: str) -> str:
    return _ESC.sub(lambda m: _ESC_MAP.get(m.group(1), m.group(1)), s)


def _inline_lines(body: str, key: str) -> List[str]:
    m = _INLINE[key].search(body)
    if not m:
        return []
    return _unescape_shell(m.group(1)).splitlines()


def check_swe_messages(msgs: Sequence[dict]) -> List[Dict[str, Any]]:
    """SWE-agent / OpenHands-command style: the *action* is a fenced command block."""
    steps: List[Dict[str, Any]] = []
    for m in msgs:
        role = m.get("role")
        if role in ("assistant", "agent", "ai"):
            blocks = fenced_bash(m.get("content") or "")
            if not blocks:
                continue
            for b in blocks:
                first = b.splitlines()[0].strip() if b.strip() else ""
                target, is_edit, lines = "", False, []
                sm = re.match(r"str_replace_editor\s+(\w+)\s+(\S+)", first)
                if sm:
                    sub, target = sm.group(1), sm.group(2)
                    body = b
                    if sub == "create":
                        is_edit = True
                        lines = _extract_create_text(body) or _inline_lines(body, "file_text")
                    elif sub in ("str_replace", "insert"):
                        is_edit = True
                        lines = (_extract_new_str(body) or _inline_lines(body, "new_str")
                                 or _inline_lines(body, "new_string"))
                else:
                    target, lines, is_edit = _bash_edit(b)
                steps.append(_mk_step(len(steps), is_edit, target, lines, "", "bash", b))
        elif role in ("user", "tool") and steps:
            c = m.get("content") or ""
            if c.startswith("OBSERVATION:"):
                c = c[len("OBSERVATION:"):].lstrip("\n")
            steps[-1]["obs"] = (steps[-1]["obs"] + "\n" + c).strip()
    return steps


_CREATE_TEXT = re.compile(r"file_text\s*<<\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\1", re.S)
_NEW_STR = re.compile(r"new_str\s*<<\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\1", re.S)


def _extract_create_text(body: str) -> List[str]:
    m = _CREATE_TEXT.search(body)
    return m.group(2).splitlines() if m else []


def _extract_new_str(body: str) -> List[str]:
    m = _NEW_STR.search(body)
    return m.group(2).splitlines() if m else []


def ext_mini_swe(msgs: Sequence[dict]) -> List[Dict[str, Any]]:
    """mini-swe-agent: assistant THOUGHT + one fenced bash block; user carries <output>."""
    steps: List[Dict[str, Any]] = []
    for m in msgs:
        role = m.get("role")
        if role == "assistant":
            blocks = fenced_bash(m.get("content") or "")
            if not blocks:
                continue
            b = blocks[0]
            target, lines, is_edit = _bash_edit(b)
            steps.append(_mk_step(len(steps), is_edit, target, lines, "", "bash", b))
        elif role == "user" and steps:
            c = m.get("content") or ""
            mm = re.search(r"<output>\n?(.*?)</output>", c, re.S)
            body = mm.group(1) if mm else c
            rc = re.search(r"<returncode>(-?\d+)</returncode>", c)
            steps[-1]["obs"] = (steps[-1]["obs"] + "\n" + body).strip()
            if rc:
                steps[-1]["obs"] = f"exit code {rc.group(1)}\n" + steps[-1]["obs"]
    return steps


def last_git_diff(texts: Iterable[str]) -> str:
    """Recover the agent's own final patch from a ``git diff`` printed into a tool output."""
    joined = [(i, t or "") for i, t in enumerate(texts)]
    best = ""
    for _i, t in joined:
        for m in re.finditer(r"^diff --git ", t, re.M):
            seg = t[m.start():]
            best = seg if len(seg) > len(best) else best
    if best:
        return best
    # fall back to a fenced ```diff block
    for _i, t in joined:
        for m in re.finditer(r"```diff\s*\n(.*?)```", t, re.S):
            if len(m.group(1)) > len(best):
                best = m.group(1)
    return best


# --------------------------------------------------------------------------------------
# Row iterators
# --------------------------------------------------------------------------------------


def parquet_files(corpus: str) -> List[Path]:
    return sorted((RAW / corpus).rglob("*.parquet"))


def iter_rows(corpus: str, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
    """Yield one normalised run record per corpus row.

    Every record gets a corpus-unique ``run_id``.  This matters: in
    ``SWE-Gym/OpenHands-Sampled-Trajectories`` the ``run_id`` column is a *sampling
    label* shared by thousands of instances (2429 rows share one value), and in the PI
    corpus ``task_id`` repeats too, so neither column is a key.  An ordinal appended to
    the natural id makes the identity stable across re-runs of this script and unique
    within a corpus, which the taxonomy's "was this file edited again in this run"
    question requires.
    """
    import pyarrow.parquet as pq

    n = 0
    for f in parquet_files(corpus):
        pf = pq.ParquetFile(f)
        for batch in pf.iter_batches(batch_size=200):
            for r in batch.to_pylist():
                rec = ROW_BUILDERS[corpus](r)
                if rec is None:
                    continue
                rec["run_id"] = f"{rec['run_id']}::r{n}"
                rec["ordinal"] = n
                yield rec
                n += 1
                if limit and n >= limit:
                    return


def _row_nebius_openhands(r: dict) -> Dict[str, Any]:
    steps = ext_openhands_messages(r.get("trajectory") or [])
    return {
        "run_id": f"{r.get('trajectory_id')}", "instance_id": str(r.get("instance_id")),
        "model": str(r.get("model") or ""), "resolved": int(r.get("resolved") or 0),
        "patch": r.get("model_patch") or "", "patch_source": "column:model_patch",
        "exit_status": str(r.get("exit_status") or ""),
        "extra": {"repo": r.get("repo"),
                  "pred_passes_gen_tests": r.get("pred_passes_gen_tests")},
        "steps": steps,
    }


def _row_swegym(r: dict) -> Dict[str, Any]:
    msgs = r.get("messages") or []
    steps = ext_openhands_messages(msgs, obs_prefix=True)
    tr = r.get("test_result") or {}
    rep = tr.get("report") or {}
    patch = tr.get("git_patch") or ""
    return {
        "run_id": str(r.get("run_id")), "instance_id": str(r.get("instance_id")),
        "model": str(r.get("run_id") or "").split("_")[0], "resolved": int(bool(r.get("resolved"))),
        "patch": patch, "patch_source": "column:test_result.git_patch",
        "exit_status": "",
        "extra": {"empty_generation": rep.get("empty_generation"),
                  "failed_apply_patch": rep.get("failed_apply_patch"),
                  "test_output_len": len(tr.get("test_output") or "")},
        "steps": steps,
    }


def _row_pi(r: dict) -> Dict[str, Any]:
    try:
        msgs = json.loads(r.get("messages") or "[]")
    except Exception:
        msgs = []
    steps = ext_openhands_messages(msgs)
    patch = last_git_diff([s["obs"] for s in steps])
    return {
        "run_id": str(r.get("task_id")) + "::" + str(len(msgs)), "instance_id": str(r.get("task_id")),
        "model": "", "resolved": 1, "patch": patch,
        "patch_source": "derived:last git-diff in tool output" if patch else "none",
        "exit_status": "",
        "extra": {"num_turns": r.get("num_turns"), "n_msgs": len(msgs),
                  "all_successful": True},
        "steps": steps,
    }


def _row_mini(r: dict) -> Dict[str, Any]:
    msgs = r.get("messages") or []
    steps = ext_mini_swe(msgs)
    patch = last_git_diff([s["obs"] for s in steps])
    return {
        "run_id": str(r.get("instance_id")), "instance_id": str(r.get("instance_id")),
        "model": "", "resolved": None, "patch": patch,
        "patch_source": "derived:last git-diff in tool output" if patch else "none",
        "exit_status": "", "extra": {"n_msgs": len(msgs)},
        "steps": steps,
    }


def _row_tw(r: dict) -> Dict[str, Any]:
    try:
        msgs = json.loads(r.get("messages_json") or "[]")
    except Exception:
        msgs = []
    try:
        gt = json.loads(r.get("ground_truth_meta_json") or "{}")
    except Exception:
        gt = {}
    # the corpus mixes a command-style transcript with a tool_call-style one
    if any(m.get("tool_calls_json") for m in msgs):
        conv = [{"role": m.get("role"), "content": m.get("content"),
                 "tool_calls": m.get("tool_calls_json"),
                 "tool_call_id": m.get("tool_call_id")} for m in msgs]
        steps = ext_openhands_messages(conv, obs_prefix=True)
    else:
        steps = check_swe_messages(msgs)
    patch = last_git_diff([s["obs"] for s in steps])
    return {
        "run_id": str(r.get("session_id")), "instance_id": str(gt.get("instance_id")
                                                              or r.get("source_id") or ""),
        "model": str(r.get("recorded_model") or ""), "resolved": int(bool(gt.get("resolved"))),
        "patch": patch,
        "patch_source": "derived:last git-diff in tool output" if patch else "none",
        "exit_status": "",
        "extra": {"agent_framework": r.get("agent_framework"),
                  "source_dataset": r.get("source_dataset"),
                  "n_turns": r.get("n_turns"), "n_msgs": len(msgs),
                  "patch_present_meta": gt.get("patch_present")},
        "steps": steps,
    }


ROW_BUILDERS = {
    "nebius_openhands": _row_nebius_openhands,
    "swegym": _row_swegym,
    "pi": _row_pi,
    "smithmarines": _row_mini,
    "thoughtworks": _row_tw,
}

PATCH_TRUST = {
    "nebius_openhands": "own_patch_column",
    "swegym": "own_patch_column",
    "pi": "recovered_from_transcript",
    "smithmarines": "recovered_from_transcript",
    "thoughtworks": "recovered_from_transcript",
}


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--chunk", type=int, default=20000,
                    help="rows buffered before a parquet chunk is flushed")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    PROC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    import pyarrow as pa
    import pyarrow.parquet as pq

    keys = [args.corpus] if args.corpus else list(ROW_BUILDERS)

    for key in keys:
        if not parquet_files(key):
            print(f"{key}: no local parquet — run scripts/xscaffold_download.py first")
            continue
        print(f"\n=== {key} ===")
        spath = PROC / f"{key}_steps.parquet"
        rpath = PROC / f"{key}_runs.parquet"
        for p in (spath, rpath):
            if p.exists():
                p.unlink()
        sw = rw = None
        sbuf: List[Dict[str, Any]] = []
        rbuf: List[Dict[str, Any]] = []
        ev: Dict[str, Any] = {
            "n_runs": 0, "n_steps": 0, "n_tool_obs": 0,
            "obs_with_footer": 0, "obs_with_lines_total": 0, "obs_with_catn": 0,
            "obs_truncated": 0,
            "first_footer_literal": None, "first_footer_obs_snippet": None,
            "first_lines_total_literal": None, "first_catn_literal": None,
            "max_numbered_line_seen": 0, "n_edits": 0,
            "n_edits_with_target_path": 0, "n_runs_with_patch": 0,
            "patch_chars_total": 0, "added_lines_total": 0,
            "n_runs_patch_from_column": 0, "n_runs_patch_recovered": 0,
        }

        def flush() -> None:
            # row_group_size is passed explicitly: left to its default a ParquetWriter
            # accumulates up to a million rows in one in-memory row group, and with
            # 3.7 M step rows from the 2 GB OpenHands corpus that is what killed the
            # first attempt at this corpus part-way through.
            nonlocal sw, rw, sbuf, rbuf
            if sbuf:
                t = pa.Table.from_pylist(sbuf)
                if sw is None:
                    sw = pq.ParquetWriter(spath, t.schema)
                sw.write_table(t, row_group_size=len(sbuf))
                sbuf = []
            if rbuf:
                t = pa.Table.from_pylist(rbuf)
                if rw is None:
                    rw = pq.ParquetWriter(rpath, t.schema)
                rw.write_table(t, row_group_size=len(rbuf))
                rbuf = []
            gc.collect()

        for rec in iter_rows(key, args.limit):
            ev["n_runs"] += 1
            if rec["patch"]:
                ev["n_runs_with_patch"] += 1
                ev["patch_chars_total"] += len(rec["patch"])
                if rec["patch_source"].startswith("column:"):
                    ev["n_runs_patch_from_column"] += 1
                else:
                    ev["n_runs_patch_recovered"] += 1
            p_hash, p_files = patch_hashes(rec["patch"])
            rbuf.append({
                "run_id": rec["run_id"], "instance_id": rec["instance_id"],
                "model": rec["model"], "resolved": rec["resolved"],
                "n_steps": len(rec["steps"]),
                "n_edits": sum(s["is_edit"] for s in rec["steps"]),
                "patch_hashes": " ".join(sorted(set(p_hash))),
                "patch_n_added": len(set(p_hash)),
                "patch_files": " ".join(sorted({norm_path(f) for f in p_files})),
                "patch_source": rec["patch_source"],
                "patch_chars": len(rec["patch"] or ""),
                "exit_status": str(rec.get("exit_status", "")),
                "extra": json.dumps(rec.get("extra") or {}, default=str),
            })
            for s in rec["steps"]:
                o = s["obs"] or ""
                ts = obs_test_summary(o)
                if o:
                    ev["n_tool_obs"] += 1
                    if "[" + "File:" in o:
                        m = FILE_HDR.search(o)
                        if m:
                            ev["obs_with_footer"] += 1
                            if ev["first_footer_literal"] is None:
                                ev["first_footer_literal"] = m.group(0)[:300]
                                ev["first_footer_obs_snippet"] = o[:600]
                    if ts["has_lines_total"]:
                        ev["obs_with_lines_total"] += 1
                        if ev["first_lines_total_literal"] is None:
                            ev["first_lines_total_literal"] = LINES_TOTAL_ANY.search(o).group(0)[:300]
                    if ts["has_catn"]:
                        ev["obs_with_catn"] += 1
                        if ev["first_catn_literal"] is None:
                            ev["first_catn_literal"] = o[:300]
                    if ts["truncated"]:
                        ev["obs_truncated"] += 1
                if ts["max_numbered"] > ev["max_numbered_line_seen"]:
                    ev["max_numbered_line_seen"] = ts["max_numbered"]
                if s["is_edit"]:
                    ev["n_edits"] += 1
                    ev["added_lines_total"] += len(s["added"])
                    if s["file"]:
                        ev["n_edits_with_target_path"] += 1
                sbuf.append({
                    "run_id": rec["run_id"], "instance_id": rec["instance_id"],
                    "model": rec["model"], "resolved": rec["resolved"],
                    "step": s["i"], "is_edit": s["is_edit"], "file": s["file"],
                    "n_added": len(s["added"]), "added_hashes": " ".join(s["added"]),
                    "tool": s["tool"],
                    "cmd": (s["cmd"][:600] if s["is_edit"] else ""),
                    "obs_chars": len(o), "truncated": ts["truncated"],
                    "test_strict": ts["test_strict"], "test_loose": ts["test_loose"],
                    "n_pass": ts["n_pass"], "n_fail": ts["n_fail"], "n_err": ts["n_err"],
                    "exit_code": ts["exit_code"],
                    "has_footer": ts["has_footer"], "has_lines_total": ts["has_lines_total"],
                    "has_catn": ts["has_catn"],
                })
            ev["n_steps"] += len(rec["steps"])
            if len(sbuf) >= args.chunk:
                flush()
                print(f"    ... {ev['n_runs']:,} runs, {ev['n_steps']:,} steps", flush=True)
        flush()
        if sw is not None:
            sw.close()
        if rw is not None:
            rw.close()
        if ev["n_runs"] == 0:
            print("  no rows")
            continue
        ev["patch_trust"] = PATCH_TRUST[key]
        print(f"  runs {ev['n_runs']:,}  steps {ev['n_steps']:,}  edits {ev['n_edits']:,}")
        print(f"  obs with [File: ...] footer : {ev['obs_with_footer']:,} "
              f"({ev['obs_with_footer']/max(ev['n_tool_obs'],1):.4%} of {ev['n_tool_obs']:,} obs)")
        print(f"  obs with '(N lines total)'   : {ev['obs_with_lines_total']:,}")
        print(f"  obs with 'cat -n` on X:'     : {ev['obs_with_catn']:,}")
        if ev["first_footer_literal"]:
            print(f"  LITERAL footer: {ev['first_footer_literal']!r}")
        if ev["first_lines_total_literal"]:
            print(f"  LITERAL lines-total: {ev['first_lines_total_literal']!r}")
        if ev["first_catn_literal"]:
            print(f"  LITERAL cat -n head: {ev['first_catn_literal'].splitlines()[0]!r}")
        print(f"  edits {ev['n_edits']:,}, of which with a named target "
              f"{ev['n_edits_with_target_path']:,}; runs with a recoverable patch "
              f"{ev['n_runs_with_patch']:,}/{ev['n_runs']:,}")

        # one file per corpus so several corpora can be extracted in parallel
        (OUT / f"xscaffold_markers_{key}.json").write_text(
            json.dumps({key: ev}, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote per-corpus marker files under {OUT}")


if __name__ == "__main__":
    main()
