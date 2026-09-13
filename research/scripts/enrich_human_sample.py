"""Make the human check readable without opening anything else.

    python scripts/enrich_human_sample.py

`docs/human_check_sample.md` lists twelve windows with a card path, which means a reader has to
find and open twelve files. This puts the actual trajectory text in the document instead — the
agent messages, the tool calls and the observations for each window — so a person can read the
evidence and commit to a verdict in one pass.

Each window is trimmed to its own step span and each step to a readable excerpt. The mechanical
verdict is deliberately placed *after* the transcript and under a heading that says not to look
until the reader has decided, because the point of the exercise is an independent reading.

Writes ``docs/human_check_readable.md``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"
DOCS = ROOT / "docs"


def step_excerpts(traj, lo_step: int, hi_step: int, per_step: int = 220,
                  max_steps: int = 12) -> List[str]:
    """Readable excerpts for one window, from the raw trajectory records."""
    out: List[str] = []
    shown = 0
    idx = -1
    for m in traj:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "ai":
            idx += 1
            if idx < lo_step or idx > hi_step:
                continue
            if shown >= max_steps:
                break
            shown += 1
            text = (m.get("text") or "").strip().replace("\r", "")
            cmds = re.findall(r"```(?:bash|sh)?\s*\n(.*?)```", text, re.S)
            body = cmds[0].strip() if cmds else ""
            prose = text.split("```")[0].strip()
            out.append(f"**[step {idx}] agent** — {prose[:per_step]}")
            if body:
                out.append(f"```\n{body[:per_step]}\n```")
        elif role == "user" and idx >= lo_step and idx <= hi_step and shown:
            obs = (m.get("text") or "").strip().replace("\r", "")
            if obs:
                out.append(f"> obs: {obs[:per_step]}")
    return out


def tb2_steps_excerpts(traj_raw, lo_step: int, hi_step: int, per_step: int = 200,
                       max_steps: int = 12) -> List[str]:
    """Readable excerpts for one Terminal-Bench window, from the raw `steps` JSON."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "src"))
    from agentstall.corpus import build_tb2_steps
    steps = build_tb2_steps(traj_raw)
    out: List[str] = []
    shown = 0
    for s in steps:
        if s.index < lo_step or s.index > hi_step:
            continue
        if shown >= max_steps:
            break
        shown += 1
        prose = (s.text or "").split("```")[0].strip()
        out.append(f"**[step {s.index}] agent** — {prose[:per_step]}")
        if s.cmds:
            out.append(f"```\n{s.cmds[0].strip()[:per_step]}\n```")
        if s.obs:
            out.append(f"> obs: {s.obs.strip()[:per_step]}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-step", type=int, default=200)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    csv = OUT / "human_check_sample.csv"
    if not csv.exists():
        print(f"{csv} missing; run scripts/make_human_sample.py first")
        return
    sample = pd.read_csv(csv)
    print(f"{len(sample)} windows to enrich; corpora: "
          f"{sample['corpus'].value_counts().to_dict()}")

    # index the raw corpus by run identity.  Terminal-Bench keys on trial_name and carries its
    # steps as a JSON string; the SWE-agent corpus keys on instance::model.
    want_tb2 = set(sample.loc[sample["corpus"] == "tb2", "run_id"])
    want_neb = {str(r) for r in sample.loc[sample["corpus"] != "tb2", "run_id"]}
    tb2_raw: Dict[str, str] = {}
    neb_traj: Dict[str, list] = {}
    import pyarrow.parquet as pq
    if want_tb2:
        for f in sorted((ROOT / "data" / "raw" / "tb2").glob("*.parquet")):
            for batch in pq.ParquetFile(f).iter_batches(batch_size=200):
                d = batch.to_pydict()
                for i in range(len(d["trial_name"])):
                    tn = d["trial_name"][i]
                    if tn in want_tb2 and tn not in tb2_raw:
                        tb2_raw[tn] = d["steps"][i]
            if len(tb2_raw) == len(want_tb2):
                break
    if want_neb:
        want_pairs = {(r.split("::")[0], r.split("::")[1]) for r in want_neb if "::" in r}
        for f in sorted((ROOT / "data" / "raw" / "nebius").glob("*.parquet")):
            for batch in pq.ParquetFile(f).iter_batches(batch_size=60):
                for row in batch.to_pylist():
                    key = (row["instance_id"], row["model_name"])
                    if key in want_pairs and row["trajectory"] is not None:
                        neb_traj[f"{key[0]}::{key[1]}"] = list(row["trajectory"])
    print(f"fetched {len(tb2_raw)}/{len(want_tb2)} tb2 and {len(neb_traj)}/{len(want_neb)} nebius")

    lines: List[str] = [
        "# Human check — the twelve windows, with their trajectories inline",
        "",
        "Read each window's transcript and decide **before** scrolling to the verdict beneath it.",
        "The exercise only produces a result if your reading is independent of the two labels.",
        "",
        "Generated by `scripts/enrich_human_sample.py`; the sample itself is fixed by seed in",
        "`scripts/make_human_sample.py`, so this document is reproducible.",
        "",
        "---",
        "",
    ]
    empty = 0
    for i, r in enumerate(sample.itertuples(), start=1):
        rid = str(r.run_id)
        t = int(r.t)
        w = int(r.w)
        lines += [
            f"## Window {i} — `{r.task}` step {t} (a {w}-step window)",
            "",
            f"*scaffold {r.agent}, model {r.model}, run solved the task: {bool(r.reward)}*",
            "",
            "### Transcript",
            "",
        ]
        ex: List[str] = []
        if r.corpus == "tb2":
            raw = tb2_raw.get(rid)
            if raw is not None:
                ex = tb2_steps_excerpts(raw, max(0, t - w + 1), t, per_step=args.per_step)
        else:
            traj = neb_traj.get(rid)
            if traj is not None:
                ex = step_excerpts(traj, max(0, t - w + 1), t, per_step=args.per_step)
        if not ex:
            empty += 1
            lines += ["*no agent actions recovered inside this window*", ""]
        else:
            lines += ex + [""]
        lines += [
            "### Labels — look only after committing to your own verdict",
            "",
            "| source | verdict |",
            "|---|---|",
            f"| a codebook-reading annotator | **{r.gold}** |",
            f"| this study's mechanical target | "
            f"**{'STAGNANT (quiet)' if r.mech_stagnant else 'productive (workspace moved)'}** "
            f"(quiet share {r.y_stagnation:.2f}) |",
            "",
            "Your verdict: ____________________",
            "",
            "---",
            "",
        ]
    lines += [
        "## Scoring",
        "",
        "Fill the `human_label` column in `results/rebuild/human_check_sample.csv` (`stagnant` or",
        "`productive`), then:",
        "",
        "```powershell",
        "cd research",
        "python scripts/score_human_sample.py",
        "```",
        "",
        "That reports your agreement with each label separately, plus Cohen's kappa against both.",
        "",
    ]
    (DOCS / "human_check_readable.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {DOCS / 'human_check_readable.md'}"
          + (f" (with {empty} windows lacking a found trajectory)" if empty else ""))


if __name__ == "__main__":
    main()
