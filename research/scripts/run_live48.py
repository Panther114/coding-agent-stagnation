"""Causal experiment on the 48-task verified suite (8 real packages).

Differs from `run_live_experiment.py` in three ways that the suite requires:

1. Workspaces are materialised by the suite's own `prepare_workspace.py` from pinned zip
   archives, not by copying a `repo_root`.  The two conditions (`lost` / `directed`) differ
   ONLY in `.task/objective.md` -- repo, defect and verifier are byte-identical, which is the
   clean manipulation for the localisation question.
2. Success is **not** exit code.  boltons ships 1 pre-existing failing test and validators 17,
   so an exit-code criterion would mark 12 of 48 tasks permanently broken.  A run succeeds when
   it produces **no failure outside that task's `pre_existing_failures` set**.
3. The recorded interpreter is used (`python_bin`), because these packages are imported from a
   venv rather than the study's environment.

Arms:
  unhinted   condition=lost      the agent must find the defect itself
  hinted     condition=directed  told the exact file and function
  verify     condition=lost      plus an instruction to re-diagnose after a failed test
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
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall.llm import Gateway  # noqa: E402

SUITE = ROOT / "data" / "live"
OUT = ROOT / "results" / "live"
WORK = SUITE / "work48"
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

FAILED_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.M)

TOOLS = [
    {"type": "function", "function": {
        "name": "read", "description": "Show the contents of a file in the repository.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write", "description": "Replace a file with new full contents.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "test", "description": "Run the project's test suite and see the output.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "done", "description": "Finish. Call when you believe the defect is fixed.",
        "parameters": {"type": "object", "properties": {}}}},
]

VERIFY_INSTRUCTION = (
    "\n\nIMPORTANT METHOD: after every edit, run the tests. If they still fail, do NOT simply try "
    "another guess -- re-read the failing code and reconsider whether your DIAGNOSIS of the defect "
    "is correct before making another change."
)

SYSTEM = """You are a coding agent fixing a defect in a Python project.

Use the provided tools. Rules:
- Call `read` before editing a file you have not seen.
- `write` replaces the whole file, so include the complete new contents.
- Call `test` to run the suite. Call `done` only when you believe the defect is fixed.
"""


def prepare(task_id: str, dest: Path, condition: str, python: str) -> bool:
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        [python, "prepare_workspace.py", "--task-id", task_id,
         "--target-dir", str(dest), "--condition", condition],
        cwd=str(SUITE), capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        print(f"    prepare failed: {(p.stdout + p.stderr)[-300:]}")
        return False
    return True


def run_tests(dest: Path, task: Dict[str, Any], timeout: int = 300) -> Tuple[Set[str], str]:
    """Return (set of failing node ids, raw output). Never raises."""
    py = task.get("python_bin") or sys.executable
    args = task.get("test_args") or ["tests", "-q", "--no-header", "-p", "no:cacheprovider"]
    cmd = [py, "-m", "pytest"] + list(args)
    env = dict(os.environ)
    if task.get("env_pythonpath"):
        env["PYTHONPATH"] = str(task["env_pythonpath"])
    try:
        p = subprocess.run(cmd, cwd=str(dest), capture_output=True, text=True,
                           timeout=timeout, env=env)
        out = (p.stdout or "") + (p.stderr or "")
        return set(FAILED_RE.findall(out)), out
    except subprocess.TimeoutExpired:
        return {"<timeout>"}, f"[timeout after {timeout}s]"
    except Exception as e:
        return {"<error>"}, f"[{type(e).__name__}: {e}]"


def is_success(fails: Set[str], pre: Set[str]) -> bool:
    """No failure outside the task's known pre-existing set."""
    return len({f for f in fails if f not in pre}) == 0


def materialise(task: Dict[str, Any], arm: str, seed: int) -> Optional[Tuple[Path, Path]]:
    dest = WORK / f"{task['task_id']}__{arm}__s{seed}"
    condition = "directed" if arm == "hinted" else "lost"
    py = task.get("python_bin") or sys.executable
    if not prepare(task["task_id"], dest, condition, py):
        return None
    pristine = WORK / (dest.name + "__pristine")
    if pristine.exists():
        shutil.rmtree(pristine, ignore_errors=True)
    shutil.copytree(dest, pristine, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache"))
    return dest, pristine


def is_test_path(rel: str) -> bool:
    parts = [x.lower() for x in Path(rel).parts]
    if any(x in ("tests", "test") for x in parts[:-1]):
        return True
    n = Path(rel).name.lower()
    return n.startswith("test_") or n.endswith("_test.py") or n == "conftest.py"


# --- the "masked" condition ------------------------------------------------------------------
# Every live arm so far reached the gold file 100% of the time, which made the router's SEARCH
# branch untestable.  Inspecting the transcripts showed why: pytest prints the failing test's FILE
# NAME, and that name contains the module name (e.g. "test_ioutils.py" -> "ioutils.py"), so
# locating the defect is a string match rather than a diagnosis -- 51.5% of the test observations
# handed to the agent literally name the gold module.  In the masked condition the agent is told
# only THAT tests fail, never which ones or where.  The grader still sees the real output; only
# what the agent is shown changes, so the success criterion is untouched.
_COUNT_LINE = re.compile(r"^\s*=*\s*(\d+\s+(?:failed|passed|error)[^\n]*)$", re.M)
MASK_PREAMBLE = ("[test run complete -- the failing test names, file paths and tracebacks are "
                 "withheld by this project's CI configuration]\n")


def mask_output(out: str) -> str:
    """Keep the pass/fail counts; remove every hint of *where* the failure is."""
    hits = _COUNT_LINE.findall(out or "")
    counts = hits[-1].strip() if hits else ""
    tail = ("\nNo failing test names, no module names and no tracebacks are available. "
            "Determine the defect by reading the code.\n")
    return MASK_PREAMBLE + (counts + "\n" if counts else "test run finished\n") + tail


def restore_tests(pristine: Path, dest: Path) -> int:
    """Restore the original verifier before FINAL grading only."""
    removed = 0
    if pristine.exists():
        for p in pristine.rglob("*"):
            if p.is_file():
                rel = p.relative_to(pristine)
                if is_test_path(str(rel)):
                    tgt = dest / rel
                    tgt.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, tgt)
    for p in list(dest.rglob("*")):
        if p.is_file():
            rel = p.relative_to(dest)
            if is_test_path(str(rel)) and not (pristine / rel).exists():
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    pass
    return removed


def run_episode(task: Dict[str, Any], arm: str, seed: int, max_turns: int, tag: str) -> Dict[str, Any]:
    got = materialise(task, arm, seed)
    if got is None:
        return {"task_id": task["task_id"], "arm": arm, "seed": seed, "success": False,
                "error": "prepare_workspace failed", "usd": 0.0, "n_turns": 0}
    dest, pristine = got
    pre = set(task.get("pre_existing_failures") or [])
    fails0, out0 = run_tests(dest, task)

    # timeout=120, max_retries=2: the international route fails intermittently (measured: 1 in 3
    # probes), and the default 4 retries x 180 s could burn 12 minutes on one request before the
    # domestic fallback was tried.  This keeps a bad patch cheap so the chain fails over fast.
    g = Gateway(session=f"l48-{task['task_id']}-{arm}-{seed}", tag=tag, temperature=0.0,
                timeout=120, max_retries=2)
    obj = ""
    objf = dest / ".task" / "objective.md"
    if objf.exists():
        obj = objf.read_text(encoding="utf-8", errors="replace")
    first_out = mask_output(out0) if arm == "masked" else out0[-1500:]
    first = (f"{obj}\n\nThe repository is the current directory.\n"
             f"Test command: `{task['test_command']}`\n"
             f"Current test output (tail):\n```\n{first_out}\n```\n\nSend your first tool call.")
    if arm == "verify":
        first += VERIFY_INSTRUCTION

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": first},
    ]
    gold_rel = str(task["gold_file"]).replace("\\", "/")
    reached_gold = edits = test_calls = n_tamper = n_empty = 0
    final_ok = False
    transcript: List[Dict[str, Any]] = []
    writes: List[Dict[str, Any]] = []
    turns = 0
    err = ""

    for turn in range(max_turns):
        turns = turn + 1
        done_early = False
        try:
            rep = g.chat(messages, max_tokens=3500, tools=TOOLS)
            if not (rep.get("tool_calls") or (rep.get("text") or "").strip()):
                n_empty += 1
                rep = g.chat(messages, max_tokens=3500, tools=TOOLS)
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:150]}"
            break
        txt = (rep.get("text") or "").strip()
        tcs = rep.get("tool_calls") or []
        if not tcs:
            obs = ("[No tool call received. Use the tools: read, write, test, done.]")
            transcript.append({"turn": turns, "cmd": "", "obs": obs})
            messages.append({"role": "assistant", "content": txt[:3000] or "(no content)"})
            messages.append({"role": "user", "content": obs})
            continue

        parts: List[str] = []
        for tc in tcs:
            fn = tc.get("function") or {}
            name = (fn.get("name") or "").lower()
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            if name == "read":
                arg = str(args.get("path", ""))
                p = dest / arg.lstrip("./")
                if gold_rel in arg.replace("\\", "/") or str(p).endswith(gold_rel):
                    reached_gold = 1
                try:
                    parts.append(p.read_text(encoding="utf-8", errors="replace")[:6000])
                except Exception as e:
                    parts.append(f"[cannot read {arg}: {type(e).__name__}]")
            elif name == "write":
                arg = str(args.get("path", ""))
                content = args.get("content", "")
                p = dest / arg.lstrip("./")
                if gold_rel in arg.replace("\\", "/") or str(p).endswith(gold_rel):
                    reached_gold = 1
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content, encoding="utf-8")
                    edits += 1
                    parts.append(f"[wrote {arg}, {len(content)} bytes]")
                    writes.append({"turn": turns, "path": arg, "bytes": len(content),
                                   "content": content[:3000]})
                except Exception as e:
                    parts.append(f"[cannot write {arg}: {type(e).__name__}: {e}]")
            elif name == "test":
                test_calls += 1
                f, o = run_tests(dest, task)
                new = {x for x in f if x not in pre}
                # the grader always sees the real output; the AGENT sees a masked view when the
                # arm is "masked", so that success is measured on the true suite while the agent
                # has to diagnose the defect instead of reading its location off the traceback
                shown = mask_output(o) if arm == "masked" else o[-2500:]
                parts.append((f"[{len(new)} failing test(s) outside the known pre-existing set] "
                              if new else "[all tests pass] ") + shown)
            elif name == "done":
                n_tamper += restore_tests(pristine, dest)
                f, o = run_tests(dest, task)
                final_ok = is_success(f, pre)
                transcript.append({"turn": turns, "cmd": "done", "obs": o[-1200:]})
                messages.append({"role": "assistant", "content": txt[:3000] or None,
                                 "tool_calls": tcs})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                 "content": o[-3000:]})
                done_early = True
                break
            else:
                parts.append(f"[unknown tool {name!r}]")

        obs = "\n".join(parts) if parts else "[no output]"
        transcript.append({"turn": turns,
                           "cmd": (tcs[0].get("function") or {}).get("name", ""),
                           "reply": txt[:600], "obs": obs[-1500:]})
        messages.append({"role": "assistant", "content": txt[:3000] or None, "tool_calls": tcs})
        for tc in tcs:
            messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": obs[:4000]})
        if done_early:
            break

    if not final_ok and not err:
        n_tamper += restore_tests(pristine, dest)
        f, _ = run_tests(dest, task)
        final_ok = is_success(f, pre)

    return {
        "task_id": task["task_id"], "package": task.get("package"), "arm": arm, "seed": seed,
        "n_turns": turns, "edits": edits, "test_calls": test_calls, "reached_gold": bool(reached_gold),
        "success": bool(final_ok), "fail_before": len({x for x in fails0 if x not in pre}) > 0,
        "test_files_removed": n_tamper, "n_empty": n_empty, "error": err,
        "gold_file": task["gold_file"], "n_source_files": task.get("n_source_files"),
        "usd": round(g.spend.usd, 6), "calls": g.spend.calls,
        "route_failures": dict(g._route_fail),
        "writes": writes, "transcript": transcript,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="data/live/tasks.jsonl")
    ap.add_argument("--arms", nargs="+", default=["unhinted", "hinted", "verify"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--max-turns", type=int, default=14)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--tag", default="live48")
    ap.add_argument("--python-bin", default=None,
                    help="interpreter used to run the task suites. Overrides the value recorded "
                         "in tasks.jsonl. Needed because that recorded a venv under D:\\Devs\\temp "
                         "which was deleted between runs -- every episode then died with "
                         "FileNotFoundError before its first tool call, and the failure looked "
                         "like a result (0/48 success, 0%% reached gold) until the transcripts were "
                         "read. The suite is now built in-repo at research/data/live/.venv.")
    ap.add_argument("--out", default="results/live/episodes48.jsonl")
    args = ap.parse_args()

    tp = Path(args.tasks)
    if not tp.is_absolute():
        tp = ROOT / tp
    tasks = [json.loads(l) for l in tp.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        tasks = tasks[: args.limit]
    if args.python_bin:
        missing = [t["task_id"] for t in tasks
                   if not Path(t.get("python_bin") or "").exists()]
        print(f"--python-bin override -> {args.python_bin}  "
              f"(replaces {len(missing)} task(s) whose recorded interpreter is missing)")
        for t in tasks:
            t["python_bin"] = args.python_bin
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    eps = [(t, a, s) for t in tasks for a in args.arms
           for s in range(args.seed_start, args.seed_start + args.seeds)]
    print(f"tasks={len(tasks)} arms={args.arms} episodes={len(eps)} workers={args.workers}",
          flush=True)

    lock = threading.Lock()
    done = 0
    usd = 0.0
    t0 = time.time()

    def work(it):
        t, a, s = it
        return run_episode(t, a, s, args.max_turns, args.tag)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, it): it for it in eps}
        for fut in as_completed(futs):
            t, a, s = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"task_id": t["task_id"], "arm": a, "seed": s, "success": False,
                       "error": f"{type(e).__name__}: {str(e)[:150]}", "usd": 0.0,
                       "n_turns": None, "writes": [], "transcript": []}
            with lock:
                done += 1
                usd += rec.get("usd", 0.0) or 0.0
                with out_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                print(f"  [{done}/{len(eps)}] {str(t['task_id'])[:44]:44s} {a:8s} "
                      f"ok={str(rec.get('success')):5s} turns={rec.get('n_turns')} "
                      f"gold={rec.get('reached_gold')} ${usd:.4f} {time.time()-t0:.0f}s", flush=True)

    print(f"\ndone {done} episodes, ${usd:.4f}, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
