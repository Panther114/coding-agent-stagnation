"""Build batch prompts for labelling the stride-2 refinement cards.

Usage: python scripts/make_refine_batches.py --batches 32 --per-batch 30
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\Gavania\Academic\Competitions\Agent_Correction\research"

PROMPT = """You are an independent annotator for a research study on coding-agent stagnation. Work strictly by the study's codebook; do not substitute your own definition.

STEP 0 — read the codebook with the read tool:
{root}\\docs\\annotation_guide.md

STEP 1 — list your assigned cards with the glob tool, pattern "data/annotations/tb2/cards_dense/*.md" in path {root}, sort the file names ascending, and keep the cards at these 1-based ranks: {ranks}. Read EVERY one of them with the read tool (one read call per file) before deciding anything. Each card shows the task statement, the window under judgement (steps lo-hi), and the steps immediately before and after it.

STEP 2 — apply the codebook §4 decision procedure IN ORDER to each card and produce:
- label: PRODUCTIVE | STAGNANT | REGRESSION | DONE_REDUNDANT | BLOCKED_EXTERNAL | UNCERTAIN
- confidence: high | medium | low
- boundary: true | false (true when the window cuts a productive stretch in half)
- channels: E | I | V | none (which advanced; combine with / when several)
- detail: only when STAGNANT: repeat_search | repeat_read | repeat_verify | edit_revert | irrelevant_exploration | no_new_information | post_completion | no_tool_text_loop | other
- reason: at most 20 words citing step numbers; use semicolons instead of commas

RULES
- Judge only what the card shows; never speculate about the hidden reference solution or the grading.
- Ignore the printed final reward when labelling.
- Repetition alone is NOT stagnation: check whether the observations carried information that was not already known, whether a change plausibly survived, and whether the verification state moved.
- Steps with no tool call whose message repeats what the agent already knew: STAGNANT with detail no_tool_text_loop.
- Say UNCERTAIN rather than guessing.

STEP 3 — write the results with the write tool to
{root}\\data\\annotations\\tb2\\{outfile}
as valid CSV with exactly this header:
card_id,label,confidence,boundary,channels,detail,reason
One row per assigned card; no markdown fences; no extra prose; quote any field containing a comma.

Reply with only: the number of cards labelled and the counts per label."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=32)
    ap.add_argument("--per-batch", type=int, default=30)
    ap.add_argument("--prefix", default="labels_refine_")
    ap.add_argument("--out", default="data/annotations/tb2/refine_batches.json")
    args = ap.parse_args()
    n = 952
    batches = []
    start = 1
    b = 0
    while start <= n:
        b += 1
        end = min(n, start + args.per_batch - 1)
        ranks = list(range(start, end + 1))
        ranks_s = f"{ranks[0]}-{ranks[-1]} (i.e. ranks {ranks[0]}, {ranks[0]+1}, ..., {ranks[-1]})"
        outfile = f"{args.prefix}{b:02d}.csv"
        batches.append({"batch": b, "n": len(ranks), "outfile": outfile, "ranks": ranks,
                        "prompt": PROMPT.format(root=ROOT, ranks=ranks_s, outfile=outfile)})
        start = end + 1
    with open(os.path.join(ROOT, args.out.replace("/", os.sep)), "w", encoding="utf-8") as fh:
        json.dump({"n_cards": n, "n_batches": len(batches), "batches": batches}, fh, indent=2)
    print(f"{n} cards -> {len(batches)} batches")
    for x in batches[:3]:
        print(x["batch"], x["n"], x["outfile"], x["ranks"][:4])


if __name__ == "__main__":
    main()
