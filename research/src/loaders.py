"""Load coding-agent trajectories into one normalized schema.

Two public corpora are supported:

* ``tb2``    - Terminal-Bench 2.0 trajectories (yoonholee/terminalbench-trajectories).
  Each row is one trial; ``steps`` is a JSON string of
  ``{"src", "msg", "tools": [{"fn","cmd"}], "obs"}`` objects.
* ``nebius`` - SWE-agent trajectories (nebius/SWE-agent-trajectories) over SWE-bench tasks.
  Each row has a ``trajectory`` list of chat messages in the SWE-agent
  ``ASSISTANT: ... ACTION: ...`` text format.

The normalized unit is a :class:`Trajectory` with a list of :class:`Step`.
A ``Step`` is one *agent turn*: the agent's written text, the tool calls it issued,
and the observation(s) that came back.

Nothing here may look at anything other than the observable prefix: features are
computed downstream and are responsible for respecting the online constraint.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pyarrow.parquet as pq

from paths import NEBIUS_DIR, TB2_PARQUET

# --------------------------------------------------------------------------------------
# Normalized structures
# --------------------------------------------------------------------------------------


@dataclass
class Action:
    """One tool invocation."""

    name: str
    arg: str


@dataclass
class Step:
    """One agent turn: text + tool calls + resulting observation."""

    index: int
    text: str = ""
    actions: List[Action] = field(default_factory=list)
    observation: str = ""

    @property
    def action_text(self) -> str:
        return " ; ".join(f"{a.name} {a.arg}".strip() for a in self.actions)


@dataclass
class Trajectory:
    traj_id: str
    task: str
    agent: str
    model: str
    reward: Optional[int]
    steps: List[Step]
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def n_steps(self) -> int:
        return len(self.steps)

    def task_relevant_text(self, task_statement: str) -> str:
        return task_statement


# --------------------------------------------------------------------------------------
# Terminal-Bench 2 loader
# --------------------------------------------------------------------------------------

# claude-code embeds tool calls inside the agent message as fenced blocks.
_TOOLTAG = re.compile(r"\[TOOL_CALL\]\s*(.*?)\s*\[/TOOL_CALL\]", re.S)
_TOOLTAG_NAME = re.compile(r'tool\s*=>\s*"([^"]+)"')
_TOOLTAG_ARGS = re.compile(r"--args\s*(.*?)(?:\n\}\}|\}\})", re.S)


def _parse_tooltags(msg: str) -> List[Action]:
    out = []
    for block in _TOOLTAG.findall(msg):
        nm = _TOOLTAG_NAME.search(block)
        ar = _TOOLTAG_ARGS.search(block)
        out.append(Action(nm.group(1) if nm else "tool", (ar.group(1).strip() if ar else block.strip())))
    return out


def _is_placeholder(text: str) -> bool:
    """The TB2 scrape redacts some payloads as ``$NN`` tokens."""
    return bool(re.fullmatch(r"\$\d+", text.strip()))


def _tb2_row_to_traj(row: Dict[str, Any], row_key: str) -> Optional[Trajectory]:
    raw = row.get("steps")
    if not raw or raw == "null":
        return None
    try:
        raw_steps = json.loads(raw)
    except json.JSONDecodeError:
        return None
    steps: List[Step] = []
    for obj in raw_steps:
        src = obj.get("src")
        msg = obj.get("msg") or ""
        obs = obj.get("obs") or ""
        actions = []
        for t in obj.get("tools") or []:
            if isinstance(t, dict):
                actions.append(Action(str(t.get("fn", "tool")), str(t.get("cmd", ""))))
        if not actions:
            actions = _parse_tooltags(msg)
        if not msg.strip() and not actions and not obs.strip():
            continue  # skip empty frames
        if src == "system":
            continue
        steps.append(Step(index=len(steps), text=msg, actions=actions, observation=obs))
    if len(steps) < 3:
        return None
    return Trajectory(
        traj_id=row_key,
        task=row["task_name"],
        agent=row["agent"],
        model=row["model"],
        reward=int(row["reward"]) if row.get("reward") is not None else None,
        steps=steps,
        meta={
            "duration_seconds": row.get("duration_seconds"),
            "input_tokens": row.get("input_tokens"),
            "output_tokens": row.get("output_tokens"),
            "trial_name": row.get("trial_name"),
            "started_at": row.get("started_at"),
            "corpus": "tb2",
        },
    )


def load_tb2(limit: Optional[int] = None, row_groups: Optional[Iterable[int]] = None) -> List[Trajectory]:
    pf = pq.ParquetFile(TB2_PARQUET)
    cols = ["task_name", "agent", "model", "reward", "duration_seconds", "input_tokens",
            "output_tokens", "trial_name", "trial_id", "started_at", "steps"]
    groups = list(row_groups) if row_groups is not None else range(pf.metadata.num_row_groups)
    seen: Dict[str, int] = {}  # trial_name -> index into out (release ships UUID + empty-UUID twins)
    out: List[Trajectory] = []
    for g in groups:
        for i, row in enumerate(pf.read_row_group(g, columns=cols).to_pylist()):
            key = row.get("trial_name") or f"rg{g}-{i}"
            t = _tb2_row_to_traj(row, key)
            if t is None:
                continue
            if key in seen:
                # Prefer the twin carrying a real trial_id; first-seen order is preserved.
                if row.get("trial_id"):
                    out[seen[key]] = t
                continue
            seen[key] = len(out)
            out.append(t)
            if limit and len(out) >= limit:
                return out
    return out


def tb2_task_statements() -> Dict[str, str]:
    """Recover a canonical task statement per Terminal-Bench task.

    The scraper stored the task prompt only for scaffolds that emit a distinct
    user turn (``terminus-2``, ``terminus-3-3``).  For those rows the first long
    user message is the task description; we take the longest such message per
    task so that the recovered statement is as complete as possible.
    """
    pf = pq.ParquetFile(TB2_PARQUET)
    best: Dict[str, str] = {}
    for g in range(pf.metadata.num_row_groups):
        rows = pf.read_row_group(g, columns=["task_name", "agent", "steps"]).to_pylist()
        for row in rows:
            raw = row.get("steps")
            if not raw or raw == "null":
                continue
            if not (row["agent"].startswith("terminus") or row["agent"] in {"openhands", "codex"}):
                continue
            try:
                steps = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for s in steps[:4]:
                if s.get("src") != "user":
                    continue
                msg = (s.get("msg") or "").strip()
                if _is_placeholder(msg) or len(msg) < 120:
                    continue
                if msg.lower().startswith("warmup"):
                    continue
                if len(msg) > len(best.get(row["task_name"], "")):
                    best[row["task_name"]] = msg
                break
    return best


# --------------------------------------------------------------------------------------
# Nebius SWE-agent loader
# --------------------------------------------------------------------------------------

_ASSISTANT = re.compile(r"^ASSISTANT:\s*(.*?)(?=\nACTION:|\Z)", re.S | re.M)
_ACTION = re.compile(r"^ACTION:\s*(.*?)(?=\nOBSERVATION:|\Z)", re.S | re.M)
_OBS = re.compile(r"^OBSERVATION:\s*(.*?)(?=\nASSISTANT:|\Z)", re.S | re.M)


def _parse_swe_agent_text(text: str) -> Tuple[str, List[Action], str]:
    a = _ASSISTANT.search(text)
    act = _ACTION.search(text)
    obs = _OBS.search(text)
    thought = a.group(1).strip() if a else ""
    action_s = act.group(1).strip() if act else ""
    obs_s = obs.group(1).strip() if obs else ""
    actions: List[Action] = []
    if action_s:
        # first token is the command, remainder the argument
        head, _, rest = action_s.partition(" ")
        actions.append(Action(head.strip(), rest.strip()))
    return thought, actions, obs_s


def load_nebius(limit: Optional[int] = None, files: Optional[int] = 4) -> List[Trajectory]:
    out: List[Trajectory] = []
    names = sorted(f for f in os.listdir(NEBIUS_DIR) if f.endswith(".parquet"))
    for name in names[: files or len(names)]:
        pf = pq.ParquetFile(os.path.join(NEBIUS_DIR, name))
        for g in range(pf.metadata.num_row_groups):
            rows = pf.read_row_group(
                g, columns=["instance_id", "model_name", "target", "trajectory", "exit_status", "generated_patch"]
            ).to_pylist()
            for i, row in enumerate(rows):
                msgs = row["trajectory"] or []
                steps: List[Step] = []
                pending_text, pending_actions = "", []
                for m in msgs:
                    role = m.get("role")
                    txt = m.get("text") or ""
                    if role == "system":
                        continue
                    if role == "ai":
                        thought, actions, obs = _parse_swe_agent_text(txt)
                        if pending_actions or pending_text:
                            steps.append(Step(len(steps), pending_text, pending_actions, ""))
                        pending_text, pending_actions = thought, actions
                        if obs:  # some rows pack observation into the ai turn
                            pending_text = (pending_text + "\n" + obs).strip()
                    else:  # user turn carries the observation
                        if pending_actions or pending_text:
                            steps.append(Step(len(steps), pending_text, pending_actions, txt))
                            pending_text, pending_actions = "", []
                        else:
                            steps.append(Step(len(steps), "", [], txt))
                if pending_actions or pending_text:
                    steps.append(Step(len(steps), pending_text, pending_actions, ""))
                steps = [s for s in steps if s.text.strip() or s.actions or s.observation.strip()]
                for j, s in enumerate(steps):
                    s.index = j
                if len(steps) < 3:
                    continue
                out.append(
                    Trajectory(
                        traj_id=f"nebius::{row['instance_id']}::{i}",
                        task=row["instance_id"],
                        agent="swe-agent",
                        model=row["model_name"],
                        reward=int(bool(row["target"])),
                        steps=steps,
                        meta={
                            "exit_status": row.get("exit_status"),
                            "generated_patch": row.get("generated_patch"),
                            "corpus": "nebius",
                        },
                    )
                )
                if limit and len(out) >= limit:
                    return out
    return out


def nebius_task_statements(limit_files: int = 4) -> Dict[str, str]:
    """Issue text lives in the first user message of each SWE-agent trajectory."""
    out: Dict[str, str] = {}
    names = sorted(f for f in os.listdir(NEBIUS_DIR) if f.endswith(".parquet"))[:limit_files]
    for name in names:
        pf = pq.ParquetFile(os.path.join(NEBIUS_DIR, name))
        for g in range(pf.metadata.num_row_groups):
            rows = pf.read_row_group(g, columns=["instance_id", "trajectory"]).to_pylist()
            for row in rows:
                if row["instance_id"] in out:
                    continue
                for m in row["trajectory"] or []:
                    if m.get("role") == "user":
                        txt = (m.get("text") or "").strip()
                        if len(txt) > 80:
                            out[row["instance_id"]] = txt
                        break
    return out


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    trajs = load_tb2(limit=5)
    print(f"tb2 sample: {len(trajs)}")
    for t in trajs:
        print(f"  {t.traj_id} {t.agent}/{t.model} steps={t.n_steps} reward={t.reward}")
    stmts = tb2_task_statements()
    print(f"recovered task statements: {len(stmts)}")
    k = next(iter(stmts))
    print(f"--- {k} ---\n{stmts[k][:400]}")
    nt = load_nebius(limit=3)
    print(f"nebius sample: {len(nt)}")
    for t in nt:
        print(f"  {t.traj_id} steps={t.n_steps} reward={t.reward}")
