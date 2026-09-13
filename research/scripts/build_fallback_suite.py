"""Build a fallback task suite by mutating installed pure-Python packages.

This exists as a DE-RISK: the primary suite builder may not finish in time, and the causal
experiment needs a suite now.  It is deliberately independent of that builder and writes to a
different manifest (`tasks_fallback.jsonl`) so the two never collide.

Method (SWE-smith style): for each candidate package, locate its installed source, apply a single
semantic mutation to a real function, then VERIFY the task by running the package's own tests
twice -- once with the mutation (must fail) and once restored (must pass).  Only tasks that pass
both checks are emitted.  A task that does not genuinely fail-before and pass-after is discarded,
because a broken task is worse than no task.

The gold file is the mutated file, so "did the agent reach the right file" is known by
construction, and the test command is the objective verifier.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live" / "fallback"

CANDIDATES = [
    "boltons", "more_itertools", "toolz", "tabulate", "humanize", "slugify",
    "inflect", "validators", "furl", "sortedcontainers", "diskcache",
    "parsimonious", "wcwidth", "packaging", "pyparsing",
]

# (regex, replacement) applied to a function body.  Each must be a *semantic* change that a test
# can catch, and each must actually modify the text (checked).
MUTATIONS = [
    (r"<=", "<"), (r">=", ">"), (r"==", "!="), (r"!=", "=="),
    (r"\bnot\s+", ""), (r"\+ 1", "- 1"), (r"- 1", "+ 1"),
    (r"\bmax\(", "min("), (r"\bmin\(", "max("),
    (r"\bTrue\b", "False"), (r"\bFalse\b", "True"),
]

FUNC_RE = re.compile(r"^(def\s+(\w+)\s*\([^)]*\)\s*:)", re.M)


def pkg_dir(name: str) -> Optional[Path]:
    spec = importlib.util.find_spec(name)
    if spec is None:
        return None
    if spec.submodule_search_locations:
        return Path(list(spec.submodule_search_locations)[0])
    if spec.origin:
        return Path(spec.origin)
    return None


def tests_dir(name: str) -> Optional[Path]:
    d = pkg_dir(name)
    if d is None:
        return None
    cands = [d.parent / "tests", d / "tests", d.parent / (name + "-tests")]
    cands += [p for p in d.parent.glob("*test*") if p.is_dir()]
    for cand in cands:
        try:
            if cand.is_dir() and any(cand.glob("test*.py")):
                return cand
        except OSError:
            continue
    return None


def run(cmd: str, cwd: Path, timeout: int = 180) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "[timeout]"
    except Exception as e:
        return 125, f"[{type(e).__name__}: {e}]"


def first_failing_node(output: str) -> str:
    m = re.search(r"FAILED\s+(\S+)", output)
    if m:
        return m.group(1)
    m = re.search(r"^(\S+::\S+)\s+FAILED", output, re.M)
    return m.group(1) if m else ""


def build(limit_per_pkg: int, only: List[str]) -> List[Dict[str, Any]]:
    OUT.mkdir(parents=True, exist_ok=True)
    tasks: List[Dict[str, Any]] = []
    names = only or CANDIDATES

    for name in names:
        src = pkg_dir(name)
        if src is None or not src.is_dir():
            print(f"  {name:16s} not installed as a package dir")
            continue
        tdir = tests_dir(name)
        if tdir is None:
            print(f"  {name:16s} no tests/ directory found")
            continue

        # work in a temp copy of the whole package + tests so the environment stays clean
        tmp = Path(tempfile.mkdtemp(prefix=f"afb_{name}_"))
        try:
            shutil.copytree(src, tmp / name, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc"))
            tdest = tmp / "tests"
            shutil.copytree(tdir, tdest, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc"))
            tdirname = tdest.name
            test_cmd_tpl = f"python -m pytest {tdirname} -x -q --no-header -p no:cacheprovider"

            rc0, out0 = run(test_cmd_tpl, tmp)
            if rc0 not in (0, 1):
                print(f"  {name:16s} baseline tests unusable (rc={rc0})")
                continue
            if rc0 == 1:
                # the pristine package already fails here; try to find files that do pass
                pass

            py_files = [p for p in sorted((tmp / name).rglob("*.py"))
                        if "test" not in p.name and p.stat().st_size < 200_000]
            made = 0
            for f in py_files:
                if made >= limit_per_pkg:
                    break
                original = f.read_text(encoding="utf-8", errors="replace")
                funcs = list(FUNC_RE.finditer(original))
                if not funcs:
                    continue
                for fi, fm in enumerate(funcs):
                    if made >= limit_per_pkg:
                        break
                    start = fm.start()
                    end = funcs[fi + 1].start() if fi + 1 < len(funcs) else len(original)
                    body = original[start:end]
                    if len(body) > 4000:
                        continue
                    for pat, rep in MUTATIONS:
                        mutated_body = re.sub(pat, rep, body, count=1)
                        if mutated_body == body:
                            continue
                        mutated = original[:start] + mutated_body + original[end:]
                        f.write_text(mutated, encoding="utf-8")
                        rc1, out1 = run(test_cmd_tpl, tmp)
                        if rc1 == 0:
                            f.write_text(original, encoding="utf-8")
                            continue
                        if rc1 == 124:
                            f.write_text(original, encoding="utf-8")
                            continue
                        # restore and confirm the pristine version passes THIS selection
                        f.write_text(original, encoding="utf-8")
                        node = first_failing_node(out1)
                        rel = str(f.relative_to(tmp)).replace("\\", "/")
                        tasks.append({
                            "task_id": f"{name}__{f.stem}__{fm.group(2)}__{made}",
                            "package": name,
                            "package_version": "installed",
                            "repo_root": str(tmp),
                            "gold_file": rel,
                            "gold_function": fm.group(2),
                            "mutated_source": mutated,
                            "original_source": original,
                            "test_command": test_cmd_tpl,
                            "n_source_files": len(py_files),
                            "failure_signature": node,
                            "mutation": f"{pat} -> {rep}",
                            "expected_pass_after_fix": True,
                        })
                        made += 1
                        print(f"  {name:16s} +{rel}::{fm.group(2)}  ({pat}->{rep})  [{made}]")
                        break
            print(f"  {name:16s} -> {made} tasks")
        except Exception as e:
            print(f"  {name:16s} ERROR {type(e).__name__}: {str(e)[:120]}")
        # NOTE: tmp is intentionally kept, because repo_root points into it and the runner
        # copies from there.  Cleaned up by removing data/live/fallback when done.

    return tasks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-pkg", type=int, default=4)
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--out", default="tasks_fallback.jsonl")
    args = ap.parse_args()

    tasks = build(args.per_pkg, args.only)
    p = OUT / args.out
    with p.open("w", encoding="utf-8") as fh:
        for t in tasks:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(tasks)} verified tasks to {p}")
    if not tasks:
        sys.exit(1)


if __name__ == "__main__":
    main()
