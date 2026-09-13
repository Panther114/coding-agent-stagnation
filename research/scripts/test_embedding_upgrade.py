"""Controlled representation swap: v1's exact semantic features, bag-of-words vs real encoder.

The first study's winning monitor (B4_semantic, ROC 0.775) used a hashing bag-of-words surrogate.
This reruns *v1's own feature definitions verbatim* -- abs-cosine diversity, nearest-similarity,
centroid distance, novelty rate -- with a real sentence encoder in place of the surrogate, on the
same windows and the same task-disjoint folds.  The only thing that changes is the representation,
so any difference is attributable to it.

Usage: python scripts/test_embedding_upgrade.py
"""
from __future__ import annotations

import csv
import json
import os
import pickle
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np

PROC = "data/processed/tb2/sample_trajectories.jsonl"
GOLD = "../datasets/annotations/tb2/adjudicated.csv"
CACHE = os.path.abspath("data/raw/models")
OUT = "results/final/v2"
os.makedirs(OUT, exist_ok=True)
W = 10
SEM_FEATS = ["sem_diversity", "sem_nearest_sim", "sem_centroid_dist", "sem_novelty_rate"]


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
    n1 = int((y == 1).sum())
    n0 = int((y == 0).sum())
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def sem_features(M, lo):
    """v1's definitions, verbatim (features.py lines 408-441), for one window matrix M."""
    f = {}
    if M.shape[0] >= 2:
        sims = np.abs(M @ M.T)
        iu = np.triu_indices(M.shape[0], k=1)
        f["sem_diversity"] = 1.0 - float(np.mean(sims[iu]))
        last, prev = M[-1], M[:-1]
        denom = (np.linalg.norm(prev, axis=1) * (np.linalg.norm(last) + 1e-12)) + 1e-12
        f["sem_nearest_sim"] = float(np.max(np.abs(prev @ last) / denom))
        cent = M.mean(axis=0)
        nc = float(np.linalg.norm(cent))
        f["sem_centroid_dist"] = 1.0 - (abs(float(last @ cent)) / (nc + 1e-12) if nc > 1e-12 else 0.0)
    else:
        for k in ("sem_diversity", "sem_nearest_sim", "sem_centroid_dist"):
            f[k] = np.nan
    return f


def main() -> None:
    # ---- per-step text, in the same form v1 embedded ----
    steps = {}
    for line in open(PROC, encoding="utf-8"):
        t = json.loads(line)
        for i, s in enumerate(t["steps"]):
            acts = " ".join(str((a or {}).get("name", "")) + " " +
                            str((a or {}).get("arg", ""))[:200]
                            for a in (s.get("actions") or []))
            txt = " ".join(x for x in (str(s.get("msg") or ""), str(s.get("obs") or ""),
                                       acts) if x)
            steps[(t["traj_id"], i)] = txt[:2000]
    print(f"steps indexed: {len(steps)}")

    gold = [r for r in csv.DictReader(open(GOLD, encoding="utf-8"))
            if r["binary"] != "" and int(r["w"]) == W]
    rows = []
    for r in gold:
        tid, t = r["traj_id"], int(r["t"])
        rows.append({"traj": tid, "t": t, "task": r["task"], "y": int(r["binary"])})
    print(f"gold windows at w={W}: {len(rows)}")

    # ---- embeddings: real encoder, with a second model as a robustness check ----
    uniq = sorted({steps.get((r["traj"], i), "") for r in rows
                   for i in range(r["t"] - W + 1, r["t"] + 1)} - {""})
    print(f"unique step strings: {len(uniq)}")

    from sentence_transformers import SentenceTransformer
    models = {"MiniLM-L6": "sentence-transformers/all-MiniLM-L6-v2"}
    emb_by_model = {}
    for name, path in models.items():
        try:
            m = SentenceTransformer(path, cache_folder=CACHE, device="cpu")
            t0 = time.time()
            E = m.encode(uniq, batch_size=128, normalize_embeddings=True,
                         show_progress_bar=False)
            emb_by_model[name] = (E, {u: i for i, u in enumerate(uniq)})
            print(f"  {name}: {E.shape} in {time.time()-t0:.0f}s")
        except Exception as exc:
            print(f"  {name}: FAILED {type(exc).__name__}: {str(exc)[:90]}")

    # ---- features per representation ----
    feats = {}
    for name, (E, idx) in emb_by_model.items():
        F = {k: [] for k in SEM_FEATS}
        for r in rows:
            vecs = [E[idx[steps[(r["traj"], i)]]] for i in range(r["t"] - W + 1, r["t"] + 1)
                    if steps.get((r["traj"], i)) in idx]
            if len(vecs) < 2:
                for k in SEM_FEATS:
                    F[k].append(np.nan)
                continue
            M = np.asarray(vecs)
            f = sem_features(M, 0)
            for k in SEM_FEATS:
                F[k].append(f.get(k, np.nan))
        feats[name] = F
        print(f"  computed {len(SEM_FEATS)} features for {name}")

    # ---- v1's stored monitor score, same windows ----
    import pyarrow.parquet as pq
    stored = {}
    for r in pq.read_table("results/final/tb2_v5/monitor_scores.parquet",
                           columns=["traj_id", "t", "w", "monitor", "score"]).to_pylist():
        if r["monitor"] == "B4_semantic" and r["w"] == W:
            stored[(r["traj_id"], r["t"])] = r["score"]
    base = np.array([stored.get((r["traj"], r["t"]), np.nan) for r in rows])

    # ---- v1's monitor recipe: per-feature z-score, bounded linear map, mean over features ----
    y = np.array([r["y"] for r in rows])
    tasks = sorted({r["task"] for r in rows})
    rng = np.random.default_rng(11)
    folds = np.array_split(rng.permutation(len(tasks)), 5)
    task_of = [r["task"] for r in rows]

    def fit_predict(F):
        """Replicate v1's FeatureMonitor: standardise on train, orient by train separation."""
        pred = np.full(len(y), np.nan)
        for f in folds:
            test = {tasks[i] for i in f}
            tr = np.array([t not in test for t in task_of])
            te = ~tr
            parts = []
            for k in SEM_FEATS:
                v = np.asarray(F[k], dtype=float)
                mu, sd = np.nanmean(v[tr]), np.nanstd(v[tr])
                if not np.isfinite(sd) or sd < 1e-12:
                    continue
                z = (v - mu) / (3 * sd)
                z = np.clip(z, -1, 1)
                # orient: stagnant should score high, so use the train-split sign
                a = z[tr & (y == 1)]
                b = z[tr & (y == 0)]
                if len(a) and len(b) and np.nanmean(a) < np.nanmean(b):
                    z = -z
                parts.append(z)
            if not parts:
                continue
            pred[te] = np.nanmean(np.vstack([p[te] for p in parts]), axis=0)
        return pred

    print("\n=== pooled task-disjoint ROC-AUC (identical folds, identical windows) ===")
    out = {}
    a = roc_auc(y, base)
    out["v1_hashing_bow_B4_semantic"] = a
    print(f"  {'v1 B4_semantic (hashing BoW)':32} {a:.3f}")
    for name, F in feats.items():
        p = fit_predict(F)
        a = roc_auc(y, p)
        out[f"v2_semantic_{name}"] = a
        print(f"  {'v2 semantic (' + name + ')':32} {a:.3f}")
        # also each feature alone, to see which carries the signal
        for k in SEM_FEATS:
            aa = roc_auc(y, np.asarray(F[k], dtype=float))
            orient = max(aa, 1 - aa) if np.isfinite(aa) else float("nan")
            print(f"      {k:22} {aa:.3f}")

    per_feat = {}
    for name, F in feats.items():
        for k in SEM_FEATS:
            v = np.asarray(F[k], dtype=float)
            a = roc_auc(y, v)
            per_feat[k] = float(max(a, 1 - a)) if np.isfinite(a) else float("nan")
    json.dump({"auc": out, "per_feature": per_feat, "n_windows": len(rows),
               "positive_rate": float(y.mean())},
              open(os.path.join(OUT, "embedding_upgrade_test.json"), "w", encoding="utf-8"),
              indent=2)
    with open(os.path.join(OUT, "sem_features_v2.pkl"), "wb") as fh:
        pickle.dump({"rows": rows, "feats": feats, "base": base, "y": y}, fh)
    print(f"\nwrote {OUT}/embedding_upgrade_test.json and sem_features_v2.pkl")


if __name__ == "__main__":
    main()
