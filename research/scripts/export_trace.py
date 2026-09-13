"""Export a condensed, human-readable view of a trajectory for inspection or annotation.

Two outputs:

* ``summary``  - one line per step: kind, action head, observation head.  Cheap enough
  to read a whole 100-step trajectory.
* ``card``     - a per-window annotation card: the task statement, the trajectory
  *before* the window (compressed), the window itself in more detail, and the steps
  *after* the window (compressed).  The after-context is what makes a judgement about
  "did this window advance the task" possible; a runtime could not see it, but an
  annotator must.

Usage:
  python scripts/export_trace.py --corpus tb2 --traj <traj_id> --window 40 10 --out x.md
  python scripts/export_trace.py --corpus tb2 --list --min-steps 60
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import loaders  # noqa: E402
from evidence import extract_entities, extract_state, relevance, task_terms  # noqa: E402
from normalize import normalize_action  # noqa: E402

WS = re.compile(r"\s+")


def clean(s: str, n: int) -> str:
    if not s:
        return ""
    return WS.sub(" ", s)[:n]


def step_line(tr, i: int, obs_chars: int = 130, text_chars: int = 110) -> str:
    s = tr.steps[i]
    acts = [normalize_action(a.name, a.arg) for a in s.actions]
    head = " | ".join(f"{a.kind}:{a.verb}" + (f"({','.join(a.targets[:2])})" if a.targets else "") for a in acts)
    st = extract_state(s.observation)
    ver = []
    if st.exit_code is not None:
        ver.append(f"exit={st.exit_code}")
    if st.n_passed is not None:
        ver.append(f"pass={st.n_passed}")
    if st.n_failed is not None:
        ver.append(f"fail={st.n_failed}")
    if st.build_ok is not None:
        ver.append(f"build={'ok' if st.build_ok else 'FAIL'}")
    if st.error_sig:
        ver.append(f"err[{st.error_sig[:40]}]")
    parts = [f"[{i:>3}] {head or 'no-tool'}"]
    if ver:
        parts.append("{" + " ".join(ver) + "}")
    txt = clean(s.text, text_chars)
    if txt:
        parts.append(f'say="{txt}"')
    obs = clean(s.observation, obs_chars)
    if obs:
        parts.append(f'obs="{obs}"')
    return "  ".join(parts)


def window_card(tr, task_statement: str, t: int, w: int, before: int = 12, after: int = 12,
                detail_obs: int = 260, detail_text: int = 220) -> str:
    lo = max(0, t - w + 1)
    hi = min(len(tr.steps) - 1, t)
    out: List[str] = []
    out.append(f"## trajectory `{tr.traj_id}`")
    out.append(f"- corpus: {tr.meta.get('corpus')}  task: `{tr.task}`  agent: {tr.agent}  model: {tr.model}")
    out.append(f"- final reward: {tr.reward}   steps: {len(tr.steps)}   window: [{lo}, {hi}] (w={w})")
    out.append("")
    out.append("### Task statement (this is everything the agent was told)")
    out.append("```")
    out.append(clean(task_statement, 2500) or "(not recovered)")
    out.append("```")
    out.append("")
    a0 = max(0, lo - before)
    if a0 < lo:
        out.append(f"### Trajectory before the window (steps {a0}-{lo-1}, compressed)")
        out.append("```")
        for i in range(a0, lo):
            out.append(step_line(tr, i, obs_chars=110, text_chars=90))
        out.append("```")
        out.append("")
    out.append(f"### >>> WINDOW UNDER JUDGEMENT: steps {lo}-{hi} <<<")
    out.append("```")
    for i in range(lo, hi + 1):
        out.append(step_line(tr, i, obs_chars=detail_obs, text_chars=detail_text))
    out.append("```")
    out.append("")
    b1 = min(len(tr.steps), hi + 1 + after)
    if b1 > hi + 1:
        out.append(f"### Trajectory after the window (steps {hi+1}-{b1-1}, compressed)")
        out.append("```")
        for i in range(hi + 1, b1):
            out.append(step_line(tr, i, obs_chars=110, text_chars=90))
        out.append("```")
        out.append("")
    if b1 < len(tr.steps):
        out.append("### Final steps of the trajectory (compressed)")
        out.append("```")
        for i in range(max(b1, len(tr.steps) - 6), len(tr.steps)):
            out.append(step_line(tr, i, obs_chars=130, text_chars=100))
        out.append("```")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=["tb2", "nebius"], default="tb2")
    ap.add_argument("--traj")
    ap.add_argument("--task")
    ap.add_argument("--window", nargs=2, type=int, default=None)
    ap.add_argument("--before", type=int, default=12)
    ap.add_argument("--after", type=int, default=12)
    ap.add_argument("--min-steps", type=int, default=40)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.corpus == "tb2":
        trajs = loaders.load_tb2()
        stmts = loaders.tb2_task_statements()
    else:
        trajs = loaders.load_nebius()
        stmts = loaders.nebius_task_statements()

    if args.list:
        trajs = [t for t in trajs if len(t.steps) >= args.min_steps]
        if args.task:
            trajs = [t for t in trajs if args.task in t.task]
        trajs.sort(key=lambda t: len(t.steps), reverse=True)
        for t in trajs[: args.limit]:
            print(f"{t.traj_id:<56} {t.agent:<18} {t.model:<42} reward={t.reward} steps={len(t.steps)}")
        print(f"# {len(trajs)} matching trajectories")
        return

    sel = None
    for t in trajs:
        if args.traj and t.traj_id == args.traj:
            sel = t
            break
        if args.task and args.task in t.task and len(t.steps) >= args.min_steps and sel is None:
            sel = t
    if sel is None:
        print("no trajectory selected")
        return
    if args.window:
        t, w = args.window
        card = window_card(sel, stmts.get(sel.task, ""), t, w, args.before, args.after)
    else:
        out = [f"## `{sel.traj_id}` {sel.agent}/{sel.model} reward={sel.reward} steps={len(sel.steps)}",
               "### Task", "```", clean(stmts.get(sel.task, ""), 2500), "```", "### Steps", "```"]
        out += [step_line(sel, i, obs_chars=150, text_chars=120) for i in range(len(sel.steps))]
        out.append("```")
        card = "\n".join(out)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(card)
        print(f"wrote {args.out} ({len(card)} chars)")
    else:
        print(card)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
