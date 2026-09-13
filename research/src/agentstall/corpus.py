"""Core: turn both trajectory corpora into one per-step table.

Design rules
------------
* **Online.** Every quantity attached to step ``t`` is computable from steps
  ``0..t``.  Anything that needs the future (``future_*``) or the final outcome
  (``label_*``) is written with an explicit prefix so evaluation code can assert
  it never leaks into a feature matrix.
* **Scaffold-independent.** Actions are canonicalised to a small verb vocabulary
  (read / edit / run / search / list / verify / other) so a monitor transfers
  across the 26 Terminal-Bench scaffolds and the SWE-agent editor.
* **Cheap.** Regex and hashing only. A whole run costs a few milliseconds, so the
  study can cover tens of thousands of runs rather than the 45 tasks that the
  first version could afford to annotate.

Corpora
-------
``tb2``    yoonholee/terminalbench-trajectories. One row per trial; ``steps`` is a
           JSON list of {src, msg, tools, obs}.  Label: ``reward``.
``nebius`` nebius/SWE-agent-trajectories. ``trajectory`` is a list of messages with
           role in {system, ai, user}; the ai turn carries the agent's thought and a
           fenced command block, the following user turn carries the observation.
           Labels: ``target`` (bool), ``eval_logs`` (pytest transcript), and
           ``generated_patch`` (the agent's own final diff).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Action canonicalisation
# --------------------------------------------------------------------------------------

VERB_READ = "read"
VERB_EDIT = "edit"
VERB_RUN = "run"
VERB_SEARCH = "search"
VERB_LIST = "list"
VERB_VERIFY = "verify"
VERB_FINISH = "finish"
VERB_OTHER = "other"
VERBS = [VERB_READ, VERB_EDIT, VERB_RUN, VERB_SEARCH, VERB_LIST, VERB_VERIFY, VERB_FINISH, VERB_OTHER]

# Tool names seen across the 26 Terminal-Bench scaffolds.
_TOOL_VERB = {
    "bash": VERB_RUN, "shell": VERB_RUN, "execute_bash": VERB_RUN, "bash_command": VERB_RUN,
    "run_shell_command": VERB_RUN, "terminal": VERB_RUN, "kill_shell": VERB_RUN,
    "bashoutput": VERB_RUN, "taskoutput": VERB_RUN, "wait": VERB_OTHER,
    "read": VERB_READ, "read_file": VERB_READ, "open": VERB_READ, "view": VERB_READ,
    "str_replace_editor": VERB_EDIT, "edit": VERB_EDIT, "write": VERB_EDIT,
    "write_file": VERB_EDIT, "replace": VERB_EDIT, "multi_edit": VERB_EDIT,
    "apply_patch": VERB_EDIT, "create": VERB_EDIT, "str_replace": VERB_EDIT,
    "insert": VERB_EDIT, "undo_edit": VERB_EDIT,
    "grep": VERB_SEARCH, "search": VERB_SEARCH, "search_dir": VERB_SEARCH,
    "search_file": VERB_SEARCH, "find_file": VERB_SEARCH, "glob": VERB_SEARCH,
    "list_directory": VERB_LIST, "ls": VERB_LIST,
    "think": VERB_OTHER, "todo_write": VERB_OTHER, "task_tracker": VERB_OTHER,
    "update_plan": VERB_OTHER, "save_plan": VERB_OTHER, "plan": VERB_OTHER,
    "finish": VERB_FINISH, "mark_task_complete": VERB_FINISH, "submit": VERB_FINISH,
    "goto": VERB_READ, "scroll_down": VERB_READ, "scroll_up": VERB_READ,
}

# first shell token -> verb, for the SWE-agent fenced commands and TB2 bash cmd
_SHELL_READ = {"cat", "head", "tail", "less", "more", "nl", "bat", "xxd", "od", "strings"}
_SHELL_EDIT = {"sed", "tee", "patch", "apply", "touch", "mkdir", "cp", "mv", "rm", "ln",
               "chmod", "chown", "truncate", "dd", "python", "python3", "perl", "awk"}
_SHELL_SEARCH = {"grep", "rg", "ag", "find", "fd", "ack", "locate", "which", "whereis"}
_SHELL_LIST = {"ls", "tree", "du", "df", "stat", "file", "wc"}
_SHELL_VERIFY = {"pytest", "unittest", "tox", "nox", "make", "cmake", "cargo", "go", "npm",
                 "yarn", "mvn", "gradle", "bazel", "ninja", "gcc", "g++", "clang", "javac",
                 "rustc", "test", "bats", "shunit2"}

_VERIFY_HINT = re.compile(
    r"\b(pytest|unittest|tox|npm test|yarn test|cargo test|go test|make test|"
    r"python -m pytest|python -m unittest|bash .*test|\./test|ctest|jest|mocha|"
    r"rspec|phpunit|gradle test|mvn test|bazel test)\b", re.I)

# --------------------------------------------------------------------------------------
# Observation state
# --------------------------------------------------------------------------------------

# exit codes appear in many scaffolds' wrappers
_EXIT_CODE = re.compile(r"(?:exit(?:\s*code)?|returncode|return code)\D{0,12}(-?\d{1,4})", re.I)
_XML_RETCODE = re.compile(r"<returncode>(-?\d+)</returncode>")
_TIMEOUT = re.compile(r"\b(timed out|timeout|killed|took too long|command timed out)\b", re.I)
_TRACEBACK = re.compile(r"^\s*Traceback \(most recent call last\)", re.M)
_ERROR_LINE = re.compile(
    r"^\s*(?:\w*Error|\w*Exception|\w*Warning|error|ERROR|FAILED|fatal|Fatal)\b[:\s].{0,160}$", re.M)
_SYNTAX_ERR = re.compile(r"\b(SyntaxError|IndentationError|ParseError|unexpected token|"
                         r"syntax error|E999)\b", re.I)
_PYTEST_SUMMARY = re.compile(
    r"(?:^|\n)[=!\-]{2,}\s*(?:(?P<failed>\d+)\s+failed)?[,\s]*"
    r"(?:(?P<passed>\d+)\s+passed)?[,\s]*(?:(?P<error>\d+)\s+error)?.*?(?:\n|$)", re.M)
# NOTE: this pattern replaces an earlier `[=!]{3,}.*?(\d+)\s+(passed|failed|error).*?[=!]{3,}`
# which backtracked QUADRATICALLY on long single-line observations: `.` does not cross newlines,
# so on a 100 kB single-line observation the lazy `.*?` tried every length and the parser stalled
# for >10 minutes on 300 rows. The same work with a bounded gap runs in ~19 seconds. The result is
# identical where it matches, because the signal is the leading `[=!]` run followed by a count; the
# trailing run was redundant.  Bounding the gap is what makes it linear.
_PYTEST_SHORT = re.compile(r"[=!]{3,}[^\n]{0,160}?\b(\d+)\s+(passed|failed|error)\b", re.I)
_BUILD_OK = re.compile(r"\b(Build succeeded|Successfully built|compilation terminated\s*\.?\s*$|"
                       r"Finished .* target\(s\)|BUILD SUCCESS|ok\b)", re.I)
_TEST_SESSION = re.compile(r"test session starts|collected \d+ items?|={5,} .* in \d+\.\d+s")
_NOT_FOUND = re.compile(r"\b(command not found|No such file or directory|not found|cannot find|"
                        r"could not resolve|ModuleNotFoundError|ImportError: No module)", re.I)
_PERMISSION = re.compile(r"\b(Permission denied|Operation not permitted|read-only file system)", re.I)
_NETWORK = re.compile(r"\b(Connection refused|Could not resolve host|Network is unreachable|"
                      r"Temporary failure in name resolution|SSL.*error|timed out.*connection)", re.I)
_TERNARY = re.compile(r"(Switch to Ternary|Saving model checkpoint|epoch \d+|step \d+/\d+|"
                      r"it/s\]|\d+%\|)", re.I)
_IPYNB = re.compile(r'"execution_count"|"cell_type"', re.I)
_NUMERIC = re.compile(r"\b\d+\b")

# --------------------------------------------------------------------------------------
# Entity extraction (hashed, cheap)
# --------------------------------------------------------------------------------------

_PATH = re.compile(r"(?:^|[\s'\"=(])((?:/|\./|\.\./)[\w.\-/@+]{2,120})")
_FILELIKE = re.compile(r"\b([\w\-/]+\.(?:py|pyx|js|ts|tsx|jsx|go|rs|c|h|cpp|hpp|java|rb|sh|bash|"
                       r"pl|pm|php|lua|sql|yaml|yml|toml|json|ini|cfg|md|txt|html|css|xml|tex|"
                       r"ml|stan|r|jl|hs|ex|exs|erl|scala|kt|swift|m|f|f90|ipynb|dockerfile))\b", re.I)
_SYMBOL = re.compile(r"\b(?:def|class|function|fn|func|struct|impl|interface|trait|type)\s+"
                     r"([A-Za-z_][\w]{2,60})")
_ERR_CLASS = re.compile(r"\b([A-Z][A-Za-z_]{2,40}(?:Error|Exception|Warning|Fault|Failure))\b")
_TEST_ID = re.compile(r"\b((?:tests?|spec)[/\w\-]*\.py::[\w\[\]\-.]+|"
                      r"test_[\w\-]{2,60}|[\w\-]+_test\.(?:py|go|rb|js|ts))")
_ASSERT_LINE = re.compile(r"\b(AssertionError|assert [^\n]{0,120})", re.I)
_TASK_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")


def h64(s: str) -> str:
    return hashlib.blake2b(s.encode("utf-8", "ignore"), digest_size=8).hexdigest()


@dataclass
class ObState:
    """Everything an observation tells a runtime about execution outcome."""

    n_passed: Optional[int] = None
    n_failed: Optional[int] = None
    n_error: Optional[int] = None
    test_ran: bool = False
    build_ok: Optional[bool] = None
    exit_code: Optional[int] = None
    timed_out: bool = False
    traceback: bool = False
    syntax_error: bool = False
    not_found: bool = False
    permission: bool = False
    network: bool = False
    error_class: Optional[str] = None
    assert_fail: bool = False
    chars: int = 0
    has_output: bool = False

    def verification_score(self) -> float:
        """Monotone scalar: higher = healthier execution state."""
        s = 0.0
        if self.n_failed is not None:
            s -= min(self.n_failed, 500) / 10.0
        if self.n_passed is not None:
            s += min(self.n_passed, 500) / 10.0
        if self.n_error is not None:
            s -= min(self.n_error, 100)
        if self.build_ok is True:
            s += 3.0
        elif self.build_ok is False:
            s -= 3.0
        if self.exit_code is not None:
            s += 1.0 if self.exit_code == 0 else -1.0
        if self.traceback or self.syntax_error or self.assert_fail:
            s -= 1.5
        if self.timed_out:
            s -= 0.5
        return s

    def is_verification(self) -> bool:
        return (self.test_ran or self.build_ok is not None or self.exit_code is not None
                or self.traceback or self.syntax_error or self.n_failed is not None
                or self.n_passed is not None or self.n_error is not None)

    def signature(self) -> str:
        """Coarse state identity for transition counting."""
        bits = [
            "T" if self.test_ran else "-",
            f"p{self.n_passed}" if self.n_passed is not None else "-",
            f"f{self.n_failed}" if self.n_failed is not None else "-",
            f"e{self.n_error}" if self.n_error is not None else "-",
            f"x{self.exit_code}" if self.exit_code is not None else "-",
            "B+" if self.build_ok is True else ("B-" if self.build_ok is False else "-"),
            "TR" if self.traceback else "-",
            "SY" if self.syntax_error else "-",
            "NF" if self.not_found else "-",
            "TO" if self.timed_out else "-",
            (self.error_class or "-")[:24],
        ]
        return "|".join(bits)


def parse_obs_state(obs: str) -> ObState:
    st = ObState()
    if not obs:
        return st
    st.chars = len(obs)
    st.has_output = bool(obs.strip())
    m = _EXIT_CODE.search(obs)
    if m:
        st.exit_code = int(m.group(1))
    m = _XML_RETCODE.search(obs)
    if m:
        st.exit_code = int(m.group(1))
    if _TIMEOUT.search(obs):
        st.timed_out = True
    if _TRACEBACK.search(obs):
        st.traceback = True
    if _SYNTAX_ERR.search(obs):
        st.syntax_error = True
    if _NOT_FOUND.search(obs):
        st.not_found = True
    if _PERMISSION.search(obs):
        st.permission = True
    if _NETWORK.search(obs):
        st.network = True
    if _TEST_SESSION.search(obs):
        st.test_ran = True
    m = _PYTEST_SHORT.search(obs)
    if m:
        st.test_ran = True
        kind = m.group(2).lower()
        n = int(m.group(1))
        if kind == "passed":
            st.n_passed = n
        elif kind == "failed":
            st.n_failed = n
        else:
            st.n_error = n
    else:
        # per-kind counts anywhere in the text ("3 failed, 12 passed")
        fp = re.search(r"(\d+)\s+failed", obs)
        pp = re.search(r"(\d+)\s+passed", obs)
        ep = re.search(r"(\d+)\s+error", obs)
        if fp or pp:
            st.test_ran = True
            if fp:
                st.n_failed = int(fp.group(1))
            if pp:
                st.n_passed = int(pp.group(1))
            if ep:
                st.n_error = int(ep.group(1))
    if _BUILD_OK.search(obs) and st.exit_code in (None, 0):
        if re.search(r"BUILD SUCCESS|Build succeeded|Successfully built|Finished .* target", obs, re.I):
            st.build_ok = True
        elif re.search(r"compilation terminated|Build failed|error: could not compile", obs, re.I):
            st.build_ok = False
    if re.search(r"error: could not compile|compilation terminated|Build FAILED|fatal error", obs, re.I):
        st.build_ok = False
    ec = _ERR_CLASS.search(obs)
    if ec:
        st.error_class = ec.group(1)
    if _ASSERT_LINE.search(obs):
        st.assert_fail = True
    return st


# --------------------------------------------------------------------------------------
# Step record
# --------------------------------------------------------------------------------------


@dataclass
class Step:
    index: int
    verb: str
    tool: str
    cmds: List[str]
    targets: List[str]           # files/paths the action referenced
    sig: str                     # hash of the canonicalised action
    text: str                    # agent thought/message
    obs: str
    obs_state: ObState
    edit_lines: int = 0          # rough size of an edit payload
    is_edit: bool = False
    is_test: bool = False
    is_finish: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


def _classify_shell(cmd: str) -> Tuple[str, List[str]]:
    """Return (verb, target paths) for one shell command line."""
    stripped = cmd.strip()
    if not stripped:
        return VERB_OTHER, []
    # editors embedded in bash: python -c with open(), sed -i, heredoc redirects
    low = stripped.lower()
    if _VERIFY_HINT.search(stripped) or re.search(r"(^|\s)(pytest|tox|ctest|jest|rspec)\b", low):
        verb = VERB_VERIFY
    else:
        head = re.split(r"[\s;|&]+", low)[0]
        base = head.rsplit("/", 1)[-1]
        if base in _SHELL_READ:
            verb = VERB_READ
        elif base in _SHELL_SEARCH:
            verb = VERB_SEARCH
        elif base in _SHELL_LIST:
            verb = VERB_LIST
        elif base in _SHELL_VERIFY:
            verb = VERB_VERIFY
        elif base in _SHELL_EDIT:
            verb = VERB_EDIT if (
                base in {"sed", "tee", "patch", "touch", "mkdir", "cp", "mv", "rm", "ln",
                         "chmod", "chown", "truncate", "dd", "python", "python3", "perl", "awk"}
            ) else VERB_OTHER
        else:
            verb = VERB_RUN
    # edits that are not really edits: bare `python x.py`
    if verb == VERB_EDIT and re.match(r"^(python3?|perl|awk)\b", low) and " -i" not in low \
            and "open(" not in low and "write(" not in low and ">>" not in stripped:
        verb = VERB_VERIFY if re.match(r"^(python3?)\s+\S+\.py", low) else VERB_RUN
    targets = [m.group(1) for m in _PATH.finditer(" " + stripped)]
    targets += [m.group(1) for m in _FILELIKE.finditer(stripped)]
    # de-dup, keep order
    seen, out = set(), []
    for t in targets:
        t = t.rstrip(".,;:)")
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return verb, out


# --------------------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------------------


def _iter_json_list(raw: Any) -> List[dict]:
    if isinstance(raw, str):
        if raw in ("null", "None", ""):
            return []
        try:
            arr = json.loads(raw)
        except Exception:
            return []
    elif isinstance(raw, (list, np.ndarray)):
        arr = raw
    else:
        return []
    return [x for x in arr if isinstance(x, dict)]


def build_tb2_steps(steps_raw: Any) -> List[Step]:
    """One TB2 `steps` JSON blob -> list[Step].

    A record with ``tools`` set is an *action*; a record without ``tools`` is the
    agent's prose, and consecutive prose records belong to the action that follows
    them.  Records that merely carry a tool result (an ``agent`` record with ``obs``
    and no tools, or a ``user`` record) are folded into the preceding step's
    observation.  This is what the v1 loader got wrong: it treated every ``agent``
    record as a step, which discards the command of any action whose text was split
    across records and double-counts the tool results.
    """
    recs = _iter_json_list(steps_raw)
    out: List[Step] = []
    pending_text: List[str] = []
    pending_tools: List[Tuple[str, str]] = []   # (fn, arg)
    pending_extra_obs: List[str] = []
    open_step: Optional[Step] = None

    def flush(obs_extra: str = "") -> None:
        nonlocal pending_text, pending_tools, pending_extra_obs, open_step
        if not pending_tools:
            pending_text = []
            pending_extra_obs = []
            return
        cmds = [arg for _fn, arg in pending_tools if arg]
        tools_used = [fn for fn, _arg in pending_tools if fn]
        text = "\n".join(pending_text).strip()
        if not cmds:
            for block in re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text, re.S):
                cmds.append(block.strip())
        tool_name = tools_used[0] if tools_used else ""
        verb = _TOOL_VERB.get(tool_name.lower(), VERB_OTHER) if tool_name else VERB_OTHER
        targets: List[str] = []
        if cmds:
            v2, tg = _classify_shell("\n".join(cmds))
            if verb in (VERB_OTHER, VERB_RUN):
                verb = v2
            targets = tg
        joined = "\n".join(cmds)
        lname = tool_name.lower()
        is_edit = (
            verb == VERB_EDIT
            and (any(k in lname for k in ("edit", "write", "replace", "create", "patch", "apply"))
                 or re.search(r"\b(sed -i|tee|cat >|cat <<|apply_patch|patch -p)", joined) is not None
                 or re.search(r"""open\([^)]*['"]w""", joined) is not None
                 or re.search(r"(^|\s)>>?\s*\S", joined) is not None)
        )
        # prose and observations that precede the tool call come first; the calling
        # record's own observation is what the runtime sees last
        obs = "\n".join(x for x in (list(pending_extra_obs) + [obs_extra]) if x)
        st = parse_obs_state(obs)
        is_test = _VERIFY_HINT.search(joined) is not None or st.test_ran or "test" in lname
        step = Step(
            index=len(out),
            verb=verb,
            tool=tool_name or verb,
            cmds=cmds,
            targets=targets,
            sig=h64("|".join(sorted(set(tools_used))) + "::" + joined[:800]),
            text=text,
            obs=obs,
            obs_state=st,
            edit_lines=joined.count("\n") if is_edit else 0,
            is_edit=is_edit,
            is_test=is_test,
            is_finish=verb == VERB_FINISH or bool(
                re.search(r"\b(task_complete|mark_task_complete|finish|submit)\b", tool_name, re.I)),
        )
        step.meta["tools"] = tools_used
        step.meta["added_lines"] = edit_added_lines(joined) if is_edit else []
        out.append(step)
        pending_text = []
        pending_tools = []
        pending_extra_obs = []

    for rec in recs:
        src = rec.get("src")
        msg = rec.get("msg") or ""
        tools = rec.get("tools")
        obs = rec.get("obs") or ""
        if src in ("agent", "assistant"):
            if tools:
                # a prose record that also carries the tool call: its text belongs to the
                # action, so it must be appended *before* flushing
                if msg and not msg.startswith(("$", "Executed ")):
                    pending_text.append(msg)
                if isinstance(tools, dict):
                    tools = [tools]
                pending_tools = []
                for t in (tools if isinstance(tools, list) else []):
                    if isinstance(t, dict):
                        arg = t.get("cmd") or t.get("command") or t.get("input") or ""
                        if isinstance(arg, (dict, list)):
                            arg = json.dumps(arg)
                        pending_tools.append((str(t.get("fn") or t.get("name") or ""), str(arg or "")))
                    elif isinstance(t, str):
                        pending_tools.append(("", t))
                flush(obs_extra=obs)
            else:
                if obs:
                    pending_extra_obs.append(obs)
                if msg and not msg.startswith(("$", "Executed ")):
                    pending_text.append(msg)
        elif src == "user":
            # a record with no tools carries a tool result or a note about the environment
            if obs:
                pending_extra_obs.append(obs)
            if msg and msg not in ("Warmup",) and not msg.startswith("$"):
                pending_extra_obs.append(msg)
        elif src == "system":
            # the scaffold's system prompt is not an observation of the workspace
            continue
    flush()
    return out


_AI_CMD_FENCE = re.compile(r"```(?:bash|sh)?\s*\n(.*?)```", re.S)


def build_nebius_steps(traj: Any) -> List[Step]:
    """One Nebius `trajectory` -> list[Step] (ai turn + the user turn that follows it)."""
    msgs = list(_iter_json_list(traj))
    out: List[Step] = []
    pending: Optional[Tuple[str, List[str], str]] = None
    for m in msgs:
        role = m.get("role")
        text = m.get("text") or ""
        if role == "ai":
            # a new ai turn closes the previous one with no observation
            if pending is not None:
                out.append(_mk_nebius_step(len(out), pending[0], pending[1], ""))
                pending = None
            blocks = [b.strip() for b in _AI_CMD_FENCE.findall(text)]
            pending = (text, blocks, "")
        elif role == "user" and pending is not None:
            out.append(_mk_nebius_step(len(out), pending[0], pending[1], text))
            pending = None
        elif role == "user" and pending is None:
            # issue statement or environment note before the first action: skip as a step
            continue
    if pending is not None:
        out.append(_mk_nebius_step(len(out), pending[0], pending[1], ""))
    return out


_NUMBERED_LINE = re.compile(r"^(\d+):", re.M)
# the footer may carry "(N lines total)"; capture the path without that suffix
_FILE_HDR = re.compile(r"\[File:\s*([^\]\s]+?)\s*(?:\((\d+) lines total\))?\]")

_EDIT_OLD = re.compile(r"^>>>+ ?OLD\s*$", re.M)
_EDIT_END = re.compile(r"^<<<+ ?END\s*$", re.M)
_SPLIT_MARK = re.compile(r"^=+\s*$", re.M)
_HEREDOC = re.compile(r"<<\s*'?(\w+)'?\s*\n(.*?)\n\1\s*$", re.S | re.M)
# SWE-agent v1's editor: `edit 26:26` / `str_replace 20 22` / `insert 10`, new lines
# inline, terminated by `end_of_edit`.
_EDIT_CMD_LINE = re.compile(r"^\s*(edit|str_replace|insert)\s+(\d+)(?::(\d+))?\s*$", re.M)


def edit_added_lines(body: str) -> List[str]:
    """Text lines an edit action introduces.

    Two encodings occur in these corpora:

    * SWE-agent v1's editor block, terminated by ``end_of_edit``::

          edit 26:26
              if isinstance(output, str):
                  return []
          end_of_edit

      The block prints the whole anchored region as it will read *after* the edit -- each
      line prefixed by its line number.  The command names the range, ``edit A:B``, so
      exactly ``B - A + 1`` lines are new and SWE-agent places the new lines **last** in
      the block (context first, then the replacement).  The line numbers in the block are
      therefore the reliable way to separate them, and the count is a fallback: taking the
      whole block would treat every unchanged context line as newly written and push the
      survival rate toward 1.

    * A shell heredoc (``cat > f <<'EOF' ... EOF``), where every body line is new.

    Either way the introduced text is recoverable from the action alone, which is what lets
    the study ask, mechanically and with no judgement, whether what the agent wrote turned
    out to be what the solution needed.
    """
    if not body:
        return []
    out: List[str] = []
    for m in _HEREDOC.finditer(body):
        out.extend(m.group(2).splitlines())
    starts = list(_EDIT_CMD_LINE.finditer(body))
    for idx, m in enumerate(starts):
        end = body.find("end_of_edit", m.end())
        end = end if end >= 0 else (starts[idx + 1].start() if idx + 1 < len(starts) else len(body))
        seg = body[m.end():end]
        raw = seg.splitlines()
        # strip the SWE-agent line-number gutter when it is present
        numbered = []
        for ln in raw:
            mm = _NUMBERED_LINE_PREFIX.match(ln)
            if mm:
                numbered.append((int(mm.group(1)), ln[mm.end():]))
        k = int(m.group(2))
        span = (int(m.group(3)) - k + 1) if m.group(3) else 1
        if numbered:
            # the new lines are the ones whose numbers fall in the edited range
            chosen = [text for num, text in numbered if k <= num <= k + span - 1]
            if len(chosen) < min(span, len(numbered)):
                chosen = [text for _num, text in numbered[-span:]]
        else:
            chosen = raw[-span:] if span <= len(raw) else raw
        out.extend(chosen)
    return [ln for ln in (x.strip() for x in out) if len(ln) >= 3]


_NUMBERED_LINE_PREFIX = re.compile(r"^\s*(\d+):")


def editor_state(obs: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """(file shown, its total line count, first numbered line) from an observation.

    SWE-agent and similar scaffolds append an editor footer to every observation:

        [File: /lexicon/lexicon/providers/memset.py (151 lines total)]
        1: ...
        (Open file: /lexicon/lexicon/providers/memset.py)
        (Current directory: /lexicon)
        bash-$

    ``(N lines total)`` is an *objective, per-step* measurement of the workspace: it
    changes exactly when the agent adds or removes lines, so a runtime can watch file
    growth at every step with no test harness.  That is the densest objective signal
    any public trajectory corpus exposes.
    """
    if not obs:
        return None, None, None
    m = _FILE_HDR.search(obs)
    if not m:
        return None, None, None
    nm = _NUMBERED_LINE.search(obs)
    return (m.group(1).strip(),
            (int(m.group(2)) if m.group(2) else None),
            (int(nm.group(1)) if nm else None))


def _mk_nebius_step(idx: int, thought: str, cmds: List[str], obs: str) -> Step:
    """One SWE-agent step.

    The editor's actions do not name the file they touch: a ``str_replace`` block is
    just ``str_replace A B`` followed by OLD/===/NEW markers, and the *observation*
    opens with ``[File: /abs/path.py (N lines total)]``.  So the edit target has to be
    recovered from the observation, which is what a runtime sees anyway.
    """
    first = cmds[0].splitlines()[0] if cmds and cmds[0].strip() else ""
    body = "\n".join(cmds)
    verb = VERB_OTHER
    targets: List[str] = []
    head = first.strip().split()[0].lower() if first.strip() else ""
    if first:
        verb, targets = _classify_shell(first)
        if head in _TOOL_VERB:
            verb = _TOOL_VERB[head]
        if head in ("create", "str_replace", "insert", "undo_edit", "edit", "apply_patch"):
            verb = VERB_EDIT
        elif head in ("open", "goto", "scroll_down", "scroll_up"):
            verb = VERB_READ
    fm = _FILE_HDR.search(obs or "")
    if fm:
        p = fm.group(1)
        targets = list(dict.fromkeys([p] + [t for t in targets if t != p]))
    file_shown, file_total, file_first = editor_state(obs or "")
    is_edit = verb == VERB_EDIT and (
        head in ("create", "str_replace", "insert", "undo_edit", "edit", "apply_patch")
        or re.search(r"\b(sed -i|tee|cat >|apply_patch|patch -p)", body) is not None
        or re.search(r'\bopen\([^)]*["\']w', body) is not None
    )
    st = parse_obs_state(obs)
    is_test = _VERIFY_HINT.search(body) is not None or st.test_ran
    step = Step(
        index=idx,
        verb=verb,
        tool=(first.strip().split()[0] if first.strip() else verb),
        cmds=cmds,
        targets=targets,
        sig=h64(body[:800] if body else thought[:400]),
        text=thought,
        obs=obs,
        obs_state=st,
        edit_lines=body.count("\n") if is_edit else 0,
        is_edit=is_edit,
        is_test=is_test,
        is_finish=re.search(r"\b(submit|finish)\b", body[:80], re.I) is not None,
    )
    step.meta["file_shown"] = file_shown
    step.meta["file_total"] = file_total
    step.meta["file_first"] = file_first
    step.meta["added_lines"] = edit_added_lines(body) if is_edit else []
    return step


# --------------------------------------------------------------------------------------
# Objective outcome extraction
# --------------------------------------------------------------------------------------

_DIFF_FILE = re.compile(r"^diff --git a/(\S+)", re.M)
_PATCH_FILE_HDR = re.compile(r"^\+\+\+ b/(\S+)", re.M)
_ADDED_LINE = re.compile(r"^\+(?!\+\+)(.*)$", re.M)


def patch_shape(patch: str) -> Dict[str, Any]:
    """Objective shape of a final patch."""
    if not patch or not patch.strip():
        return {"files": [], "n_files": 0, "n_added": 0, "n_removed": 0, "added_lines": [],
                "lines": 0, "has_patch": False}
    files = _DIFF_FILE.findall(patch)
    if not files:
        files = _PATCH_FILE_HDR.findall(patch)
    added = [m.group(1).strip() for m in _ADDED_LINE.finditer(patch)]
    added_nontrivial = [a for a in added if len(a) >= 3]
    n_removed = len(re.findall(r"^-(?!--)", patch, re.M))
    return {
        "files": files,
        "n_files": len(set(files)),
        "n_added": len(added_nontrivial),
        "n_removed": n_removed,
        "added_lines": added_nontrivial,
        "lines": patch.count("\n"),
        "has_patch": True,
    }


def patch_basenames(patch: str) -> set:
    return {Path(f).name for f in patch_shape(patch)["files"]}


def parse_eval_logs(logs: str) -> Dict[str, Any]:
    """Objective test outcome from the SWE-bench evaluation transcript."""
    out = {"ran": False, "n_pass": None, "n_fail": None, "n_error": None,
           "resolved_marker": None, "duration_s": None}
    if not logs or not isinstance(logs, str):
        return out
    out["ran"] = "___TESTS_SECTION___" in logs or "test session starts" in logs
    last = None
    for m in re.finditer(r"(\d+)\s+(passed|failed|error|errors|skipped|xfailed|xpassed)", logs):
        n, kind = int(m.group(1)), m.group(2).rstrip("s")
        last = last or {}
        last[kind] = n
    if last:
        out["n_pass"] = last.get("passed")
        out["n_fail"] = last.get("failed")
        out["n_error"] = last.get("error")
    m = re.search(r"in ([\d.]+)s", logs)
    if m:
        out["duration_s"] = float(m.group(1))
    if "Some tests failed" in logs:
        out["resolved_marker"] = False
    if re.search(r"All tests passed|no tests ran|== \d+ passed", logs):
        out["resolved_marker"] = True
    return out


def ner_entities(text: str) -> List[Tuple[str, str]]:
    """(kind, value) entities in a chunk of text. Kinds are stable across corpora."""
    out: List[Tuple[str, str]] = []
    if not text:
        return out
    for m in _PATH.finditer(text):
        p = m.group(1).rstrip(".,;:)")
        if len(p) > 2:
            out.append(("path", p))
    for m in _FILELIKE.finditer(text):
        out.append(("file", m.group(1)))
    for m in _SYMBOL.finditer(text):
        out.append(("symbol", m.group(1)))
    for m in _ERR_CLASS.finditer(text):
        out.append(("exc", m.group(1)))
    for m in _TEST_ID.finditer(text):
        out.append(("testid", m.group(1)))
    return out
