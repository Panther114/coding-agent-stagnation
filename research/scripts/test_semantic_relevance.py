"""Does semantic relevance fix the evidence channel, where lexical relevance did not?

The first study's hypothesis was that weighting newly observed entities by whether they concern the
task statement detects stagnation better than relevance-blind novelty.  It lost (ROC 0.587 vs the
0.608 exact-repeat baseline and 0.775 semantic baseline), but its relevance function was literal
token overlap between entity text and task words --- so a discovery about `flask` scored zero for a
task saying "set up a web server".

This reruns the *same evidence features, on the same windows, under the same task-disjoint folds*,
varying only the relevance function:

    lexical   : fraction of the entity's tokens present in the task statement   (v1)
    semantic  : cosine similarity between the entity and the task statement     (v2, MiniLM)

If semantic relevance beats lexical relevance materially, the first study's negative finding about
its own hypothesis is explained as an instrument failure rather than a refuted idea.  That is a
positive, well-identified result.

Usage: python scripts/test_semantic_relevance.py
"""
from __future__ import annotations

import csv
import json
import os
import pickle
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np

from evidence import STOPWORDS, extract_entities, task_terms  # noqa: E402

PROC = "data/processed/tb2/sample_trajectories.jsonl"
GOLD = "data/annotations/tb2/adjudicated.csv"
CACHE = os.path.abspath("data/raw/models")
OUT = "results/final/v2"
os.makedirs(OUT, exist_ok=True)
W = 10
THR = 0.5
# v1's EVID feature set, by name
EVID = ["ev_relevance_mean", "ev_relevance_max", "ev_new_relevant_rate",
        "ev_new_relevant_frac", "ev_new_highrel_rate", "ev_rel_weighted_novelty",
        "ev_persist_rate"]


def roc_auc(y, s):
    y = np.asarray(y)
    s = np.asarray(s, dtype=float)
    ok = ~np.isnan(s)
    y, s = y[ok], s[ok]
    if y.size == 0 or y.min() == y.max():
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ss = s[order]
    ranks = np.empty(len(s), dtype=float)
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def main() -> None:
    # ---- per-step entities, and each trajectory's task statement ----
    # the task *statement* is the first step's text; `task` is only the task name
    steps = {}
    stmts = {}
    for line in open(PROC, encoding="utf-8"):
        t = json.loads(line)
        s0 = t["steps"][0] if t.get("steps") else {}
        stmts[t["traj_id"]] = str(s0.get("text") or "").strip()
        for i, s in enumerate(t["steps"]):
            text = (str(s.get("msg") or "") + "\n" + str(s.get("obs") or ""))
            steps[(t["traj_id"], i)] = extract_entities(text, "obs")
    n_ent = sum(len(v) for v in steps.values())
    print(f"trajectories: {len(stmts)}; steps: {len(steps)}; entities: {n_ent}")
    print(f"task statements resolved: {sum(1 for v in stmts.values() if v)}")

    # ---- gold windows ----
    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8"))
            if r["binary"] != "" and int(r["w"]) == W]
    print(f"gold windows at w={W}: {len(gold)}")

    # ---- for each window: newly seen entities, and their relevance under both functions ----
    # precompute, per trajectory, which entities are new at each step, plus the running set
    first_seen = {}
    per_traj = {}
    for (tid, i), ents in steps.items():
        per_traj.setdefault(tid, {})[i] = ents
    for tid, by_step in per_traj.items():
        prior = set()
        tbl = {}
        for i in sorted(by_step):
            ents = by_step[i]
            new_here = [e for e in ents if e.key not in prior]
            prior.update(e.key for e in ents)
            tbl[i] = (new_here, list(prior))
        first_seen[tid] = tbl
    print(f"trajectories indexed: {len(first_seen)}")

    wins = []
    for r in gold:
        tid, t = r["traj_id"], int(r["t"])
        idx = first_seen.get(tid)
        if not idx:
            continue
        keys = [i for i in range(t - W + 1, t + 1) if i in idx]
        if not keys:
            continue
        new_ents = [e for i in keys for e in idx[i][0]]
        all_ents = idx[keys[-1]][1]
        wins.append({"traj": tid, "t": t, "task": r["task"], "y": int(r["binary"]),
                     "new": new_ents, "all_keys": all_ents, "n": len(keys)})

    print(f"windows with entities: {len(wins)}; "
          f"mean new entities per window {np.mean([len(w['new']) for w in wins]):.1f}")
    if not wins:
        print("no windows -- cannot test")
        return

    # ---- embeddings for task statements and entities ----
    uniq_ent = sorted({e.key.split("|", 1)[-1] for w in wins for e in w["new"]})
    uniq_stmt = sorted({stmts.get(w["traj"], "") for w in wins} - {""})
    print(f"unique entities: {len(uniq_ent)}; unique task statements: {len(uniq_stmt)}")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2",
                               cache_folder=CACHE, device="cpu")
    t0 = time.time()
    E_ent = model.encode(uniq_ent, batch_size=256, normalize_embeddings=True,
                         show_progress_bar=False)
    E_st = model.encode(uniq_stmt, batch_size=64, normalize_embeddings=True,
                        show_progress_bar=False)
    print(f"embedded in {time.time()-t0:.0f}s  ({E_ent.shape}, {E_st.shape})")
    ei = {u: i for i, u in enumerate(uniq_ent)}
    si = {u: i for i, u in enumerate(uniq_stmt)}

    # ---- features under both relevance functions ----
    def feats_for(mode):
        F = {k: [] for k in EVID}
        for w in wins:
            stmt = stmts.get(w["traj"], "")
            terms = task_terms(stmt)
            sv = E_st[si[stmt]] if stmt in si else None
            rels = []
            for e in w["new"]:
                val = e.key.split("|", 1)[-1]
                if mode == "lexical":
                    toks = [x for x in re.split(r"[^A-Za-z0-9_]+", val.lower()) if x]
                    toks = [x for x in toks if len(x) >= 3 and x not in STOPWORDS]
                    rels.append(sum(1 for x in toks if x in terms) / len(toks) if toks else 0.0)
                else:
                    if sv is None or val not in ei:
                        rels.append(0.0)
                    else:
                        rels.append(max(0.0, float(E_ent[ei[val]] @ sv)))
            n = max(1, w["n"])
            F["ev_relevance_mean"].append(float(np.mean(rels)) if rels else 0.0)
            F["ev_relevance_max"].append(float(np.max(rels)) if rels else 0.0)
            F["ev_new_relevant_rate"].append(sum(1 for x in rels if x >= THR) / n)
            F["ev_new_relevant_frac"].append(sum(1 for x in rels if x >= THR) / max(1, len(rels)))
            F["ev_new_highrel_rate"].append(sum(1 for x in rels if x >= 0.8) / n)
            F["ev_rel_weighted_novelty"].append(sum(rels) / n)
            F["ev_persist_rate"].append(len(rels) / n)
        return {k: np.asarray(v, dtype=float) for k, v in F.items()}

    lex = feats_for("lexical")
    sem = feats_for("semantic")

    y = np.array([w["y"] for w in wins])
    tasks = sorted({w["task"] for w in wins})
    rng = np.random.default_rng(11)
    folds = np.array_split(rng.permutation(len(tasks)), 5)
    task_of = [w["task"] for w in wins]

    def fit_predict(F):
        pred = np.full(len(y), np.nan)
        for f in folds:
            test = {tasks[i] for i in f}
            tr = np.array([t not in test for t in task_of])
            te = ~tr
            parts = []
            for k in EVID:
                v = F[k]
                mu, sd = np.nanmean(v[tr]), np.nanstd(v[tr])
                if not np.isfinite(sd) or sd < 1e-12:
                    continue
                z = np.clip((v - mu) / (3 * sd), -1, 1)
                a, b = z[tr & (y == 1)], z[tr & (y == 0)]
                if len(a) and len(b) and np.nanmean(a) < np.nanmean(b):
                    z = -z
                parts.append(z)
            if parts:
                pred[te] = np.nanmean(np.vstack([p[te] for p in parts]), axis=0)
        return pred

    print(f"\nwindows={len(wins)}  positive rate={y.mean():.3f}")
    print("\n=== evidence channel, alone, task-disjoint ===")
    res = {}
    for name, F in (("lexical (v1 implementation)", lex), ("semantic (MiniLM relevance)", sem)):
        p = fit_predict(F)
        a = roc_auc(y, p)
        res[name] = a
        print(f"  {name:32} ROC {a:.3f}")
        for k in EVID:
            aa = roc_auc(y, F[k])
            if np.isfinite(aa):
                print(f"      {k:26} {aa:.3f} (two-sided {max(aa,1-aa):.3f})")

    print("\n=== reference points ===")
    for m, lab in (("C1_evidence", "v1 C1_evidence (lexical)"),
                   ("B2_exact_rep3", "v1 exact repetition"),
                   ("B4_semantic", "v1 semantic (BoW)")):
        import pyarrow.parquet as pq
        stored = {}
        for r in pq.read_table("results/final/tb2_v5/monitor_scores.parquet",
                               columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
            if r["monitor"] == m and r["w"] == W:
                stored[(r["traj_id"], r["t"])] = r["score"]
        s = np.array([stored.get((w["traj"], w["t"]), np.nan) for w in wins])
        a = roc_auc(y, s)
        res[lab] = a
        print(f"  {lab:32} ROC {a:.3f}")

    json.dump({"auc": res, "n_windows": len(wins), "positive_rate": float(y.mean())},
              open(os.path.join(OUT, "semantic_relevance_test.json"), "w", encoding="utf-8"),
              indent=2)
    with open(os.path.join(OUT, "evidence_features_both.pkl"), "wb") as fh:
        pickle.dump({"wins": [{"traj": w["traj"], "t": w["t"], "task": w["task"], "y": w["y"]}
                              for w in wins], "lexical": lex, "semantic": sem, "y": y}, fh)
    print(f"\nwrote {OUT}/semantic_relevance_test.json")


if __name__ == "__main__":
    main()
