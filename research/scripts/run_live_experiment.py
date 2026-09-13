"""The causal experiment: hold the bug fixed, vary only how easy it is to locate.

WHY THIS EXISTS
The observational result (REBUILD_FINDINGS_V2 §2.29) is correlational: on 19,635 logged runs,
69.1% of failures had already edited a gold-patch file, so localisation is bounded at the 30.9% of
failures that never reach the file.  A reviewer can reasonably answer "that is selection, not
cause".  The only way to answer that is to intervene: take the SAME bug and change ONLY how hard it
is to find, then measure whether finding it is what fixes the run.

DESIGN (pre-registered before the first episode ran; thresholds fixed in PRE_REG below)
Three arms, same tasks, same model, same step budget:
  unhinted  the agent is told a bug exists and must find and fix it.
  hinted    the agent is told the exact file and function.  Localisation solved by fiat.
  verify    unhinted, plus an instruction to run the tests after every edit and reconsider its
            diagnosis when they still fail -- i.e. spend the budget on checking the fix rather
            than on more searching.

PRE-REGISTERED PREDICTIONS, derived from the observational result before running anything:
  P1  hinting raises the success rate only MODESTLY.  Specifically the failure-rate drop from
      unhinted -> hinted should be smaller than the 30.9% of failures attributable to never
      reaching the file.  If hinting removes most failures, the observational result is wrong.
  P2  the verify arm beats the unhinted arm, and by more than the hinted arm does, because the
      binding constraint is fix quality rather than location.
  P3  conditional on reaching the gold file at least once, success should still be well below
      certainty -- the same 69.1% / 98.2% gap, reproduced causally.

An agent run "reaches the file" if it ever reads or writes the gold file; that is logged so P3 is
computable.

Everything is logged to results/live/episodes.jsonl, one record per episode, and the API spend
goes to the study's normal ledger.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall.llm import Gateway  # noqa: E402

LIVE = ROOT / "data" / "live"
OUT = ROOT / "results" / "live"
OUT.mkdir(parents=True, exist_ok=True)
WORK = LIVE / "work"

PRE_REG = {
    "P1_hint_gain_lt_lost_fraction": 0.309,
    "P2_verify_beats_unhinted_and_hint": True,
    "P3_success_given_reached_gold_below_certainty": True,
}

SYSTEM_BASE = """You are a coding agent fixing a bug in a Python project.

You interact with the workspace using exactly one command per reply, on its own line:

  read <path>      show the contents of a file
  write <path>     replace a file; put the new full contents in a fenced ```python block
  test             run the project's test command and see the output
  done             finish; use this only when you believe the bug is fixed

Rules:
- One command per reply. Nothing else on the command line.
- Paths are relative to the repository root you are shown.
- You must call `test` at least once before `done`.
- Replying with `done` ends the episode immediately, so do not use it until the tests pass.
"""

ARM_INSTRUCTIONS = {
    "unhinted": (
        "There is a bug in this project. A test command currently fails. Find the bug and fix it "
        "so that the test suite passes."
    ),
    "hinted": (
        "There is a bug in this project. It is in the file `{gold_file}`, in the function "
        "`{gold_function}`. A test command currently fails. Fix that function so the test suite "
        "passes."
    ),
    "verify": (
        "There is a bug in this project. A test command currently fails. Find the bug and fix it "
        "so that the test suite passes.\n\n"
        "IMPORTANT METHOD: after every edit, run `test`. If the tests still fail, do NOT simply try "
        "another guess -- re-read the failing code and reconsider whether your DIAGNOSIS of the bug "
        "is correct, before making another change."
    ),
}

CMD_RE = re.compile(r"^\s*(read|write|test|done)\b\s*(.*)$", re.I)
FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


# ---------------------------------------------------------------------------- workspace
def materialise(task: Dict[str, Any], dest: Path) -> None:
    """Fresh copy of the package source with the mutated file written in place."""
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    src = Path(task["repo_root"])
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc", ".pytest_cache", ".tox", "*.egg-info"))
    gold = dest / task["gold_file"]
    gold.parent.mkdir(parents=True, exist_ok=True)
    gold.write_text(task["mutated_source"], encoding="utf-8")


def run_tests(dest: Path, cmd: str, timeout: int = 120) -> Tuple[bool, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(dest), capture_output=True,
                           text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, f"[timeout after {timeout}s]"
    except Exception as e:
        return False, f"[error running tests: {type(e).__name__}: {e}]"


def tree(dest: Path, limit: int = 60) -> str:
    files = []
    for p in sorted(dest.rglob("*.py")):
        rel = p.relative_to(dest)
        if any(part.startswith(".") for part in rel.parts):
            continue
        files.append(str(rel).replace("\\", "/"))
        if len(files) >= limit:
            break
    return "\n".join(files)


# ---------------------------------------------------------------------------- episode
def run_episode(task: Dict[str, Any], arm: str, max_turns: int, seed: int,
                tag: str) -> Dict[str, Any]:
    dest = WORK / f"{task['task_id']}__{arm}__s{seed}"
    materialise(task, dest)
    passed0, out0 = run_tests(dest, task["test_command"])

    g = Gateway(session=f"live-{task['task_id']}-{arm}-{seed}", tag=tag, temperature=0.0)
    instr = ARM_INSTRUCTIONS[arm].format(gold_file=task["gold_file"],
                                         gold_function=task.get("gold_function", ""))
    first = (f"{instr}\n\nThe repository is at the current directory. Python files present:\n"
             f"{tree(dest)}\n\nTest command: `{task['test_command']}`\n"
             f"Before you begin, the test output looks like:\n```\n{out0[-1200:]}\n```\n\n"
             f"Send your first command.")
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_BASE},
        {"role": "user", "content": first},
    ]

    gold_rel = task["gold_file"].replace("\\", "/")
    reached_gold = False
    edits = 0
    test_calls = 0
    final_pass = False
    transcript: List[Dict[str, Any]] = []
    write_log: List[Dict[str, Any]] = []
    turns = 0
    err = ""

    for turn in range(max_turns):
        turns = turn + 1
        try:
            rep = g.chat(messages, max_tokens=2000)
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:160]}"
            break
        txt = (rep.get("text") or "").strip()
        cmd_line, cmd_arg = "", ""
        for line in txt.splitlines():
            m = CMD_RE.match(line)
            if m:
                cmd_line, cmd_arg = m.group(1).lower(), m.group(2).strip()
                break
        obs = ""
        if cmd_line == "read":
            p = (dest / cmd_arg.lstrip("./"))
            if gold_rel in cmd_arg.replace("\\", "/") or str(p).endswith(gold_rel):
                reached_gold = True
            try:
                body = p.read_text(encoding="utf-8", errors="replace")
                obs = body[:6000]
            except Exception as e:
                obs = f"[cannot read {cmd_arg}: {type(e).__name__}]"
        elif cmd_line == "write":
            # Pick the LARGEST fenced block, not the first: models routinely emit a short
            # illustrative fragment before (or inside) their reasoning and then the real file.
            # Taking the first block silently wrote 37-byte stubs that the agent then had to
            # redo; taking the largest is the safer reading of "here is the file".
            blocks = FENCE_RE.findall(txt)
            fm_content = max(blocks, key=len) if blocks else None
            if fm_content is None:
                obs = ("[write needs the full new file contents in a ```python block; "
                       "resend as: write <path> then a fenced block]")
            else:
                p = (dest / cmd_arg.lstrip("./"))
                if gold_rel in cmd_arg.replace("\\", "/") or str(p).endswith(gold_rel):
                    reached_gold = True
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(fm_content, encoding="utf-8")
                    edits += 1
                    obs = f"[wrote {cmd_arg}, {len(fm_content)} bytes]"
                    # record the literal bytes written, so an episode can be audited later and
                    # so "did it edit the gold file" is checkable from the transcript alone
                    write_log.append({"turn": turn + 1, "path": cmd_arg,
                                      "bytes": len(fm_content),
                                      "n_fences": len(blocks),
                                      "content": fm_content[:4000]})
                except Exception as e:
                    obs = f"[cannot write {cmd_arg}: {type(e).__name__}: {e}]"
        elif cmd_line == "test":
            test_calls += 1
            ok, o = run_tests(dest, task["test_command"])
            obs = o[-3000:] if o else "[no output]"
        elif cmd_line == "done":
            final_pass, outF = run_tests(dest, task["test_command"])
            transcript.append({"turn": turns, "cmd": "done", "reply": txt[:800],
                               "obs": outF[-1500:], "final": True})
            break
        else:
            obs = ("[unrecognised. Reply with exactly one of: read <path> | write <path> | "
                   "test | done]")
        transcript.append({"turn": turns, "cmd": cmd_line, "arg": cmd_arg[:200],
                           "reply": txt[:800], "obs": obs[-1500:],
                           "obs_full": obs[-6000:]})
        messages.append({"role": "assistant", "content": txt[:4000]})
        messages.append({"role": "user", "content": obs[:4000]})

    if not final_pass and not err:
        final_pass, _ = run_tests(dest, task["test_command"])

    return {
        "task_id": task["task_id"], "package": task.get("package"), "arm": arm, "seed": seed,
        "n_turns": turns, "edits": edits, "test_calls": test_calls,
        "reached_gold": reached_gold, "success": bool(final_pass),
        "fail_before": not passed0, "error": err,
        "usd": round(g.spend.usd, 6), "calls": g.spend.calls,
        "route_failures": dict(g._route_fail),
        "transcript": transcript, "writes": write_log,
    }


# ---------------------------------------------------------------------------- main
def load_tasks(limit: Optional[int], path: Optional[str] = None) -> List[Dict[str, Any]]:
    p = Path(path) if path else (LIVE / "tasks.jsonl")
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        raise SystemExit(f"no task suite at {p} — wait for the builder to finish")
    tasks = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            tasks.append(json.loads(line))
    return tasks[:limit] if limit else tasks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=None, help="path to tasks.jsonl (default data/live/tasks.jsonl)")
    ap.add_argument("--arms", nargs="+", default=["unhinted", "hinted", "verify"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--max-turns", type=int, default=14)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", default="live")
    ap.add_argument("--out", default=None, help="episodes jsonl path (default results/live/episodes.jsonl)")
    args = ap.parse_args()

    tasks = load_tasks(args.limit, args.tasks)
    print(f"tasks: {len(tasks)}  arms: {args.arms}  seeds: {args.seeds}  "
          f"max_turns: {args.max_turns}  workers: {args.workers}")
    episodes = [(t, a, s) for t in tasks for a in args.arms for s in range(args.seeds)]
    print(f"episodes to run: {len(episodes)}")

    out_path = Path(args.out) if args.out else (OUT / "episodes.jsonl")
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    done = 0
    total_usd = 0.0
    t0 = time.time()

    def work(item):
        t, a, s = item
        return run_episode(t, a, args.max_turns, s, args.tag)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, it): it for it in episodes}
        for fut in as_completed(futs):
            t, a, s = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"task_id": t["task_id"], "arm": a, "seed": s, "success": False,
                       "error": f"{type(e).__name__}: {str(e)[:200]}", "usd": 0.0}
            with lock:
                done += 1
                total_usd += rec.get("usd", 0.0)
                with out_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                el = time.time() - t0
                print(f"  [{done}/{len(episodes)}] {t['task_id'][:28]:28s} {a:8s} "
                      f"success={rec.get('success')} turns={rec.get('n_turns')} "
                      f"gold={rec.get('reached_gold')} ${total_usd:.4f}  {el:.0f}s", flush=True)

    print(f"\ndone: {done} episodes, ${total_usd:.4f}, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
