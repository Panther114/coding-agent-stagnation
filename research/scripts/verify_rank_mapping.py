"""Validate that the rank-based label assignments were resolved the way we intended.

The labelers were given rank ranges over an alphabetically sorted list of card file names.
Plain string sort orders ``..._101`` before ``..._11``, while a natural sort orders it after.
If a labeler resolved ranks with a different sort order, the card they read is not the card
they wrote a row for.  This script quantifies the exposure and tests it:

* how many rank positions differ between plain and natural sort;
* for cards labelled by more than one reader, agreement split by whether the two readers came
  from the same "resolution regime" (both would have read the same file) or not.

Usage: python scripts/verify_rank_mapping.py --corpus tb2
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import re
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import paths  # noqa: E402

NUM = re.compile(r"(\d+)")


def natural_key(s: str):
    return [int(t) if t.isdigit() else t for t in NUM.split(s)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    args = ap.parse_args()
    d = os.path.join(paths.DATA, "annotations", args.corpus)
    cards_dir = os.path.join(d, "cards_dense")
    files = [f for f in os.listdir(cards_dir) if f.endswith(".md")]
    plain = sorted(files)
    natural = sorted(files, key=natural_key)
    same = sum(1 for a, b in zip(plain, natural) if a == b)
    print(f"cards={len(files)} positions identical under plain vs natural sort: {same} "
          f"({100*same/len(files):.1f}%)")
    diff_pos = [i for i, (a, b) in enumerate(zip(plain, natural)) if a != b]
    print(f"differing rank positions: {len(diff_pos)}; first few: "
          f"{[(i+1, plain[i], natural[i]) for i in diff_pos[:5]]}")

    # which trajectories are affected by the ambiguity
    def traj(name: str) -> str:
        return name[:-3].replace("d_", "", 1).rsplit("_", 1)[0]
    affected_traj = {traj(plain[i]) for i in diff_pos} | {traj(natural[i]) for i in diff_pos}
    print(f"trajectories touched by the ambiguity: {len(affected_traj)}")

    # agreement among multi-read cards, using the two candidate readings of each labeler's file
    def load(fname: str) -> Dict[str, str]:
        p = os.path.join(d, fname)
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if not rows:
            return {}
        lc = next((k for k in rows[0] if k and k.startswith("label")), None)
        return {r["card_id"]: (r[lc] or "").strip().upper() for r in rows if r.get("card_id")}

    by_card: Dict[str, List[Tuple[str, str]]] = collections.defaultdict(list)
    for f in sorted(os.listdir(d)):
        if not f.endswith(".csv") or not f.startswith("labels_"):
            continue
        for cid, lab in load(f).items():
            if lab:
                by_card[cid].append((f, lab))
    multi = {c: v for c, v in by_card.items() if len({f for f, _ in v}) > 1}
    POS = {"STAGNANT", "DONE_REDUNDANT"}

    def b(l):
        return 1 if l in POS else (0 if l in {"PRODUCTIVE", "REGRESSION"} else None)
    agree_same, agree_diff = [], []
    for cid, v in multi.items():
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                bi, bj = b(v[i][1]), b(v[j][1])
                if bi is None or bj is None:
                    continue
                same_regime = (v[i][0].startswith("labels_dense") and v[j][0].startswith("labels_dense")) or \
                              (v[i][0].startswith("labels_refine") and v[j][0].startswith("labels_refine"))
                (agree_same if same_regime else agree_diff).append(int(bi == bj))
    print(f"\nmulti-read cards: {len(multi)}")
    if agree_same:
        print(f"  same-regime pairs: n={len(agree_same)} agreement={sum(agree_same)/len(agree_same):.3f}")
    if agree_diff:
        print(f"  cross-regime pairs: n={len(agree_diff)} agreement={sum(agree_diff)/len(agree_diff):.3f}")
    print("\ninterpretation: if cross-regime agreement is comparable to same-regime agreement, "
          "the rank ambiguity did not corrupt the labels in a detectable way.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
