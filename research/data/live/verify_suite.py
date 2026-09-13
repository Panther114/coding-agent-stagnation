#!/usr/bin/env python3
"""End-to-end verification of every task in ``data/live/tasks.jsonl``.

For each task this script rebuilds the workspace twice with ``prepare_workspace.py``
and runs the real vendor test suite:

  1. buggy state must FAIL, and the recorded ``failure_signature`` must be among
     the observed failures;
  2. restored state must PASS, i.e. no failures other than the task's recorded
     ``pre_existing_failures``.

Nothing here is inferred from the build session: the workspace comes only from
``tasks.jsonl`` plus the pinned archives, exactly as a run-time harness would do it.

    python verify_suite.py                 # verify all tasks
    python verify_suite.py --task-id <id>  # verify one task
    python verify_suite.py --sample 5      # verify a deterministic sample
    python verify_suite.py --json-report out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prepare_workspace as pw  # noqa: E402

DEFAULT_TASKS = os.path.join(HERE, "tasks.jsonl")


def run_pytest(rec, workspace, timeout, json_dir):
    """Run the task's own test command; return (failed node ids, passed count, info)."""
    rep = os.path.join(json_dir, "rep.json")
    cfg_args = list(rec["test_args"]) + [
        "-p", "no:randomly",
        "--json-report", "--json-report-file=" + rep,
        "--json-report-omit=log,collectors,traceback",
    ]
    cmd = [rec["python_bin"], "-m", "pytest"] + cfg_args
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if rec.get("env_pythonpath"):
        env["PYTHONPATH"] = os.path.join(workspace, rec["env_pythonpath"])
    if os.path.exists(rep):
        os.unlink(rep)
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=workspace, env=env, capture_output=True,
                              text=True, timeout=timeout, errors="replace")
        out, rc = (proc.stdout or "") + (proc.stderr or ""), proc.returncode
    except subprocess.TimeoutExpired:
        return None, 0, {"timeout": True, "sec": timeout, "cmd": cmd}
    dt = time.time() - t0
    failed, passed, skipped = [], 0, 0
    if os.path.exists(rep):
        with open(rep, encoding="utf-8") as fh:
            data = json.load(fh)
        for t in data.get("tests", []):
            if t.get("outcome") == "failed":
                failed.append(t["nodeid"])
            elif t.get("outcome") == "error":
                failed.append(t["nodeid"])
            elif t.get("outcome") == "passed":
                passed += 1
            elif t.get("outcome") == "skipped":
                skipped += 1
        try:
            os.unlink(rep)
        except OSError:
            pass
        return failed, passed, {"sec": round(dt, 2), "rc": rc, "cmd": cmd,
                                "skipped": skipped}
    return None, passed, {"sec": round(dt, 2), "rc": rc, "cmd": cmd,
                          "output_tail": out[-600:]}


def verify_task(rec, timeout=900, workdir=None, keep=False):
    result = {"task_id": rec["task_id"], "ok": False, "errors": []}
    tmp = workdir or tempfile.mkdtemp(prefix="live_verify_")
    try:
        ws = os.path.join(tmp, "workspace_mutated")
        pw.prepare(rec["task_id"], ws, DEFAULT_TASKS, "lost", "mutated_source", True)
        failed, passed, info = run_pytest(rec, ws, timeout, tmp)
        result["buggy_passed"] = passed
        result["buggy_sec"] = info["sec"]
        if failed is None:
            result["errors"].append("buggy run did not produce a test report "
                                    "(collection/import failure or timeout)")
            result["buggy_tail"] = info.get("output_tail", "")
            return result
        result["buggy_failures"] = failed
        result["n_buggy_failures"] = len(failed)
        if not failed:
            result["errors"].append("no tests failed with the bug present")
            return result
        sig = rec["failure_signature"]
        if sig not in failed:
            result["errors"].append("recorded failure_signature %s not among observed "
                                    "failures %s" % (sig, failed[:5]))
        allowed = set(rec.get("pre_existing_failures", []))
        unexpected = [f for f in failed if f not in allowed]
        if not unexpected:
            result["errors"].append("all failures are pre-existing; mutation has no effect")
            return result

        ws2 = os.path.join(tmp, "workspace_restored")
        pw.prepare(rec["task_id"], ws2, DEFAULT_TASKS, "lost", "original_source", True)
        failed2, passed2, info2 = run_pytest(rec, ws2, timeout, tmp)
        result["restored_passed"] = passed2
        result["restored_sec"] = info2["sec"]
        if failed2 is None:
            result["errors"].append("restored run did not produce a test report")
            result["restored_tail"] = info2.get("output_tail", "")
            return result
        result["restored_failures"] = failed2
        leftover = [f for f in failed2 if f not in allowed]
        if leftover:
            result["errors"].append("restored source still fails: %s" % leftover[:5])
            return result
        result["ok"] = not result["errors"]
        return result
    finally:
        if not keep and workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify every live task fails-before/passes-after.")
    ap.add_argument("--tasks", default=DEFAULT_TASKS)
    ap.add_argument("--task-id", action="append", default=None)
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--json-report")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    tasks = pw.load_tasks(args.tasks)
    ids = sorted(tasks)
    if args.task_id:
        ids = [t for t in ids if t in set(args.task_id)]
        missing = set(args.task_id) - set(ids)
        if missing:
            print("unknown task ids: %s" % sorted(missing), file=sys.stderr)
            return 2
    if args.sample:
        step = max(1, len(ids) // args.sample)
        ids = ids[::step][:args.sample]

    results, bad = [], []
    t0 = time.time()
    for i, tid in enumerate(ids, 1):
        res = verify_task(tasks[tid], timeout=args.timeout)
        results.append(res)
        flag = "OK  " if res["ok"] else "FAIL"
        if not res["ok"]:
            bad.append(res)
        if not args.quiet:
            print("[%d/%d] %s %-52s buggy_fail=%-3s restored_pass=%-4s %ss" % (
                i, len(ids), flag, tid[:52], res.get("n_buggy_failures", "-"),
                res.get("restored_passed", "-"), res.get("buggy_sec", "-")), flush=True)
            for e in res["errors"]:
                print("        ! %s" % e, flush=True)
    dt = time.time() - t0
    summary = {"tasks_checked": len(ids), "ok": len(ids) - len(bad), "failed": len(bad),
               "bad_task_ids": [b["task_id"] for b in bad], "seconds": round(dt, 1)}
    print("\n== verification: %d/%d ok, %d bad, %.1fs ==" % (
        summary["ok"], summary["tasks_checked"], summary["failed"], dt))
    if bad:
        print("bad tasks: %s" % ", ".join(summary["bad_task_ids"]))
    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as fh:
            json.dump({"summary": summary, "results": results}, fh, indent=2)
        print("report written to %s" % args.json_report)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
