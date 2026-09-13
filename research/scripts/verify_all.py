"""One command that proves the paper and its figures are in the state they claim to be in.

Runs, in order:

  1. selftest_figure_audit.py   -- proves the audit's pixel mapping and collision test are correct,
                                   on a synthetic figure with a known collision and a known clean pair
  2. audit_figure_text.py       -- measures every text box of every figure the paper includes and
                                   fails on text-on-text overlap, text printed over another panel,
                                   glyphs cut at the raster border, and sub-5pt printed labels
  3. check_figures.py           -- content check: every plotted series has real points, no monitor is
                                   silently dropped, families have distinct hues
  4. audit_numbers.py           -- re-derives the paper's headline values from the frozen run and
                                   compares them with the macros the paper prints
  5. run_tests.py               -- the protocol invariants (online restriction, gold-file consistency)
  6. verify_paper_pdf.py        -- the compiled PDF still prints those values and is the expected length
  7. check_macro_coverage.py    -- reports which exported values the shortened paper no longer prints

Usage: python scripts/verify_all.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAPER = os.path.normpath(os.path.join(ROOT, "..", "paper"))

STEPS = [
    ("figure-audit self-test", ["selftest_figure_audit.py"]),
    ("figure geometry/content", ["check_figures.py", "--run", "results/final/tb2_v5"]),
    ("figure text audit", ["audit_figure_text.py", "--json", "results/final/fig_audit.json"]),
    ("figure edge/clipping", ["check_figure_edges.py"]),
    ("number audit", ["audit_numbers.py"]),
    ("protocol tests", ["run_tests.py"]),
    ("compiled-PDF check", ["verify_paper_pdf.py"]),
    ("macro coverage", ["check_macro_coverage.py"]),
]


def main() -> None:
    results = []
    for label, argv in STEPS:
        print("\n" + "=" * 100)
        print(f"### {label}:  python {' '.join(argv)}")
        print("=" * 100, flush=True)
        p = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, argv[0]), *argv[1:]],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        tail = out.strip().splitlines()
        # keep the interesting tail; the audits print their summary last
        show = tail if len(tail) <= 40 else tail[:20] + ["   ..."] + tail[-18:]
        print("\n".join(show))
        failed = p.returncode != 0
        # check_macro_coverage is informational: a shorter paper prints fewer values by design
        informational = argv[0] == "check_macro_coverage.py"
        results.append((label, p.returncode, informational))

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    for label, code, informational in results:
        state = "ok" if code == 0 else ("info (non-blocking)" if informational else "FAILED")
        print(f"  {label:28} {state}")

    pages = None
    log = os.path.join(PAPER, "main.log")
    if os.path.exists(log):
        m = re.search(r"Output written on main\.pdf \((\d+) pages", open(log, encoding="utf-8",
                                                                       errors="replace").read())
        pages = m.group(1) if m else None
    print(f"\n  paper length: {pages} pages (target ~20)")
    hard = [label for label, code, informational in results if code != 0 and not informational]
    print("  RESULT:", "ALL CHECKS PASSED" if not hard else f"FAILURES: {hard}")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
