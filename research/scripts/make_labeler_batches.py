"""Generate the round-3 (dense) annotation batch prompts, one per labeler.

Usage: python scripts/make_labeler_batches.py --cards-dir ../datasets/annotations/tb2/cards_dense --batches 18
Prints the prompts to ../datasets/annotations/tb2/batches.json and a shell-friendly listing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")

PROMPT_TEMPLATE = """You are an independent annotator for a research study on coding-agent stagnation. Work strictly by the study's codebook; do not substitute your own definition.

STEP 0 — read the codebook with the read tool:
D:\\Gavania\\Academic\\Competitions\\Agent_Correction\\research\\docs\\annotation_guide.md

STEP 1 — list the cards assigned to you with the glob tool, pattern "{globpat}" in path D:\\Gavania\\Academic\\Competitions\\Agent_Correction\\research, then sort the resulting file names ascending and keep the ones at 1-based ranks {ranks}. That is {count} cards: read EVERY one of them with the read tool before deciding anything. Each card shows the task statement, the window under judgement, and the steps immediately before and after it.

STEP 2 — for each card apply the codebook §4 decision procedure IN ORDER and produce:
- label: PRODUCTIVE | STAGNANT | REGRESSION | DONE_REDUNDANT | BLOCKED_EXTERNAL | UNCERTAIN
- confidence: high | medium | low
- boundary: true | false   (true when the window cuts a productive stretch in half)
- channels: E | I | V | none   (which of epistemic / implementation / verification advanced; combine with / when several)
- detail: only when label is STAGNANT, one of repeat_search | repeat_read | repeat_verify | edit_revert | irrelevant_exploration | no_new_information | post_completion | no_tool_text_loop | other
- reason: at most 25 words citing the specific step numbers you relied on

RULES
- Judge only what the card shows. Never speculate about the hidden reference solution, hidden tests, or the grading.
- Ignore the printed final reward when labelling: a run can be productive and still fail.
- Repetition of a command is NOT stagnation by itself. Check whether the observations carried information that was NOT already known, whether a change plausibly survived, and whether the verification state moved.
- A run of steps with no tool call whose message repeats what the agent already knew is STAGNANT with detail no_tool_text_loop.
- If a window is genuinely ambiguous, say UNCERTAIN rather than guessing.

STEP 3 — write your results with the write tool to
D:\\Gavania\\Academic\\Competitions\\Agent_Correction\\research\\data\\annotations\\tb2\\{outfile}
as valid CSV with exactly this header line:
card_id,label,confidence,boundary,channels,detail,reason
Use one row per assigned card, no markdown fences, no extra prose. Quote any field containing a comma. Do not use commas inside the reason field: use semicolons instead.

Reply with only: the number of cards labelled and the count of each label."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards-dir", default="../datasets/annotations/tb2/cards_dense")
    ap.add_argument("--root", default=r"D:\Gavania\Academic\Competitions\Agent_Correction\research")
    ap.add_argument("--batches", type=int, default=18)
    ap.add_argument("--out", default="../datasets/annotations/tb2/batches.json")
    args = ap.parse_args()

    full = os.path.join(args.root, args.cards_dir.replace("/", os.sep))
    names = sorted(f for f in os.listdir(full) if f.endswith(".md"))
    n = len(names)
    k = args.batches
    batches = []
    for b in range(k):
        ranks = list(range(b + 1, n + 1, k))
        batches.append({
            "batch": b + 1,
            "n": len(ranks),
            "outfile": f"labels_dense_{b+1:02d}.csv",
            "ranks": f"{b+1}, {b+1+k}, {b+1+2*k}, ... (every {k}th file, {len(ranks)} cards)",
            "prompt": PROMPT_TEMPLATE.format(
                globpat=f"{args.cards_dir}/*.md", ranks=f"{b+1}, {b+1+k}, {b+1+2*k}, ...",
                count=len(ranks), outfile=f"labels_dense_{b+1:02d}.csv"),
        })
    with open(os.path.join(args.root, args.out.replace("/", os.sep)), "w", encoding="utf-8") as fh:
        json.dump({"n_cards": n, "n_batches": k, "batches": batches}, fh, indent=2)
    print(f"{n} cards split into {k} batches of ~{n//k}")
    for b in batches[:3]:
        print(f"  {b['outfile']}: {b['n']} cards")


if __name__ == "__main__":
    main()
