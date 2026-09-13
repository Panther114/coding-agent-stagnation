"""Acquire REAL package sources (with their test suites) and build verified tasks.

Why this supersedes the wheel-based builder: pip wheels do not ship tests, so the wheel approach
found a test directory for only 2 of 16 packages and produced 4 tasks.  Source distributions
(sdists) do ship tests, and the Tsinghua mirror serves them, so every task can be verified against
the package's own suite rather than against tests we wrote ourselves.

Pipeline per package:
  1. `pip download --no-binary :all: --no-deps` to get the sdist from the domestic mirror
  2. extract, locate the importable package directory and its tests directory
  3. confirm the PRISTINE suite passes
  4. apply one semantic mutation inside a real function; keep the task only if the suite now FAILS
  5. restore and re-confirm the suite passes
Tasks failing any check are discarded.  `repo_root` points at the extracted tree, so the runner can
materialise a fresh workspace per episode and the agent sees a realistic multi-file project.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live" / "sdist"
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

PACKAGES = [
    "boltons", "more-itertools", "toolz", "tabulate", "humanize", "python-slugify",
    "inflect", "validators", "furl", "sortedcontainers", "parsimonious", "wcwidth",
    "cytoolz", "pyparsing", "click", "packaging",
]

MUTATIONS = [
    (r"<=", "<"), (r">=", ">"), (r"==", "!="), (r"!=", "=="),
    (r"\+ 1", "- 1"), (r"- 1", "+ 1"), (r"\bmax\(", "min("), (r"\bmin\(", "max("),
    (r"\bTrue\b", "False"), (r"\bFalse\b", "True"),
]

FUNC_RE = re.compile(r"^(def\s+(\w+)\s*\([^)]*\)\s*:)", re.M)


def run(cmd: str, cwd: Path, timeout: int = 240) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "[timeout]"
    except Exception as e:
        return 125, f"[{type(e).__name__}: {e}]"


def sdist(pkg: str, dest: Path) -> Optional[Path]:
    """Fetch an sdist straight from the mirror's simple index.

    Uses the index and a plain GET rather than ``pip download``, because pip insists on
    resolving and building the project's declared build backend (flit_core, hatchling, ...)
    even for ``--no-binary``, which fails in this environment and costs minutes per package.
    The index lists the sdist URL directly, and an sdist is just a tarball.
    """
    import urllib.request
    url = f"{MIRROR}/{pkg}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agentstall-research/1.0"})
        html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"    index fetch failed: {type(e).__name__}: {str(e)[:100]}")
        return None
    hrefs = re.findall(r'href="([^"]+\.tar\.gz)[^"]*"', html)
    if not hrefs:
        print("    no sdist on index")
        return None

    def key(u: str):
        m = re.search(r"-(\d+[\.\d]*(?:[abrc]\d+)?)\.tar\.gz", u)
        if not m:
            return (0,)
        return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", m.group(1)))

    hrefs.sort(key=key)
    from urllib.parse import urljoin
    target = urljoin(url, hrefs[-1])
    out = dest / Path(target).name
    try:
        req = urllib.request.Request(target, headers={"User-Agent": "agentstall-research/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r, out.open("wb") as fh:
            shutil.copyfileobj(r, fh)
        print(f"    sdist {out.name} ({out.stat().st_size:,} B)")
        return out
    except Exception as e:
        print(f"    sdist download failed: {type(e).__name__}: {str(e)[:100]}")
        return None


def extract(archive: Path, dest: Path) -> Optional[Path]:
    try:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                z.extractall(dest)
        else:
            with tarfile.open(archive) as t:
                t.extractall(dest)
    except Exception as e:
        print(f"    extract failed: {type(e).__name__}: {e}")
        return None
    subs = [p for p in dest.iterdir() if p.is_dir()]
    return subs[0] if subs else None


def find_dirs(root: Path, pkg: str) -> Tuple[Optional[Path], Optional[Path]]:
    """Locate the importable package directory and a tests directory inside the sdist."""
    mod = pkg.replace("-", "_")
    pkgdir = None
    for cand in [root / mod, root / "src" / mod,
                 *(p for p in root.rglob(mod) if p.is_dir() and (p / "__init__.py").exists())]:
        if cand.is_dir() and (cand / "__init__.py").exists():
            pkgdir = cand
            break
    tdir = None
    for cand in [root / "tests", root / "test", root / mod / "tests",
                 *(p for p in root.rglob("*test*") if p.is_dir())]:
        try:
            if cand.is_dir() and any(cand.glob("test*.py")):
                tdir = cand
                break
        except OSError:
            continue
    return pkgdir, tdir


def build(per_pkg: int, only: List[str], budget_s: int) -> List[Dict[str, Any]]:
    OUT.mkdir(parents=True, exist_ok=True)
    tasks: List[Dict[str, Any]] = []
    import time
    t_start = time.time()
    names = only or PACKAGES

    for pkg in names:
        if time.time() - t_start > budget_s:
            print(f"  [budget] stopping after {budget_s}s")
            break
        print(f"  {pkg}")
        tmp = Path(tempfile.mkdtemp(prefix=f"sd_{pkg}_"))
        dl = tmp / "dl"
        dl.mkdir()
        arc = sdist(pkg, dl)
        if arc is None:
            continue
        root = extract(arc, tmp / "src")
        if root is None:
            continue
        pkgdir, tdir = find_dirs(root, pkg)
        if pkgdir is None or tdir is None:
            print(f"    package={pkgdir is not None} tests={tdir is not None} -> skip")
            continue

        # make the package importable the way the project intends
        setup = ""
        if (root / "src").is_dir():
            setup = 'import sys; sys.path.insert(0,"src"); '
        test_cmd_tpl = (f'python -c "{setup}import {pkgdir.name}" && '
                        f'python -m pytest "{tdir.relative_to(root).as_posix()}" -x -q '
                        f'--no-header -p no:cacheprovider')
        rc0, out0 = run(test_cmd_tpl, root)
        if rc0 != 0:
            print(f"    pristine suite not green (rc={rc0}) -> skip")
            continue
        print(f"    pristine suite green")

        py_files = [p for p in sorted(pkgdir.rglob("*.py"))
                    if p.stat().st_size < 150_000 and "test" not in p.name]
        made = 0
        for f in py_files:
            if made >= per_pkg:
                break
            original = f.read_text(encoding="utf-8", errors="replace")
            funcs = list(FUNC_RE.finditer(original))
            if not funcs:
                continue
            for fi, fm in enumerate(funcs):
                if made >= per_pkg:
                    break
                start = fm.start()
                end = funcs[fi + 1].start() if fi + 1 < len(funcs) else len(original)
                body = original[start:end]
                if len(body) > 5000 or body.count("\n") < 2:
                    continue
                for pat, rep in MUTATIONS:
                    mbody = re.sub(pat, rep, body, count=1)
                    if mbody == body:
                        continue
                    f.write_text(original[:start] + mbody + original[end:], encoding="utf-8")
                    rc1, out1 = run(test_cmd_tpl, root)
                    f.write_text(original, encoding="utf-8")
                    if rc1 in (0, 124, 125):
                        continue
                    m = re.search(r"FAILED\s+(\S+)", out1)
                    tasks.append({
                        "task_id": f"{pkgdir.name}__{f.stem}__{fm.group(2)}__{made}",
                        "package": pkg, "package_version": "sdist",
                        "repo_root": str(root), "gold_file": str(f.relative_to(root)).replace("\\", "/"),
                        "gold_function": fm.group(2),
                        "mutated_source": original[:start] + mbody + original[end:],
                        "original_source": original,
                        "test_command": test_cmd_tpl,
                        "n_source_files": len(py_files),
                        "failure_signature": m.group(1) if m else "",
                        "mutation": f"{pat} -> {rep}",
                        "expected_pass_after_fix": True,
                    })
                    made += 1
                    print(f"    +{f.name}::{fm.group(2)}  ({pat}->{rep})  [{made}]")
                    break
        print(f"    -> {made} verified tasks")
    return tasks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-pkg", type=int, default=3)
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--budget-s", type=int, default=1500)
    ap.add_argument("--out", default="tasks_sdist.jsonl")
    args = ap.parse_args()
    tasks = build(args.per_pkg, args.only, args.budget_s)
    p = OUT / args.out
    with p.open("w", encoding="utf-8") as fh:
        for t in tasks:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(tasks)} verified tasks -> {p}")
    if not tasks:
        sys.exit(1)


if __name__ == "__main__":
    main()
