"""Draw the annotation sample and export one card per window.

Design decisions
----------------
* Trajectories are drawn from the same stratified sample that the feature dataset uses
  (``data/processed/<corpus>/sample_trajectories.jsonl``), so annotations and features
  describe exactly the same runs.
* Windows per trajectory are placed at evenly spaced positions ("position sample") rather
  than at positions the detector suspects.  A small number of *control* windows is added
  with an explicit prior (long runs of identical commands; runs immediately after a
  verification that made the failure set shrink) to check the labels are not degenerate.
* One card per window, written to ``../datasets/annotations/cards/<card_id>.md``, plus an index
  CSV with the sampling metadata.  Cards contain no monitor scores.

Usage:
  python scripts/make_annotation_cards.py --corpus tb2 --n-traj 36 --per-traj 4 --w 10
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import paths  # noqa: E402
from export_trace import step_line  # noqa: E402
from loaders import Step, Trajectory  # noqa: E402
from normalize import normalize_action  # noqa: E402

PH = re.compile(r"^\$[0-9a-fA-F]{1,4}$")


def load_sample(path: str) -> List[Trajectory]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            b = json.loads(line)
            steps = [Step(index=i, text=s["text"],
                          actions=[__import__("loaders").Action(a["name"], a["arg"]) for a in s["actions"]],
                          observation=s["obs"])
                     for i, s in enumerate(b["steps"])]
            out.append(Trajectory(traj_id=b["traj_id"], task=b["task"], agent=b["agent"],
                                  model=b["model"], reward=b["reward"], steps=steps, meta=b["meta"]))
    return out


def quality_flags(tr: Trajectory) -> Dict[str, Any]:
    n = len(tr.steps)
    ph = sum(1 for s in tr.steps if PH.match((s.observation or "").strip()))
    msgs = [re.sub(r"\s+", " ", (s.text or "").strip()) for s in tr.steps if (s.text or "").strip()]
    maxrep = (max(Counter(msgs).values()) / len(msgs)) if msgs else 0.0
    notool = sum(1 for s in tr.steps if not s.actions)
    return {
        "n_steps": n,
        "placeholder_frac": ph / max(1, n),
        "max_msg_repeat_frac": maxrep,
        "no_tool_frac": notool / max(1, n),
        "exclude": (n < 30) or (ph / max(1, n) > 0.5) or (maxrep > 0.4),
    }


def verification_improvements(tr: Trajectory) -> List[int]:
    """Steps at which the verification state improved relative to the previous check."""
    from features import _state_is_verification, _state_score  # local import, private helpers
    out, prev = [], None
    for s in tr.steps:
        from evidence import extract_state
        cur = extract_state(s.observation)
        if not _state_is_verification(cur):
            continue
        if prev is not None and _state_score(cur) > _state_score(prev):
            out.append(s.index)
        prev = cur
    return out


def exact_repeat_runs(tr: Trajectory, k: int = 4) -> List[int]:
    """Steps at the end of a run of k+ identical normalized actions."""
    sigs: List[Tuple[int, str]] = []
    for s in tr.steps:
        for a in s.actions:
            sigs.append((s.index, normalize_action(a.name, a.arg).signature))
    out, run = [], 1
    for i in range(1, len(sigs)):
        run = run + 1 if sigs[i][1] == sigs[i - 1][1] else 1
        if run == k:
            out.append(sigs[i][0])
    return out


def position_windows(n: int, per: int, w: int, rng: random.Random, min_head: int = 5) -> List[int]:
    """Evenly spaced window end points, jittered, avoiding the first ``min_head`` steps."""
    if n <= w + min_head:
        return [n - 1]
    lo, hi = w + min_head - 1, n - 1
    if hi <= lo:
        return [hi]
    span = (hi - lo) / max(1, per)
    ends = []
    for j in range(per):
        c = lo + span * (j + 0.5)
        ends.append(int(min(hi, max(lo, c + rng.uniform(-span / 3, span / 3)))))
    return sorted(set(ends))


def card(tr: Trajectory, statement: str, t: int, w: int, cid: str,
         extra_note: str = "", before: int = 14, after: int = 14) -> str:
    lo = max(0, t - w + 1)
    out: List[str] = []
    out.append(f"# Annotation card `{cid}`")
    out.append("")
    out.append(f"- corpus: `{tr.meta.get('corpus')}`")
    out.append(f"- task id: `{tr.task}`")
    out.append(f"- scaffold: `{tr.agent}`   model: `{tr.model}`")
    out.append(f"- trajectory length: {len(tr.steps)} steps   final task reward: {tr.reward}")
    out.append(f"- **window under judgement: steps {lo}–{t} (w={w})**")
    if extra_note:
        out.append(f"- sampling note: {extra_note}")
    out.append("")
    out.append("## Task statement (all the information the agent was given)")
    out.append("```text")
    out.append((statement or "(task statement not recoverable from this corpus)")[:3000])
    out.append("```")
    out.append("")
    a0 = max(0, lo - before)
    if a0 < lo:
        out.append(f"## Before the window (steps {a0}–{lo-1})")
        out.append("```text")
        out.extend(step_line(tr, i, obs_chars=140, text_chars=120) for i in range(a0, lo))
        out.append("```")
        out.append("")
    out.append(f"## WINDOW UNDER JUDGEMENT (steps {lo}–{t})")
    out.append("```text")
    out.extend(step_line(tr, i, obs_chars=300, text_chars=260) for i in range(lo, t + 1))
    out.append("```")
    out.append("")
    b1 = min(len(tr.steps), t + 1 + after)
    if b1 > t + 1:
        out.append(f"## After the window (steps {t+1}–{b1-1})")
        out.append("```text")
        out.extend(step_line(tr, i, obs_chars=140, text_chars=120) for i in range(t + 1, b1))
        out.append("```")
        out.append("")
    if b1 < len(tr.steps):
        out.append("## Final steps of the trajectory")
        out.append("```text")
        out.extend(step_line(tr, i, obs_chars=160, text_chars=120)
                   for i in range(max(b1, len(tr.steps) - 6), len(tr.steps)))
        out.append("```")
        out.append("")
    out.append("## Your label")
    out.append("")
    out.append("Apply `docs/annotation_guide.md` §4 in order. Record:")
    out.append("")
    out.append("```")
    out.append("label: PRODUCTIVE | STAGNANT | REGRESSION | DONE_REDUNDANT | BLOCKED_EXTERNAL | UNCERTAIN")
    out.append("confidence: high | medium | low")
    out.append("boundary: true | false        (window cuts a productive interval in half)")
    out.append("channels_advanced: E | I | V | none")
    out.append("justification: one or two sentences citing specific step numbers")
    out.append("```")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--processed", default=None)
    ap.add_argument("--n-traj", type=int, default=36)
    ap.add_argument("--per-traj", type=int, default=4)
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--n-control", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    proc = args.processed or os.path.join(paths.PROCESSED, args.corpus)
    outdir = args.outdir or os.path.join(paths.DATA, "annotations", args.corpus)
    cards_dir = os.path.join(outdir, "cards")
    os.makedirs(cards_dir, exist_ok=True)

    trajs = load_sample(os.path.join(proc, "sample_trajectories.jsonl"))
    from loaders import nebius_task_statements, tb2_task_statements
    statements = tb2_task_statements() if args.corpus == "tb2" else nebius_task_statements()

    flags = {t.traj_id: quality_flags(t) for t in trajs}
    usable = [t for t in trajs if not flags[t.traj_id]["exclude"]]
    rng = random.Random(args.seed)
    print(f"sample={len(trajs)} usable={len(usable)}")

    # Stratify by (scaffold, reward, length bucket).  Terminus-2 accounts for roughly
    # half of the corpus, so sampling proportionally would drown out the other scaffolds;
    # we take a bounded number per scaffold instead and report the composition.
    buckets: Dict[Any, List[Trajectory]] = {}
    for t in usable:
        nb = flags[t.traj_id]["n_steps"]
        lb = "m" if nb < 60 else ("l" if nb < 150 else "xl")
        buckets.setdefault((t.agent, t.reward, lb), []).append(t)
    keys = sorted(buckets)
    for k in keys:
        rng.shuffle(buckets[k])

    per_agent = max(1, args.n_traj // max(1, len({t.agent for t in usable})))
    chosen: Dict[str, int] = {}
    picked: List[Trajectory] = []
    round_i = 0
    while len(picked) < args.n_traj and round_i < 200:
        round_i += 1
        progress = False
        for agent in sorted({t.agent for t in usable}):
            if chosen.get(agent, 0) >= per_agent:
                continue
            for k in keys:
                if k[0] != agent or not buckets[k]:
                    continue
                picked.append(buckets[k].pop())
                chosen[agent] = chosen.get(agent, 0) + 1
                progress = True
                break
            if len(picked) >= args.n_traj:
                break
        if not progress:
            break
    # fill any remainder from the largest remaining strata
    while len(picked) < args.n_traj and any(buckets[k] for k in keys):
        k = max(keys, key=lambda kk: len(buckets[kk]))
        if buckets[k]:
            picked.append(buckets[k].pop())
    picked.sort(key=lambda t: flags[t.traj_id]["n_steps"])

    rows: List[Dict[str, Any]] = []
    for tr in picked:
        n = len(tr.steps)
        ends = position_windows(n, args.per_traj, args.w, rng)
        for t in ends:
            cid = f"{args.corpus}_{tr.traj_id}_{t}"
            with open(os.path.join(cards_dir, cid + ".md"), "w", encoding="utf-8") as fh:
                fh.write(card(tr, statements.get(tr.task, ""), t, args.w, cid,
                              extra_note="evenly spaced position sample"))
            rows.append({"card_id": cid, "corpus": args.corpus, "traj_id": tr.traj_id, "task": tr.task,
                         "agent": tr.agent, "model": tr.model, "reward": tr.reward, "n_steps": n,
                         "t": t, "w": args.w, "kind": "position",
                         "placeholder_frac": round(flags[tr.traj_id]["placeholder_frac"], 3),
                         "max_msg_repeat_frac": round(flags[tr.traj_id]["max_msg_repeat_frac"], 3)})

    # control windows: clear expected-stagnant (long exact repeats) and expected-productive
    # (right after a verification improvement), to check labels are not degenerate.
    ctrl = 0
    for tr in picked:
        if ctrl >= args.n_control:
            break
        reps = exact_repeat_runs(tr, k=4)
        imps = verification_improvements(tr)
        for t in reps[:1]:
            if t >= args.w:
                cid = f"{args.corpus}_{tr.traj_id}_{t}_ctrlSTAG"
                with open(os.path.join(cards_dir, cid + ".md"), "w", encoding="utf-8") as fh:
                    fh.write(card(tr, statements.get(tr.task, ""), t, args.w, cid,
                                  extra_note="control: window ends a run of >=4 identical normalized actions"))
                rows.append({"card_id": cid, "corpus": args.corpus, "traj_id": tr.traj_id, "task": tr.task,
                             "agent": tr.agent, "model": tr.model, "reward": tr.reward, "n_steps": len(tr.steps),
                             "t": t, "w": args.w, "kind": "control_stagnant",
                             "placeholder_frac": round(flags[tr.traj_id]["placeholder_frac"], 3),
                             "max_msg_repeat_frac": round(flags[tr.traj_id]["max_msg_repeat_frac"], 3)})
                ctrl += 1
        for t in imps[:1]:
            if ctrl >= args.n_control:
                break
            if t >= args.w:
                cid = f"{args.corpus}_{tr.traj_id}_{t}_ctrlPROD"
                with open(os.path.join(cards_dir, cid + ".md"), "w", encoding="utf-8") as fh:
                    fh.write(card(tr, statements.get(tr.task, ""), t, args.w, cid,
                                  extra_note="control: window ends at a verification state improvement"))
                rows.append({"card_id": cid, "corpus": args.corpus, "traj_id": tr.traj_id, "task": tr.task,
                             "agent": tr.agent, "model": tr.model, "reward": tr.reward, "n_steps": len(tr.steps),
                             "t": t, "w": args.w, "kind": "control_productive",
                             "placeholder_frac": round(flags[tr.traj_id]["placeholder_frac"], 3),
                             "max_msg_repeat_frac": round(flags[tr.traj_id]["max_msg_repeat_frac"], 3)})
                ctrl += 1

    with open(os.path.join(outdir, "cards_index.csv"), "w", newline="", encoding="utf-8") as fh:
        wtr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    with open(os.path.join(outdir, "sample_flags.csv"), "w", newline="", encoding="utf-8") as fh:
        keys_ = ["traj_id", "task", "agent", "model", "reward", "n_steps", "placeholder_frac",
                 "max_msg_repeat_frac", "no_tool_frac", "exclude"]
        wtr = csv.DictWriter(fh, fieldnames=keys_)
        wtr.writeheader()
        for t in trajs:
            f = flags[t.traj_id]
            wtr.writerow({"traj_id": t.traj_id, "task": t.task, "agent": t.agent, "model": t.model,
                          "reward": t.reward, **{k: round(v, 3) if isinstance(v, float) else v
                                                 for k, v in f.items()}})
    print(f"cards={len(rows)} kinds={Counter(r['kind'] for r in rows)} -> {cards_dir}")
    print(f"trajectories used: {len(picked)}; agents={Counter(t.agent for t in picked)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
