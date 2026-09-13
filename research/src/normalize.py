"""Action normalization: turn raw tool calls into canonical, comparable actions.

Everything downstream (repetition, target novelty, phase labelling) works on
:class:`NormAction` objects, never on raw strings.  Normalization is deterministic
and reference-free: it uses only the agent's own tool call.
"""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------------------
# Tool-class taxonomy (unified over scaffolds)
# --------------------------------------------------------------------------------------

TOOL_CLASSES: Dict[str, str] = {
    # shell / terminal
    "bash_command": "shell", "execute_bash": "shell", "shell": "shell", "Bash": "shell",
    "run_shell_command": "shell", "execute": "shell", "bash": "shell", "shell_command": "shell",
    "run_shell-command": "shell", "run_-shell_command": "shell", "interact_with_shell": "shell",
    "BashOutput": "shell", "KillShell": "shell", "wait_shell_command": "shell",
    "kill_shell_command": "shell", "terminal": "shell", "cmdtool": "shell",
    # file reading
    "Read": "read", "read_file": "read", "view": "read", "open_file": "read",
    "cat": "read", "read_many_files": "read", "image_read": "read", "open_image": "read",
    "view_image": "read", "read_media": "read",
    # file writing / editing
    "Write": "edit", "write_file": "edit", "Edit": "edit", "edit_file": "edit",
    "str_replace_editor": "edit", "replace": "edit", "replace_file": "edit",
    "create": "edit", "insert": "edit", "MultiEdit": "edit", "apply_patch": "edit",
    "NotebookEdit": "edit",
    # search
    "Grep": "search", "grep": "search", "search_file_content": "search", "Glob": "search",
    "glob": "search", "list_directory": "search", "ls": "search", "find": "search",
    # python / notebook
    "execute_ipython_cell": "python", "python": "python", "execute_python": "python",
    "call_llm_batch": "python",
    # web
    "WebFetch": "web", "web_fetch": "web", "fetch_url": "web", "http_request": "web",
    "WebSearch": "web", "web_search": "web", "google_web_search": "web",
    # control / bookkeeping
    "mark_task_complete": "control", "finish": "control", "finish_verification": "control",
    "end_execution": "control", "think": "control", "task_tracker": "control",
    "TodoWrite": "control", "update_plan": "control", "save_plan": "control",
    "write_todos": "control", "Task": "control", "TaskOutput": "control", "TaskStop": "control",
    "AskUserQuestion": "control", "list_mcp_resources": "control",
    # swe-agent shell commands are bash_command from the parser, but the family is recovered below
}

# shell commands that are really searches / reads / edits
SHELL_SEARCH = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "find", "locate", "fd"}
SHELL_READ = {"cat", "head", "tail", "less", "more", "bat", "wc", "nl", "sed", "awk", "grep"}
SHELL_EDIT = {"sed", "patch", "tee", "touch", "rm", "mv", "cp", "mkdir"}
SHELL_VERIFY = {
    "pytest", "python", "python3", "tox", "make", "npm", "yarn", "pnpm", "cargo", "go",
    "javac", "java", "gcc", "g++", "clang", "cmake", "dotnet", "mvn", "gradle", "r",
    "rscript", "julia", "node", "deno", "bun", "swift", "ruby", "perl", "php", "bash",
    "sh", "zsh", "test", "unittest", "nosetests", "jest", "mocha", "vitest", "ctest",
    "pkg-config", "pip", "pip3", "apt-get", "apt", "yum", "apk", "conda", "uv", "poetry",
}

VERIFY_VERBS = {
    "pytest", "tox", "ctest", "jest", "mocha", "vitest", "nosetests", "unittest",
    "make", "cmake", "ninja", "cargo", "go", "javac", "java", "gcc", "g++", "clang",
    "dotnet", "mvn", "gradle", "rscript", "test", "bats", "check",
}
INSTALL_VERBS = {"pip", "pip3", "apt-get", "apt", "apk", "yum", "conda", "uv", "poetry",
                 "npm", "yarn", "pnpm", "gem", "bundle", "brew", "pacman", "dnf"}
# priority when a batch contains several commands: verification is the most
# task-informative, pure bookkeeping least.
KIND_PRIORITY = ["verify", "install", "edit", "search", "read", "execute", "python", "web", "other"]


def _verb_of(cmd: str) -> str:
    toks = _tokenize(cmd)
    while toks and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=\S*", toks[0])
                    or toks[0] in {"sudo", "time", "env", "nohup", "command", "exec"}):
        toks = toks[1:]
    if not toks:
        return ""
    base = os.path.basename(toks[0]).lower()
    if base in {"python", "python3", "python2"} and len(toks) > 1:
        if toks[1] == "-c":
            return "python-c"
        if len(toks) > 2 and toks[1] == "-m":
            return "python-m-" + toks[2].lower()
    return base


def _kind_of_verb(verb: str) -> str:
    if not verb:
        return "other"
    if verb in VERIFY_VERBS or verb.startswith("python-m-pytest") or verb.startswith("python-m-unittest"):
        return "verify"
    if verb in INSTALL_VERBS:
        return "install"
    if verb in SHELL_SEARCH:
        return "search"
    if verb in {"sed", "awk", "cat", "head", "tail", "less", "more", "bat", "wc", "nl"}:
        return "read"
    if verb in {"touch", "rm", "mv", "cp", "mkdir", "tee", "patch", "chmod", "chown"}:
        return "edit"
    if verb in {"gdb", "valgrind", "strace", "ltrace"}:
        return "verify"
    if verb in {"curl", "wget"}:
        return "web"
    if verb in {"cd", "echo", "export", "source", "true", "printf", "pwd", "which", "sleep",
                "kill", "ps", "ls", "du", "df", "uname", "whoami", "id", "date", "uptime",
                "hostname", "mount", "history", "wait", "exit", "set", "ulimit"}:
        return "control"
    if verb.startswith("python"):
        return "execute"
    return "execute"

TEST_HINTS = ("test", "spec", "check", "verify", "assert", "pytest", "unittest", "tox")

REDIRECT_RE = re.compile(r"(>>?|<<?|\|&?|&&|\|\||;|\n)")


def _tokenize(cmd: str) -> List[str]:
    """Best-effort shell tokenizer that never raises."""
    cmd = cmd.strip()
    if not cmd:
        return []
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return re.findall(r'"[^"]*"|\'[^\']*\'|\S+', cmd)


PATH_RE = re.compile(r"[\w./\-@+]*/[\w./\-@+]*|[\w\-.]+\.(?:py|r|js|ts|tsx|jsx|go|rs|c|h|cpp|hpp|java|rb|sh|json|yaml|yml|toml|md|txt|csv|cfg|ini|sql|html|css|xml|ipynb)\b")
SYMBOL_RE = re.compile(r"\b([a-z_][a-z0-9_]{2,})\s*\(")
CAMEL_RE = re.compile(r"\b([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b")
DOTTED_RE = re.compile(r"\b([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*){1,3})\b")
IDENT_RE = re.compile(r"\b([a-z_][a-z0-9_]{3,})\b")


@dataclass
class NormAction:
    """Canonical description of one tool call."""

    raw_name: str
    tool: str                      # taxonomy class: shell/read/edit/search/python/web/control/other
    verb: str                      # e.g. grep, cat, pytest, str_replace
    targets: Tuple[str, ...]       # plausible file/symbol targets, normalized
    search_terms: Tuple[str, ...]  # grep patterns / queries
    signature: str                 # normalized string for exact-duplicate detection
    kind: str                      # coarse intent: explore/read/edit/execute/verify/control
    commands: Tuple[str, ...] = ()  # individual shell commands when a compound command was batched

    def as_dict(self) -> Dict[str, object]:
        return {
            "raw_name": self.raw_name, "tool": self.tool, "verb": self.verb,
            "targets": list(self.targets), "search_terms": list(self.search_terms),
            "signature": self.signature, "kind": self.kind,
        }


_WS = re.compile(r"\s+")
_NUM = re.compile(r"\b\d+\b")


def _norm_ws(s: str) -> str:
    return _WS.sub(" ", s).strip()


def norm_signature(name: str, arg: str) -> str:
    """Normalized (name, argument) key for exact-duplicate detection.

    Numbers, quoted literals and whitespace are collapsed so that e.g.
    ``sed -n '10,20p' f.py`` and ``sed -n '30,40p' f.py`` are treated as the same
    *shape* of action, while the exact-command variant keeps the digits.
    """
    a = _norm_ws(arg)
    a = _NUM.sub("#", a)
    a = re.sub(r"'[^']*'", "'#'", a)
    a = re.sub(r'"[^"]*"', '"#"', a)
    return f"{name}::{a}"[:400]


def _extract_targets(tokens: Sequence[str], raw: str) -> Tuple[List[str], List[str]]:
    targets: List[str] = []
    terms: List[str] = []
    for t in tokens:
        if t.startswith("-"):
            continue
        if "/" in t or "." in t:
            m = PATH_RE.search(t)
            if m:
                p = m.group(0).strip("'\"")
                if len(p) > 1:
                    targets.append(p.lstrip("./"))
    for m in SYMBOL_RE.finditer(raw):
        targets.append(m.group(1) + "()")
    for m in CAMEL_RE.finditer(raw):
        targets.append(m.group(1))
    # keep order, dedupe
    seen, out = set(), []
    for p in targets:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:12], terms[:6]


def _shell_recipe(cmd: str) -> List[str]:
    """Split a compound shell command into its individual commands."""
    parts = [p for p in REDIRECT_RE.split(cmd) if p and p not in ("|", "||", "&&", ";", "\n", ">", ">>", "<", "<<", "|&")]
    return [_norm_ws(p) for p in parts if _norm_ws(p)]


def normalize_action(raw_name: str, arg: str) -> NormAction:
    name = (raw_name or "tool").strip()
    tool = TOOL_CLASSES.get(name, "other")
    arg = arg or ""
    verb, kind = name.lower(), "other"
    targets: List[str] = []
    terms: List[str] = []
    commands: List[str] = []

    if tool == "shell":
        commands = _shell_recipe(arg)
        my_verbs = [_verb_of(c) for c in commands]
        my_kinds = [_kind_of_verb(v) for v in my_verbs]
        # the most task-informative command in the batch defines the action
        ranked = sorted(
            zip(my_kinds, my_verbs, commands),
            key=lambda t: KIND_PRIORITY.index(t[0]) if t[0] in KIND_PRIORITY else len(KIND_PRIORITY),
        )
        kind, verb, lead_cmd = ranked[0] if ranked else ("other", "shell", "")
        # heredocs / redirects that write files are edits even when the verb is a reader
        writeish = bool(re.search(r"<<\s*'?\"?\w*'?\"?\s*\n", arg)) or re.search(r"(?<![0-9>])>\s*\S+", arg)
        if writeish and kind in {"read", "execute", "control", "search"}:
            kind = "edit"
        elif writeish and kind == "other":
            kind = "edit"
        lead_toks = _tokenize(lead_cmd)
        for v, c in zip(my_verbs, commands):
            if v in SHELL_SEARCH:
                toks = _tokenize(c)
                pat = next((t for t in toks[1:] if not t.startswith("-")), "")
                if pat and "/" not in pat:
                    terms.append(_norm_ws(pat)[:80])
        targets, _ = _extract_targets(lead_toks + commands, arg)
        for t in list(targets):
            if any(h in os.path.basename(t).lower() for h in TEST_HINTS):
                targets.append("test::" + os.path.basename(t))
        if re.search(r"\b(pytest|unittest|nosetests|tox|ctest|jest|mocha|vitest)\b", arg) or re.search(r"\btests?/\S*\.py\b", arg):
            kind = "verify"
    elif tool == "read":
        kind = "read"
        verb = "read"
        targets, _ = _extract_targets(_tokenize(arg), arg)
        m = PATH_RE.search(arg)
        if m:
            targets.append(m.group(0).lstrip("./"))
    elif tool == "edit":
        kind = "edit"
        verb = "edit"
        targets, _ = _extract_targets(_tokenize(arg), arg)
    elif tool == "search":
        kind = "search"
        verb = "search"
        terms.append(_norm_ws(arg)[:120])
        targets, _ = _extract_targets(_tokenize(arg), arg)
    elif tool == "verify":
        kind = "verify"
        verb = "verify"
    elif tool == "web":
        kind = "web"
        verb = "web"
    elif tool == "control":
        kind = "control"
        verb = name.lower()
    elif tool == "python":
        kind = "execute"
        verb = "python"
        targets, _ = _extract_targets(_tokenize(arg), arg)
    else:
        kind = "other"
        verb = name.lower()
        targets, _ = _extract_targets(_tokenize(arg), arg)

    seen, uniq = set(), []
    for t in targets:
        t = t.strip()
        if t and t not in seen and len(t) < 200:
            seen.add(t)
            uniq.append(t)
    seen, uniqterms = set(), []
    for t in terms:
        if t and t not in seen:
            seen.add(t)
            uniqterms.append(t)

    return NormAction(
        raw_name=name,
        tool=tool,
        verb=verb,
        targets=tuple(uniq[:10]),
        search_terms=tuple(uniqterms[:4]),
        signature=norm_signature(verb, arg),
        kind=kind,
        commands=tuple(commands[:40]),
    )


def normalize_trajectory_actions(steps) -> List[List[NormAction]]:
    out = []
    for s in steps:
        acts = [normalize_action(a.name, a.arg) for a in s.actions]
        out.append(acts)
    return out
