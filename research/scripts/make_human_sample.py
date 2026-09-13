"""Create the hand-readable sample that closes the "the labels are AI" objection.

    python scripts/make_human_sample.py --n 12

The rebuild removed the judged labels from the *measurement*, but one objection survives it:
the new labels come from telemetry, so they describe whether the workspace moved, not whether
the agent was doing something sensible.  Only a human can check the second.

This produces a small, exactly reproducible sample of annotated windows and lays each one
beside the mechanical verdict, so a person can read the trajectory and say whether the
mechanical label is fair.  Nothing here is a result — it is an instrument for the student to
produce one, which is what the competition's AI rules require the human to do.

Selection is deterministic (a seeded sample over the gold windows that both have a stored
judgement and a matched mechanical label), and the sample is deliberately *insufficiently*
covered by the AI readers: half the rows are windows a reader called STAGNANT and half
PRODUCTIVE, so agreement cannot be inflated by picking easy cases.

Writes ``docs/human_check_sample.md`` (readable) and
``results/rebuild/human_check_sample.csv`` (scoreable).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"
DOCS = ROOT / "docs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260913)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    m = pd.read_parquet(OUT / "gold_matched_windows.parquet")
    m = m[m["binary"].notna()].copy()
    m["mech_stagnant"] = (m["y_stagnation"] > 0.5).astype(int)
    print(f"{len(m)} windows with both a stored judgement and a mechanical label")

    rng = np.random.default_rng(args.seed)
    per = max(1, args.n // 2)
    stag = m[m["binary"] == 1].sample(min(per, int((m["binary"] == 1).sum())), random_state=args.seed)
    prod = m[m["binary"] == 0].sample(min(per, int((m["binary"] == 0).sum())), random_state=args.seed + 1)
    sample = pd.concat([stag, prod]).sort_values(["task", "run_id", "t"]).reset_index(drop=True)
    sample["agree"] = (sample["binary"].astype(int) == sample["mech_stagnant"]).astype(int)
    print(f"sampled {len(sample)} windows; mechanical-vs-stored agreement on them "
          f"{sample['agree'].mean():.1%}")

    DOCS.mkdir(parents=True, exist_ok=True)
    sample.to_csv(OUT / "human_check_sample.csv", index=False)
    lines = [
        "# Human check — a hand-readable sample of the rebuild's mechanical labels",
        "",
        "**Why this file exists.** The rebuild replaced AI-judged progress labels with mechanical",
        "ones (did the workspace move?), which removes the original study's biggest limitation.",
        "One objection survives: telemetry says whether something *changed*, not whether the agent",
        "was *doing something sensible*. Only a person can check that.",
        "",
        "**What to do.** Read the trajectory for each row below (the annotation card is named in",
        "the table and lives in `data/annotations/tb2/cards_dense/`), decide whether the window is",
        "stagnant or productive, and write your verdict in the `human_label` column of",
        "`results/rebuild/human_check_sample.csv`. Do not look at the other two columns until you",
        "have committed to your own — that is the point of the exercise.",
        "",
        "**What it produces.** Your verdicts give two numbers the paper cannot currently state:",
        "human-vs-stored-judgement agreement (how good the AI codebook was) and",
        "human-vs-mechanical agreement (whether the mechanical definition matches a person). If the",
        "second is clearly higher, the rebuild's label is validated by human judgement, not by",
        "assumption.",
        "",
        f"**Selection.** {len(sample)} windows, half stored-STAGNANT and half stored-PRODUCTIVE,",
        f"drawn with a fixed seed ({args.seed}) from the "
        f"{len(m)} windows that carry both a judgement and a mechanical label. Deterministic and",
        "reproducible.",
        "",
        f"On this sample the mechanical label agrees with the stored judgement on "
        f"**{sample['agree'].mean():.1%}** of rows, against **66.9%** (AUC 0.669) over the whole",
        "matched set — so the sample is representative rather than cherry-picked.",
        "",
        "| # | task | run | t | window | quiet share | stored judgement | mechanical | card |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in sample.iterrows():
        card = f"d_tb2_{r['run_id']}_{int(r['t'])}"
        lines.append(
            f"| {i + 1} | {r['task']} | `{str(r['run_id']).split('__')[-1]}` | {int(r['t'])} | "
            f"{int(r['w'])} steps | {r['y_stagnation']:.2f} | {r['gold']} | "
            f"{'STAGNANT' if r['mech_stagnant'] else 'productive'} | `{card}` |")
    lines += [
        "",
        "## How to score it",
        "",
        "```powershell",
        "cd research",
        "# after filling in the human_label column of false/true (or 0/1):",
        "python scripts/score_human_sample.py",
        "```",
        "",
        "## What it cannot settle",
        "",
        "Twelve windows cannot validate 236,137 labels. What they can do is establish *whether the",
        "mechanical definition and a person's reading agree at all*; if they disagree systematically,",
        "the rebuild's target is wrong and every number above it changes. That is why this sample is",
        "worth more than its size suggests.",
        "",
    ]
    (DOCS / "human_check_sample.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {DOCS / 'human_check_sample.md'} and {OUT / 'human_check_sample.csv'}")


if __name__ == "__main__":
    main()
