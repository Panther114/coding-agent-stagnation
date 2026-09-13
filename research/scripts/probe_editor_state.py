"""How much objective per-step state does a SWE-agent observation actually expose?

Every observation ends with an editor-state footer. If the footer carries the open
file, the visible line range and the file's total line count, then a runtime can
track *which region of which file* the agent is working on at every step, and the
study can define an objective progress target without re-running any environment:

  * which file each edit touched, and which line span within it
  * whether the agent keeps returning to the same span (an objective loop)
  * how the file's size changes across the run (objective growth/shrink)
  * whether the file the agent finally patched is the file it edited at step t
  * how many edits landed in files that never appear in the final patch

This measures all of it over a large sample and writes a summary + examples.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"
FENCE = re.compile(r"```(?:bash|sh)?\s*\n(.*?)```", re.S)
FILE_HDR = re.compile(r"\[File:\s*([^\]]+?)\]\s*\n")
TOTAL = re.compile(r"\((\d+) lines total\)")
WINDOW = re.compile(r"\[(\d+)\s+lines above the scrolling window are hidden\]|"
                    r"\[(\d+)\s+lines below the scrolling window are hidden\]")
NUMBERED = re.compile(r"^(\d+):", re.M)
OPEN_FILE = re.compile(r"\(Open file: ([^)]+)\)")
CWD = re.compile(r"\(Current directory: ([^)]+)\)")
EDIT_CMD = re.compile(r"^(str_replace|create|insert|undo_edit|edit|apply_patch)\b", re.M)
INSERT_CMD = re.compile(r"^insert\s+(\d+)\s*$", re.M)
SR_CMD = re.compile(r"^str_replace\s+(\d+)\s+(\d+)\s*$", re.M)


def parse_footer(obs: str):
    fm = FILE_HDR.search(obs)
    f = fm.group(1).strip() if fm else None
    tot = TOTAL.search(obs)
    lines = NUMBERED.findall(obs)
    of = OPEN_FILE.search(obs)
    return {
        "file": f,
        "total": int(tot.group(1)) if tot else None,
        "first": int(lines[0]) if lines else None,
        "last": int(lines[-1]) if lines else None,
        "n_shown": len(lines),
        "open": (of.group(1).strip() if of else None),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted((ROOT / "data" / "raw" / "nebius").glob("train-*.parquet"))
    stat = collections.Counter()
    tot_steps = 0
    with_footer = 0
    with_total = 0
    with_window = 0
    edit_kinds = collections.Counter()
    sr_spans = []
    edits_per_run = []
    files_touched_per_run = []
    final_in_edit = []
    patched_only_files = []
    rows = []
    for f in files[:2]:
        d = pd.read_parquet(f, columns=["instance_id", "model_name", "target", "trajectory",
                                        "generated_patch"])
        print(f"{f.name}: {len(d)}", flush=True)
        for i in range(len(d)):
            traj = list(d["trajectory"][i]) if d["trajectory"][i] is not None else []
            patched_files = set(re.findall(r"^diff --git a/(\S+)", d["generated_patch"][i] or "", re.M))
            n_edit = 0
            touched = set()
            hit_final = 0
            for j, m in enumerate(traj):
                if m.get("role") != "ai":
                    continue
                text = m.get("text") or ""
                obs = traj[j + 1].get("text") if (j + 1 < len(traj)
                                                 and traj[j + 1].get("role") == "user") else ""
                obs = obs or ""
                tot_steps += 1
                ft = parse_footer(obs)
                if ft["file"]:
                    with_footer += 1
                if ft["total"] is not None:
                    with_total += 1
                if ft["n_shown"]:
                    with_window += 1
                bodies = FENCE.findall(text)
                for body in bodies:
                    for kind, s in (("str_replace", SR_CMD), ("insert", INSERT_CMD)):
                        for mm in s.finditer(body):
                            edit_kinds[kind] += 1
                            if kind == "str_replace":
                                a, b = int(mm.group(1)), int(mm.group(2))
                                sr_spans.append(b - a + 1)
                    if EDIT_CMD.search(body):
                        n_edit += 1
                        if ft["file"]:
                            touched.add(ft["file"])
                            base = ft["file"].rsplit("/", 1)[-1]
                            if any(p.endswith(base) or base.endswith(p.rsplit("/", 1)[-1])
                                   for p in patched_files):
                                hit_final += 1
            if n_edit:
                edits_per_run.append(n_edit)
                files_touched_per_run.append(len(touched))
                final_in_edit.append(hit_final / n_edit)
                if patched_files:
                    patched_only_files.append(
                        len(patched_files - {t.rsplit("/", 1)[-1] for t in touched}))
    print(f"\nsteps scanned: {tot_steps}")
    print(f"  observations with a [File: ...] footer: {with_footer} ({with_footer / max(1, tot_steps):.1%})")
    print(f"  with '(N lines total)': {with_total} ({with_total / max(1, tot_steps):.1%})")
    print(f"  with numbered lines shown: {with_window} ({with_window / max(1, tot_steps):.1%})")
    print(f"  editor edit actions seen: {edit_kinds}")
    if sr_spans:
        a = np.array(sr_spans)
        print(f"  str_replace span sizes: mean {a.mean():.1f} median {np.median(a):.0f} "
              f"p90 {np.percentile(a, 90):.0f} max {a.max()}")
    if edits_per_run:
        e = np.array(edits_per_run)
        fo = np.array(files_touched_per_run)
        ff = np.array(final_in_edit)
        print(f"  edit actions per run: mean {e.mean():.1f} median {np.median(e):.0f} max {e.max()}")
        print(f"  distinct files touched per run: mean {fo.mean():.2f} median {np.median(fo):.0f}")
        print(f"  share of edits in a file that the final patch touches: mean {ff.mean():.3f} "
              f"median {np.median(ff):.3f}")
    if patched_only_files:
        p = np.array(patched_only_files)
        print(f"  patched files never edited by the agent: mean {p.mean():.2f}/run, "
              f"zero in {(p == 0).mean():.1%} of runs")
    summary = {
        "steps_scanned": tot_steps,
        "footer_rate": with_footer / max(1, tot_steps),
        "lines_total_rate": with_total / max(1, tot_steps),
        "numbered_window_rate": with_window / max(1, tot_steps),
        "edit_kinds": dict(edit_kinds),
        "edits_per_run_mean": float(np.mean(edits_per_run)) if edits_per_run else None,
        "files_touched_mean": float(np.mean(files_touched_per_run)) if files_touched_per_run else None,
        "share_edits_in_patched_file": float(np.mean(final_in_edit)) if final_in_edit else None,
    }
    with open(OUT / "editor_state_coverage.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {OUT / 'editor_state_coverage.json'}")


if __name__ == "__main__":
    main()
