"""Generate reduced-context cards for the second annotation pass.

Round 1 cards show 14 steps of context before and after each window.  Round 2 cards show
only the window itself plus 3 steps on each side, which makes the second pass a genuinely
different judgement task rather than a re-read of the same evidence, and gives a usable
estimate of label stability under reduced information.

Usage: python scripts/make_pass2_cards.py --corpus tb2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import paths  # noqa: E402
from export_trace import step_line  # noqa: E402
from loaders import Action, Step, Trajectory, nebius_task_statements, tb2_task_statements  # noqa: E402


def load_sample(path: str) -> Dict[str, Trajectory]:
    out = {}
    for line in open(path, encoding="utf-8"):
        b = json.loads(line)
        steps = [Step(index=i, text=s["text"],
                      actions=[Action(a["name"], a["arg"]) for a in s["actions"]],
                      observation=s["obs"]) for i, s in enumerate(b["steps"])]
        out[b["traj_id"]] = Trajectory(traj_id=b["traj_id"], task=b["task"], agent=b["agent"],
                                       model=b["model"], reward=b["reward"], steps=steps, meta=b["meta"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--ctx", type=int, default=3)
    args = ap.parse_args()
    ann = os.path.join(paths.DATA, "annotations", args.corpus)
    proc = os.path.join(paths.PROCESSED, args.corpus)
    outdir = os.path.join(ann, "cards_p2")
    os.makedirs(outdir, exist_ok=True)

    trajs = load_sample(os.path.join(proc, "sample_trajectories.jsonl"))
    stmts = tb2_task_statements() if args.corpus == "tb2" else nebius_task_statements()
    index = [l for l in open(os.path.join(ann, "cards_index.csv"), encoding="utf-8")][1:]
    n = 0
    for line in index:
        parts = line.rstrip("\n").split(",")
        card_id, traj_id, t, w = parts[0], parts[2], int(parts[8]), int(parts[9])
        tr = trajs.get(traj_id)
        if tr is None:
            continue
        lo = max(0, t - w + 1)
        out: List[str] = [f"# Annotation card (round 2, reduced context) `{card_id}`", ""]
        out.append(f"- scaffold `{tr.agent}`, model `{tr.model}`, trajectory length {len(tr.steps)} steps,"
                   f" final reward {tr.reward}")
        out.append(f"- **window under judgement: steps {lo}–{t} (w={w})**")
        out.append("")
        out.append("## Task statement")
        out.append("```text")
        out.append((stmts.get(tr.task, "(not recoverable)") or "")[:2000])
        out.append("```")
        out.append("")
        a0 = max(0, lo - args.ctx)
        out.append(f"## Immediately before (steps {a0}–{lo-1})")
        out.append("```text")
        out.extend(step_line(tr, i, obs_chars=160, text_chars=140) for i in range(a0, lo))
        out.append("```")
        out.append("")
        out.append(f"## WINDOW (steps {lo}–{t})")
        out.append("```text")
        out.extend(step_line(tr, i, obs_chars=260, text_chars=220) for i in range(lo, t + 1))
        out.append("```")
        out.append("")
        b1 = min(len(tr.steps), t + 1 + args.ctx)
        out.append(f"## Immediately after (steps {t+1}–{b1-1})")
        out.append("```text")
        out.extend(step_line(tr, i, obs_chars=160, text_chars=140) for i in range(t + 1, b1))
        out.append("```")
        out.append("")
        out.append("## Your label")
        out.append("```")
        out.append("label: PRODUCTIVE | STAGNANT | REGRESSION | DONE_REDUNDANT | BLOCKED_EXTERNAL | UNCERTAIN")
        out.append("confidence: high | medium | low")
        out.append("channels_advanced: E | I | V | none")
        out.append("justification: at most 25 words, cite step numbers")
        out.append("```")
        with open(os.path.join(outdir, card_id + ".md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
        n += 1
    print(f"wrote {n} reduced-context cards to {outdir}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
