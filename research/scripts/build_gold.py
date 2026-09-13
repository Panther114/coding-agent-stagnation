"""Merge all annotation rounds into gold labels.

Rounds
------
* ``labels_r*.csv``      round 1, full context, one reader per card (position sample)
* ``labels_p2_s*.csv``   round 2, reduced context, a *different* reader per card
* ``labels_dense_*.csv`` round 3, dense sample, one reader per card (region building)

Gold label = majority over readers within a round, requiring within-round agreement;
cards with conflicting reads are marked UNCERTAIN and held out.  Cross-round agreement is
reported as a label-stability statistic, not used to adjudicate (the round-2 cards contain
strictly less context, so disagreement there is expected and informative).

Usage: python scripts/build_gold.py --corpus tb2
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402

import paths  # noqa: E402

PRIOR_POS = 0.28

POSITIVE = {"STAGNANT", "DONE_REDUNDANT"}
NEGATIVE = {"PRODUCTIVE", "REGRESSION"}
HELDOUT = {"BLOCKED_EXTERNAL", "UNCERTAIN"}
KNOWN_DETAILS = {"repeat_search", "repeat_read", "repeat_verify", "edit_revert",
                 "irrelevant_exploration", "no_new_information", "post_completion",
                 "no_tool_text_loop", "other"}


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r.get("card_id")]


def label_col(path: str) -> Optional[str]:
    rows = read_csv(path)
    if not rows:
        return None
    for k in rows[0]:
        if k and k.startswith("label"):
            return k
    return None


def collect(files: Sequence[str]) -> Dict[str, List[Dict[str, str]]]:
    """card_id -> list of {label, confidence, boundary, channels, detail, reason}.

    A reader may appear more than once for the same card when a batch was topped up or when
    two readers wrote to the same path; such repeats are collapsed to a single vote per
    (reader, card) so that a duplicated row cannot outvote the rest of the panel.
    """
    out: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    seen: Dict[str, set] = defaultdict(set)
    for f in files:
        lc = label_col(f)
        if not lc:
            continue
        base = os.path.basename(f)
        for r in read_csv(f):
            lab = (r.get(lc) or "").strip().upper()
            if not lab:
                continue
            cid = r["card_id"]
            if (base, cid) in seen[cid]:
                continue
            seen[cid].add((base, cid))
            out[cid].append({
                "label": lab,
                "confidence": (r.get(lc.replace("label", "confidence")) or "").strip().lower(),
                "boundary": (r.get(lc.replace("label", "boundary")) or "").strip().lower(),
                "channels": (r.get(lc.replace("label", "channels")) or "").strip().upper(),
                "detail": (r.get(lc.replace("label", "detail")) or "").strip().lower(),
                "reason": (r.get(lc.replace("label", "reason")) or r.get(
                    lc.replace("label", "justification")) or "").strip(),
                "file": base,
            })
    return out


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def binz(lab: str) -> Optional[int]:
    lab = (lab or "").strip().upper()
    if lab in POSITIVE:
        return 1
    if lab in NEGATIVE:
        return 0
    return None


def compare_maps(A: Dict[str, str], B: Dict[str, str]) -> Dict[str, Any]:
    common = sorted(set(A) & set(B))
    if not common:
        return {"n": 0}
    la = [A[c] for c in common]
    lb = [B[c] for c in common]
    pairs = [(binz(x), binz(y)) for x, y in zip(la, lb)]
    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    pos_a = {c for c in common if binz(A[c]) == 1}
    pos_b = {c for c in common if binz(B[c]) == 1}
    return {
        "n": len(common),
        "exact_agreement": sum(1 for x, y in zip(la, lb) if x == y) / len(common),
        "binary_agreement": (sum(1 for x, y in pairs if x == y) / len(pairs)) if pairs else float("nan"),
        "cohen_kappa": cohen_kappa([str(x) for x, _ in pairs], [str(y) for _, y in pairs]) if pairs else float("nan"),
        "positive_jaccard": (len(pos_a & pos_b) / len(pos_a | pos_b)) if (pos_a | pos_b) else float("nan"),
        "n_positive_a": len(pos_a), "n_positive_b": len(pos_b),
        "n_binary": len(pairs),
    }


def merge_ranges(ranges: Sequence[Tuple[int, int]], gap: int = 0) -> List[List[int]]:
    rs = sorted(ranges)
    out: List[List[int]] = []
    for a, b in rs:
        if out and a <= out[-1][1] + 1 + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def labeler_qc(files: Sequence[str], prefix: str = "") -> Dict[str, Any]:
    """Per-file positive rate and outlier flag.

    Each annotation round was produced by many independent readers.  A reader who is
    systematically miscalibrated (e.g. labels everything stagnant, or never does) would add
    noise to the gold set, so we measure each file's positive rate against the median across
    readers of the same round and flag files outside a tolerance band.  Flagged files are
    reported and can be excluded from adjudication.
    """
    stats: Dict[str, Any] = {}
    rates: List[Tuple[str, float]] = []
    for f in files:
        lc = label_col(f)
        if not lc:
            continue
        rows = read_csv(f)
        if not rows:
            continue
        pos = sum(1 for r in rows if binz(r.get(lc, "")) == 1)
        bin_n = sum(1 for r in rows if binz(r.get(lc, "")) is not None)
        rate = pos / bin_n if bin_n else float("nan")
        stats[os.path.basename(f)] = {"n": len(rows), "n_binary": bin_n, "positives": pos,
                                      "positive_rate": rate}
        if rate == rate:
            rates.append((os.path.basename(f), rate))
    if not rates:
        return {"files": stats, "median_positive_rate": float("nan"), "flagged": []}
    vals = np.asarray([r for _, r in rates], dtype=float) if "np" in globals() else None
    med = float(np.median([r for _, r in rates]))
    tol = float(np.std([r for _, r in rates])) * 2.5 + 0.02 if len(rates) > 3 else 0.25
    flagged = [name for name, r in rates if abs(r - med) > max(tol, 0.30)]
    for name in stats:
        stats[name]["flagged"] = name in flagged
    return {"files": stats, "median_positive_rate": med, "tolerance": max(tol, 0.30),
            "flagged": flagged}


def em_calibrate(
    votes: Dict[str, List[Tuple[str, int]]],
    n_iter: int = 200,
    tol: float = 1e-6,
    leniency_threshold: float = 0.25,
) -> Tuple[Dict[str, float], Dict[str, float], List[str]]:
    """Dawid--Skene style EM for binary labels with one sensitivity parameter per reader.

    ``votes[card_id]`` is a list of ``(reader, y)``.  Each reader $r$ gets a single
    sensitivity $\pi_r = P(\text{reader says positive} \mid \text{card is positive})$, so a
    reader who is systematically trigger-happy or systematically conservative is absorbed by
    that parameter instead of distorting the consensus.  Returns the per-card posterior that
    the true label is positive, the per-reader sensitivities, and the readers excluded for
    being outside the calibrated band.
    """
    readers = sorted({r for v in votes.values() for r, _ in v})
    if not readers:
        return {}, {}, []
    pi = {r: 0.7 for r in readers}
    p = {c: (0.5 if sum(y for _, y in v) * 2 >= len(v) else 0.2) for c, v in votes.items()}
    prev_ll = None
    for _ in range(n_iter):
        # M-step
        num = {r: 0.0 for r in readers}
        den = {r: 0.0 for r in readers}
        ll = 0.0
        for c, v in votes.items():
            pc = min(max(p[c], 1e-6), 1 - 1e-6)
            ll += 0.0
            for r, y in v:
                if y == 1:
                    num[r] += pc
                den[r] += pc
        pi_new = {r: (num[r] / den[r] if den[r] > 0 else 0.5) for r in readers}
        pi_new = {r: min(max(v, 0.05), 0.95) for r, v in pi_new.items()}
        # E-step
        new_p = {}
        loglik = 0.0
        for c, v in votes.items():
            lp1 = math.log(PRIOR_POS)
            lp0 = math.log(1 - PRIOR_POS)
            for r, y in v:
                s = pi_new[r] if y == 1 else (1 - pi_new[r])
                lp1 += math.log(max(s, 1e-9))
                s0 = (1 - pi_new[r]) if y == 1 else pi_new[r]
                lp0 += math.log(max(s0, 1e-9))
            m = max(lp1, lp0)
            e1, e0 = math.exp(lp1 - m), math.exp(lp0 - m)
            new_p[c] = e1 / (e1 + e0)
            loglik += m + math.log(e1 + e0)
        pi = pi_new
        p = new_p
        if prev_ll is not None and abs(loglik - prev_ll) < tol:
            break
        prev_ll = loglik
    flagged = [r for r in readers if abs(pi[r] - 0.5) > leniency_threshold]
    return p, pi, flagged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--dir", default=None)
    args = ap.parse_args()
    d = args.dir or os.path.join(paths.DATA, "annotations", args.corpus)

    def find(pat: str) -> List[str]:
        return sorted(glob.glob(os.path.join(d, pat)))

    f_r1 = find("labels_r[0-9]*.csv")
    f_p2 = find("labels_p2_s*.csv")
    f_dense = find("labels_dense_*.csv")

    # ---- metadata for every card that exists in any index ----
    # All three card indices must be read.  Missing one silently orphans every label attached to
    # its cards: they are collected from the label files but never reach the gold set, so the
    # evaluation runs on a fraction of the available annotation.  That defect cost 552 labelled
    # windows (654 versus 1,206 usable) before it was found, and `scripts/size_orphan_defect.py`
    # now checks for it.
    meta: Dict[str, Dict[str, str]] = {}
    indices_read = []
    for idx_name in ("cards_index.csv", "dense_cards_index.csv", "dense2_cards_index.csv"):
        p = os.path.join(d, idx_name)
        if os.path.exists(p):
            rows = read_csv(p)
            for r in rows:
                r = dict(r)
                r.setdefault("kind", "position")
                meta[r["card_id"]] = r
            indices_read.append((idx_name, len(rows)))
    print(f"indices read: {indices_read}  -> {len(meta)} cards")

    f_refine = find("labels_refine_*.csv")
    maps = {"round1": collect(f_r1), "round2": collect(f_p2),
            "dense": collect(f_dense), "refine": collect(f_refine)}
    print({k: len(v) for k, v in maps.items()})

    # ---- per-card gold label ----
    # Adjudication is transparent majority voting over the readers who pass the calibration
    # filter.  With 55 independent readers whose positive rates cluster tightly around the
    # panel median (see agreement.json -> reader_qc), a majority is both simpler and less
    # assumptive than a latent-variable model, and it keeps every label auditable back to the
    # readers that produced it.  A card with an even split becomes UNCERTAIN and is held out.
    # Reader calibration is *reported*, not used to filter.  A reader's positive rate depends
    # on which trajectories they were assigned (the refinement round gave each reader a
    # contiguous block, and a few trajectories in this sample are so thoroughly stuck that
    # every reader who saw them labelled nearly everything stagnant), so a rate-based filter
    # would exclude exactly the readers who looked at the most interesting runs.  We instead
    # report the panel distribution and use plain majority voting, which is transparent,
    # auditable, and --- as check_agreement.py shows --- consistent across reading regimes.
    reader_cards: Dict[str, set] = defaultdict(set)
    reader_pos: Dict[str, List[int]] = defaultdict(list)
    card_readers: Dict[str, List[str]] = defaultdict(list)
    card_bin: Dict[str, List[int]] = defaultdict(list)
    for f in (f_r1 + f_p2 + f_dense + f_refine):
        lc = label_col(f)
        if not lc:
            continue
        base = os.path.basename(f)
        for r in read_csv(f):
            y = binz(r.get(lc, ""))
            if y is None:
                continue
            reader_cards[base].add(r["card_id"])
            reader_pos[base].append(y)
            card_readers[r["card_id"]].append(base)
            card_bin[r["card_id"]].append(y)
    reader_rates = {f: (sum(v) / len(v)) for f, v in reader_pos.items() if v}
    med = float(np.median(list(reader_rates.values()))) if reader_rates else float("nan")
    robust_sd = (1.4826 * float(np.median([abs(r - med) for r in reader_rates.values()]))
                 if reader_rates else float("nan"))
    print(f"reader calibration: n={len(reader_rates)} median_positive_rate={med:.3f} "
          f"robust_sd={robust_sd:.3f}")
    flagged: List[str] = []          # reported only; see comment above
    flagged_set: set = set()

    rows: List[Dict[str, Any]] = []
    for cid, m in sorted(meta.items()):
        reads = maps["round1"].get(cid, []) + maps["dense"].get(cid, []) + maps["refine"].get(cid, [])
        r2 = maps["round2"].get(cid, [])
        if not reads:
            continue
        usable = [r for r in reads if r["file"] not in flagged_set]
        if not usable:
            usable = reads
        labels = [r["label"] for r in usable]
        all_labels = labels + [r["label"] for r in r2]
        cnt = Counter(labels)
        top, topn = cnt.most_common(1)[0]
        tie = (topn * 2 == len(labels)) and len(cnt) > 1
        gold = "UNCERTAIN" if tie else top
        binary = 1 if gold in POSITIVE else (0 if gold in NEGATIVE else None)
        det = Counter(r["detail"] for r in usable if r["detail"] in KNOWN_DETAILS)
        chans = Counter(r["channels"] for r in usable if r["channels"])
        rows.append({
            "card_id": cid, "traj_id": m["traj_id"], "task": m["task"], "agent": m["agent"],
            "model": m["model"], "reward": m["reward"], "n_steps": int(m["n_steps"]),
            "t": int(m["t"]), "w": int(m["w"]), "kind": m.get("kind", "position"),
            "n_reads": len(usable), "votes": "|".join(labels), "gold": gold, "binary": binary,
            "unanimous": int(len(set(labels)) == 1),
            "n_readers_total": len(all_labels),
            "detail": (det.most_common(1)[0][0] if det else ""),
            "channels": (chans.most_common(1)[0][0] if chans else ""),
            "has_round2": int(bool(r2)),
            "round2_label": (r2[0]["label"] if r2 else ""),
            "reason": (usable[0]["reason"][:200] if usable else ""),
        })

    with open(os.path.join(d, "adjudicated.csv"), "w", newline="", encoding="utf-8") as fh:
        wtr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)
    print(f"adjudicated {len(rows)} cards")

    # ---- agreement ----
    first_of = {k: {cid: v[0]["label"] for cid, v in mp.items()} for k, mp in maps.items()}
    qc = {k: labeler_qc(files) for k, files in
          (("round1", f_r1), ("round2", f_p2), ("dense", f_dense), ("refine", f_refine))}
    agree: Dict[str, Any] = {
        "n_cards": len(rows), "n_readings": {k: sum(len(v) for v in mp.values()) for k, mp in maps.items()},
        "cross_round": compare_maps(first_of["round1"], first_of["round2"]),
        "round1_vs_dense": compare_maps(first_of["round1"], first_of["dense"]),
        "dense_vs_round2": compare_maps(first_of["dense"], first_of["round2"]),
        "reader_calibration": {
            "n_readers": len(reader_rates),
            "positive_rate_median": med, "robust_sd": robust_sd,
            "flagged_readers": flagged,
            "rates": {k: round(v, 4) for k, v in sorted(reader_rates.items())},
        },
        "reader_qc": {k: {"median_positive_rate": v["median_positive_rate"],
                          "flagged": v["flagged"]} for k, v in qc.items()},
    }
    # two independent readers inside round 3
    dense_files = f_dense
    if len(dense_files) >= 2:
        half = len(dense_files) // 2
        A = collect(dense_files[:half])
        B = collect(dense_files[half:])
        agree["dense_split"] = compare_maps({k: v[0]["label"] for k, v in A.items()},
                                            {k: v[0]["label"] for k, v in B.items()})
    agree["labels"] = dict(Counter(r["gold"] for r in rows).most_common())
    binary_rows = [r for r in rows if r["binary"] is not None]
    agree["n_binary"] = len(binary_rows)
    agree["positive_rate"] = sum(r["binary"] for r in binary_rows) / max(1, len(binary_rows))
    agree["n_held_out"] = len(rows) - len(binary_rows)
    agree["details"] = dict(Counter(r["detail"] for r in rows if r["detail"]).most_common())
    agree["channels"] = dict(Counter(r["channels"] for r in rows if r["channels"]).most_common())
    agree["by_kind"] = {}
    for kind in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == kind]
        sub_b = [r for r in sub if r["binary"] is not None]
        agree["by_kind"][kind] = {"n": len(sub), "n_binary": len(sub_b),
                                  "positive_rate": sum(r["binary"] for r in sub_b) / max(1, len(sub_b))}
    agree["by_agent"] = {}
    for ag in sorted({r["agent"] for r in rows}):
        sub = [r for r in rows if r["agent"] == ag and r["binary"] is not None]
        agree["by_agent"][ag] = {
            "n": len(sub), "positive_rate": sum(r["binary"] for r in sub) / max(1, len(sub)),
            "mean_steps": sum(r["n_steps"] for r in rows if r["agent"] == ag) / max(1, len([r for r in rows if r["agent"] == ag])),
            "positive_fraction": sum(r["binary"] for r in sub) / max(1, len(sub)),
        }
    rew = defaultdict(lambda: Counter())
    for r in binary_rows:
        rew[str(r["reward"])]["POS" if r["binary"] == 1 else "NEG"] += 1
    agree["label_by_reward"] = {k: dict(v) for k, v in rew.items()}
    # correlation between window label and final success (independent of the monitor)
    with open(os.path.join(d, "agreement.json"), "w", encoding="utf-8") as fh:
        json.dump(agree, fh, indent=2)

    # ---- regions ----
    by_traj: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_traj[r["traj_id"]].append(r)
    regions: Dict[str, Any] = {}
    for tid, items in by_traj.items():
        items.sort(key=lambda x: x["t"])
        w = items[0]["w"]
        st = [(max(0, a["t"] - w + 1), a["t"]) for a in items if a["binary"] == 1]
        pr = [(max(0, a["t"] - w + 1), a["t"]) for a in items if a["binary"] == 0]
        regions[tid] = {
            "task": items[0]["task"], "agent": items[0]["agent"], "model": items[0]["model"],
            "reward": items[0]["reward"], "n_steps": items[0]["n_steps"], "w": w,
            "n_windows": len(items), "n_positive": sum(1 for a in items if a["binary"] == 1),
            "n_negative": sum(1 for a in items if a["binary"] == 0),
            "stagnant_ranges": merge_ranges(st), "productive_ranges": merge_ranges(pr),
            "windows": [{k: a[k] for k in ("card_id", "t", "gold", "binary", "detail", "channels")}
                        for a in items],
        }
    with open(os.path.join(d, "gold_regions.json"), "w", encoding="utf-8") as fh:
        json.dump(regions, fh, indent=2)

    print(json.dumps({k: v for k, v in agree.items() if k not in ("by_agent",)}, indent=2)[:2600])
    n_pos_traj = sum(1 for v in regions.values() if v["n_positive"] > 0)
    print(f"\nregions: {len(regions)} trajectories, {n_pos_traj} with >=1 stagnant window")
    print(f"wrote adjudicated.csv, agreement.json, gold_regions.json in {d}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
