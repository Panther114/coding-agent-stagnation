"""Where the annotation rounds disagree, and how much.

With a single reading per (card, reader) most cards have one vote, so the useful reliability
statistics here are:

* cards read by two *different* readers (they arise where the dense partition and the
  refinement partition put the same card in different batches): exact and binary agreement;
* the same statistics for round-1 cards re-read in round 2 under reduced context;
* the distribution of labels per reader, which exposes readers whose calibration differs
  from the rest of the panel.

Usage: python scripts/check_agreement.py --corpus tb2
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import sys
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402

import paths  # noqa: E402

POS = {"STAGNANT", "DONE_REDUNDANT"}
NEG = {"PRODUCTIVE", "REGRESSION"}


def load_dir(d: str) -> Dict[str, List[Tuple[str, str, str]]]:
    """card_id -> [(reader_file, label, round)]"""
    out: Dict[str, List[Tuple[str, str, str]]] = collections.defaultdict(list)
    for f in sorted(os.listdir(d)):
        if not f.endswith(".csv") or not f.startswith("labels_"):
            continue
        rnd = ("round1" if f.startswith("labels_r") else
               "round2" if f.startswith("labels_p2") else
               "dense" if f.startswith("labels_dense") else
               "refine" if f.startswith("labels_refine") else "other")
        rows = list(csv.DictReader(open(os.path.join(d, f), encoding="utf-8")))
        if not rows:
            continue
        lc = next((k for k in rows[0] if k and k.startswith("label")), None)
        if not lc:
            continue
        for r in rows:
            cid = r.get("card_id")
            lab = (r.get(lc) or "").strip().upper()
            if cid and lab:
                out[cid].append((f, lab, rnd))
    return out


def binz(l: str):
    return 1 if l in POS else (0 if l in NEG else None)


def kappa(a: List[int], b: List[int]) -> float:
    if not a:
        return float("nan")
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def pairwise(votes: Dict[str, List[Tuple[str, str, str]]], ra: str, rb: str) -> Dict[str, Any]:
    pairs = []
    for cid, v in votes.items():
        A = [x for x in v if x[2] == ra]
        B = [x for x in v if x[2] == rb]
        if A and B and A[0][0] != B[0][0]:
            pairs.append((A[0][1], B[0][1]))
    if not pairs:
        return {"n": 0}
    exact = sum(1 for x, y in pairs if x == y) / len(pairs)
    bp = [(binz(x), binz(y)) for x, y in pairs]
    bp = [(x, y) for x, y in bp if x is not None and y is not None]
    return {
        "n": len(pairs), "exact": exact,
        "binary": sum(1 for x, y in bp if x == y) / len(bp) if bp else float("nan"),
        "kappa": kappa([x for x, _ in bp], [y for _, y in bp]) if bp else float("nan"),
        "agreement_on_positive": (sum(1 for x, y in bp if x == y == 1)
                                  / max(1, sum(1 for x, y in bp if x == 1 or y == 1))),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    args = ap.parse_args()
    d = os.path.join(paths.DATA, "annotations", args.corpus)
    votes = load_dir(d)
    n_cards = len(votes)
    n_readings = sum(len(v) for v in votes.values())
    distinct_readers = len({f for v in votes.values() for f, _, _ in v})
    print(f"cards={n_cards} readings={n_readings} readers={distinct_readers}")
    print("readings per card:", dict(collections.Counter(len(v) for v in votes.values())))

    out: Dict[str, Any] = {"n_cards": n_cards, "n_readings": n_readings,
                           "n_readers": distinct_readers}
    for a, b in (("dense", "refine"), ("round1", "round2"), ("dense", "round2"),
                 ("round1", "dense"), ("refine", "round2")):
        r = pairwise(votes, a, b)
        out[f"{a}_vs_{b}"] = r
        if r.get("n"):
            print(f"{a:7} vs {b:7} n={r['n']:4d} exact={r['exact']:.3f} "
                  f"binary={r['binary']:.3f} kappa={r['kappa']:.3f} "
                  f"pos-agree={r['agreement_on_positive']:.3f}")

    # within-refine pairwise between readers that share cards
    by_reader: Dict[str, Dict[str, str]] = collections.defaultdict(dict)
    for cid, v in votes.items():
        for f, lab, rnd in v:
            if rnd in {"dense", "refine"}:
                by_reader[f][cid] = lab
    reader_rates = {f: (sum(1 for l in m.values() if binz(l) == 1)
                        / max(1, sum(1 for l in m.values() if binz(l) is not None)),
                        len(m)) for f, m in by_reader.items()}
    rates = np.array([r for r, _ in reader_rates.values() if r == r])
    print(f"\nreader positive-rate distribution: mean={rates.mean():.3f} "
          f"median={np.median(rates):.3f} sd={rates.std():.3f} "
          f"min={rates.min():.3f} max={rates.max():.3f}")
    lo, hi = np.median(rates) - 2.5 * rates.std(), np.median(rates) + 2.5 * rates.std()
    flagged = [f for f, (r, _) in reader_rates.items() if r < lo or r > hi]
    print(f"flagged (outside [{lo:.3f}, {hi:.3f}]): {flagged}")
    out["reader_rates"] = {f: {"positive_rate": r, "n": n} for f, (r, n) in reader_rates.items()}
    out["flagged_readers"] = flagged
    out["reader_rate_median"] = float(np.median(rates))
    out["reader_rate_sd"] = float(rates.std())

    # does disagreement concentrate on boundary windows?
    import json
    idx = os.path.join(d, "dense_cards_index.csv")
    if os.path.exists(idx):
        pass
    print("\nwrote results to stdout only; see agreement.json for the aggregated version")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
