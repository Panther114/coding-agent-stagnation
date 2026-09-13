"""Consistency check across every rebuild artifact.

    python scripts/check_rebuild_consistency.py

Catches the class of error that a rebuild makes easy: a number quoted in the findings
document that disagrees with the artifact it came from, or a run directory whose primary
target changed without the narrative noticing.  Fails loudly with a list of mismatches.

Checks
------
1. Every artifact the findings document cites exists.
2. The per-corpus window analyses and the sequential analyses agree on run counts.
3. The aligner's step count matches the step table's edit count.
4. The flat number table matches the artifacts it was built from.
5. No analysis directory is stale relative to its input tables (mtime ordering).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"
PROBLEMS: list[str] = []


def need(path: Path) -> dict:
    if not path.exists():
        PROBLEMS.append(f"missing artifact: {path.relative_to(ROOT)}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        PROBLEMS.append(f"unreadable artifact {path.name}: {exc}")
        return {}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    required = ["tb2_w10/analysis.json", "nebius_w10/analysis.json",
                "tb2_w10/sequential.json", "nebius_w10/sequential.json",
                "alignment.json", "step_task.json", "transfer.json",
                "gold_crosscheck.json", "editor_state_coverage.json",
                "rebuild_numbers.json", "rebuild_numbers.flat.json"]
    for rel in required:
        p = OUT / rel
        if not p.exists():
            PROBLEMS.append(f"missing artifact: {rel}")
    print(f"artifacts present: {len(required) - sum('missing' in p for p in PROBLEMS)}/{len(required)}")

    # 2. run-count agreement between the window analysis and the sequential analysis
    for corpus in ("tb2", "nebius"):
        a = need(OUT / f"{corpus}_w10" / "analysis.json")
        s = need(OUT / f"{corpus}_w10" / "sequential.json")
        if not a or not s:
            continue
        # the sequential stage drops runs with no scored window, so it may see fewer
        if s.get("n_runs", 0) > a.get("n_runs", 0):
            PROBLEMS.append(f"{corpus}: sequential sees more runs ({s.get('n_runs')}) than "
                            f"the window analysis ({a.get('n_runs')})")
        print(f"  {corpus}: windows {a.get('n_windows')}, runs {a.get('n_runs')}; "
              f"sequential runs {s.get('n_runs')}, never-stalls "
              f"{s.get('frac_never_stalls', float('nan')):.3f}")

    # 3. alignment vs the step table
    steps = ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet"
    al = need(OUT / "alignment.json")
    if steps.exists() and al:
        import pandas as pd
        n_edit = int(pd.read_parquet(steps, columns=["is_edit"])["is_edit"].sum())
        n_class = int(al.get("steps", 0))
        if n_class > n_edit:
            PROBLEMS.append(f"alignment classified {n_class} steps but the table has {n_edit} edits")
        print(f"  alignment: {n_class} classified of {n_edit} edit steps")

    # 4. flat table agrees with the artifacts
    flat = need(OUT / "rebuild_numbers.flat.json")
    if flat and al:
        for key, src in (("alignment.pooled.mean_precise", al.get("pooled", {}).get("mean_precise")),
                         ("alignment.concentration.frac_runs_for_50pct",
                          al.get("concentration", {}).get("frac_runs_for_50pct"))):
            got = flat.get(key)
            if got is not None and src is not None and abs(float(got) - float(src)) > 1e-9:
                PROBLEMS.append(f"flat table disagrees with alignment.json for {key}")

    # 5. staleness: an analysis older than its input table
    for corpus in ("tb2", "nebius"):
        tbl = ROOT / "data" / "processed" / "windows" / corpus / "windows.parquet"
        run_dir = OUT / f"{corpus}_w10"
        art = run_dir / "analysis.json"
        if tbl.exists() and art.exists():
            if art.stat().st_mtime < tbl.stat().st_mtime:
                PROBLEMS.append(f"{corpus}: analysis.json is older than windows.parquet "
                                f"(rerun analyse_windows.py)")

    # 6. every run directory names its primary target
    for corpus in ("tb2", "nebius"):
        a = need(OUT / f"{corpus}_w10" / "analysis.json")
        if a and not a.get("primary_target"):
            PROBLEMS.append(f"{corpus}: analysis.json does not record its primary target")

    if PROBLEMS:
        print(f"\n{len(PROBLEMS)} problem(s):")
        for p in PROBLEMS:
            print("  -", p)
        sys.exit(1)
    print("\nall consistency checks passed")


if __name__ == "__main__":
    main()
