#!/usr/bin/env python3
"""Materialise a fresh workspace for one task from ``data/live/tasks.jsonl``.

Usage
-----
    python prepare_workspace.py --task-id <task_id> --target-dir <dir>
    python prepare_workspace.py --list
    python prepare_workspace.py --task-id <task_id> --target-dir <dir> --condition directed

The script is deterministic and safe to call repeatedly: the target directory is
completely removed and rebuilt on every call, and the package tree is restored
from a pinned, hash-verified source archive.  No network access is needed when
``data/live/packages/<pkg>-<version>.zip`` exists; otherwise the exact sdist URL
recorded in the task (with its sha256) is downloaded and verified.

What lands in ``<target_dir>``
------------------------------
    <repo tree>            # the package as published, with gold_file mutated
    .task/task.json        # task metadata (no sources: ids, paths, command)
    .task/objective.md     # condition-dependent task statement (lost|directed)
    .task/run_tests.cmd/.sh  # the exact verifier command, run from <target_dir>

Exit codes: 0 ok, 2 usage/unknown task, 3 archive or hash error, 4 mutation
mismatch (the on-disk archive does not match the recorded original source).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TASKS = os.path.join(HERE, "tasks.jsonl")
PACKAGES_DIR = os.path.join(HERE, "packages")

# fallback if a record lacks an explicit interpreter path
DEFAULT_PYTHON = sys.executable


class TaskError(RuntimeError):
    def __init__(self, message: str, code: int = 3) -> None:
        super().__init__(message)
        self.code = code


def load_tasks(path: str = DEFAULT_TASKS) -> dict:
    tasks = {}
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TaskError("bad JSON on line %d of %s: %s" % (lineno, path, exc), 2)
            tid = rec.get("task_id")
            if not tid:
                raise TaskError("line %d of %s has no task_id" % (lineno, path), 2)
            if tid in tasks:
                raise TaskError("duplicate task_id %r in %s" % (tid, path), 2)
            tasks[tid] = rec
    if not tasks:
        raise TaskError("no tasks found in %s" % path, 2)
    return tasks


def archive_path(rec: dict) -> str:
    return os.path.join(PACKAGES_DIR, "%s-%s.zip" % (rec["package"], rec["package_version"]))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_archive(rec: dict) -> str:
    """Return a verified path to the package archive, downloading if needed."""
    path = archive_path(rec)
    expect = rec.get("source_archive_sha256") or ""
    if os.path.isfile(path):
        if not expect or sha256_file(path) == expect:
            return path
    url = rec.get("source_url")
    if not url:
        raise TaskError("archive %s missing and no source_url recorded" % path)
    os.makedirs(PACKAGES_DIR, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip.part", dir=PACKAGES_DIR)
    os.close(tmp_fd)
    try:
        with urllib.request.urlopen(url, timeout=180) as resp, open(tmp_path, "wb") as out:
            shutil.copyfileobj(resp, out)
        if expect and sha256_file(tmp_path) != expect:
            raise TaskError("downloaded archive hash mismatch for %s" % rec["task_id"])
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return path


def _robust_rmtree(path: str) -> None:
    def on_error(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    if os.path.exists(path):
        shutil.rmtree(path, onerror=on_error)


def extract_archive(archive: str, dest: str, package: str) -> str:
    """Extract the archive; return the relative path of the repo root inside it."""
    with tempfile.TemporaryDirectory(prefix="live_ws_") as tmp:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                name = info.filename
                if name.startswith("/") or ".." in name.replace("\\", "/").split("/"):
                    raise TaskError("unsafe path in archive: %r" % name)
            zf.extractall(tmp)
        names = [n for n in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, n))]
        if len(names) == 1:
            src = os.path.join(tmp, names[0])
        else:
            src = tmp
        shutil.copytree(src, dest)
    return ""


def apply_source(rec: dict, target_dir: str, source_key: str = "mutated_source") -> str:
    """Write the mutated (or original) gold file into the workspace."""
    gold = rec["gold_file"].replace("\\", "/")
    path = os.path.join(target_dir, *gold.split("/"))
    if not os.path.isfile(path):
        raise TaskError("gold file %s not present in the extracted tree at %s" % (gold, target_dir), 4)
    on_disk = open(path, "r", encoding="utf-8", newline="").read()
    original = rec["original_source"]
    if on_disk != original:
        raise TaskError(
            "gold file %s does not match the recorded original source (len %d vs %d); "
            "the package archive and manifest are out of sync" % (gold, len(on_disk), len(original)), 4)
    new = rec["mutated_source"] if source_key == "mutated_source" else rec["original_source"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
    return path


def objective_text(rec: dict, condition: str) -> str:
    pkg = rec["package"]
    ver = rec["package_version"]
    lines = [
        "# Task %s" % rec["task_id"],
        "",
        "A bug has been introduced into one function of the %s %s source tree you have "
        "been given. The project's own test suite currently fails." % (pkg, ver),
        "Repair the source so that the whole test suite passes again.",
        "",
        "Run the tests with:",
        "",
        "    %s" % rec["test_command"],
        "",
    ]
    if condition == "directed":
        lines += [
            "## Location hint",
            "",
            "The defect is in `%s`, inside the function `%s`."
            % (rec["gold_file"], rec["gold_function"]),
            "",
        ]
    else:
        lines += [
            "## Location hint",
            "",
            "None: the defect could be anywhere in the %d source files of this repository."
            % rec.get("n_source_files", 0),
            "",
        ]
    lines += [
        "## Rules",
        "",
        "- Change the package source only; do not edit the tests.",
        "- The fix must be a real source change, not a test modification or a skip.",
        "",
    ]
    return "\n".join(lines)


def write_aux_files(rec: dict, target_dir: str, condition: str) -> None:
    aux = os.path.join(target_dir, ".task")
    os.makedirs(aux, exist_ok=True)
    meta = {
        "task_id": rec["task_id"],
        "package": rec["package"],
        "package_version": rec["package_version"],
        "condition": condition,
        "gold_file": rec["gold_file"],
        "gold_function": rec["gold_function"],
        "bug_kind": rec.get("bug_kind"),
        "test_command": rec["test_command"],
        "python_bin": rec.get("python_bin"),
        "n_source_files": rec.get("n_source_files"),
        "n_test_files": rec.get("n_test_files"),
    }
    with open(os.path.join(aux, "task.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(aux, "objective.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(objective_text(rec, condition))
    py = rec.get("python_bin") or DEFAULT_PYTHON
    target = rec.get("test_target") or ""
    extras = " ".join(rec.get("test_extra_args") or [])
    with open(os.path.join(aux, "run_tests.cmd"), "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("@echo off\r\n\"%s\" -m pytest %s %s %%*\r\n" % (py, target, extras))
    with open(os.path.join(aux, "run_tests.sh"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("#!/bin/sh\n\"%s\" -m pytest %s %s \"$@\"\n" % (py, target, extras))


def prepare(task_id: str, target_dir: str, tasks_path: str = DEFAULT_TASKS,
            condition: str = "lost", source_key: str = "mutated_source",
            write_aux: bool = True) -> dict:
    tasks = load_tasks(tasks_path)
    if task_id not in tasks:
        raise TaskError("unknown task_id %r (see --list)" % task_id, 2)
    rec = tasks[task_id]
    if condition not in ("lost", "directed"):
        raise TaskError("condition must be 'lost' or 'directed'", 2)
    target_dir = os.path.abspath(target_dir)
    archive = ensure_archive(rec)
    _robust_rmtree(target_dir)
    os.makedirs(os.path.dirname(target_dir) or ".", exist_ok=True)
    extract_archive(archive, target_dir, rec["package"])
    gold = apply_source(rec, target_dir, source_key)
    if write_aux:
        write_aux_files(rec, target_dir, condition)
    return {
        "task_id": task_id,
        "workspace": target_dir,
        "gold_file": os.path.relpath(gold, target_dir).replace(os.sep, "/"),
        "condition": condition,
        "applied": source_key,
        "test_command": rec["test_command"],
        "n_source_files": rec.get("n_source_files"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Materialise a live-task workspace.")
    ap.add_argument("--task-id", help="task id from tasks.jsonl")
    ap.add_argument("--target-dir", help="destination workspace directory")
    ap.add_argument("--tasks", default=DEFAULT_TASKS, help="path to tasks.jsonl")
    ap.add_argument("--condition", default="lost", choices=("lost", "directed"),
                    help="task statement variant written to .task/objective.md")
    ap.add_argument("--original", action="store_true",
                    help="write the ORIGINAL (unmutated) source instead of the mutant")
    ap.add_argument("--no-aux", action="store_true", help="do not write .task/ helper files")
    ap.add_argument("--list", action="store_true", help="list available task ids and exit")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)

    if args.list:
        tasks = load_tasks(args.tasks)
        for tid in sorted(tasks):
            rec = tasks[tid]
            print("%s\t%s\t%s\t%s" % (tid, rec["package"], rec["gold_file"],
                                      rec["gold_function"]))
        return 0
    if not args.task_id or not args.target_dir:
        ap.error("--task-id and --target-dir are required unless --list is used")
    try:
        out = prepare(args.task_id, args.target_dir, args.tasks, args.condition,
                      "original_source" if args.original else "mutated_source",
                      not args.no_aux)
    except TaskError as exc:
        print("prepare_workspace: ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print("prepared %s -> %s (condition=%s, applied=%s)"
              % (out["task_id"], out["workspace"], out["condition"], out["applied"]))
        print("test command: %s" % out["test_command"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
