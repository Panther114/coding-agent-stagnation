"""Semantic-novelty channel without a download.

The comparison this study needs is a *rolling semantic redundancy* baseline of the kind
used by livelock-detection work: represent each (action, observation) step, and watch how
similar the recent representations are.  The natural implementation uses a pretrained
sentence encoder; in this environment the model host was unreachable (see
``docs/research_decisions.md``), so we use a dependency-free surrogate that keeps the same
computation and only changes the representation:

* tokens are extracted from the step's action text and observation, lower-cased, with
  identifiers split on ``_``/camelCase and digit runs collapsed;
* token uni- and bi-grams are hashed into a fixed 512-dimensional space and L2-normalised
  (a hashing bag-of-words embedding);
* the resulting vectors feed exactly the same rolling-diversity statistics
  (``sem_diversity``, ``sem_nearest_sim``, ``sem_centroid_dist``, ``sem_novelty_rate``).

The surrogate is weaker than a sentence encoder at paraphrase invariance, so the semantic
baseline reported in the paper is a *strong* version of itself only in the sense that it is
tuned the same way as the other monitors; this limitation is stated explicitly.

Usage: python scripts/embed_semantics.py --corpus tb2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402

import paths  # noqa: E402

DIM = 512
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\sA-Za-z0-9_]")


def tokenize(text: str) -> List[str]:
    out: List[str] = []
    for raw in TOKEN_RE.findall(text):
        if raw.isdigit():
            out.append("<num>")
            continue
        tok = raw.lower()
        # split snake_case and camelCase into subtokens
        parts = re.split(r"_+", tok)
        sub: List[str] = []
        for p in parts:
            sub.extend(re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", p) or [p])
        for s in sub:
            if not s:
                continue
            if s.isdigit():
                s = "<num>"
            if len(s) > 1:
                out.append(s)
    return out


def step_vector(step: Dict, dim: int = DIM) -> np.ndarray:
    acts = " ; ".join(f"{a['name']} {a['arg']}" for a in step.get("actions") or [])
    obs = (step.get("obs") or "")[:1500]
    say = (step.get("text") or "")[:300]
    toks = tokenize(acts) * 2 + tokenize(say) + tokenize(obs)
    grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    v = np.zeros(dim, dtype=np.float32)
    for g in grams:
        h = hash(g) % dim
        v[h] += 1.0
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--processed", default=None)
    ap.add_argument("--dim", type=int, default=DIM)
    args = ap.parse_args()
    proc = args.processed or os.path.join(paths.PROCESSED, args.corpus)
    src = os.path.join(proc, "sample_trajectories.jsonl")
    trajs = [json.loads(l) for l in open(src, encoding="utf-8")]

    t0 = time.time()
    vecs: List[np.ndarray] = []
    offsets: List[int] = []
    for tr in trajs:
        offsets.append(len(vecs))
        vecs.extend(step_vector(s, args.dim) for s in tr["steps"])
    E = np.vstack(vecs).astype(np.float32)
    out = os.path.join(proc, "step_embeddings.npz")
    np.savez_compressed(out, embeddings=E, offsets=np.asarray(offsets, dtype=np.int64),
                        traj_ids=np.asarray([t["traj_id"] for t in trajs]),
                        model=np.asarray(["hashing-bow-1to2gram-512"]))
    with open(os.path.join(proc, "embeddings_config.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "representation": "hashing bag-of-words (uni+bi-grams) over action+message+observation tokens",
            "dim": args.dim, "n_traj": len(trajs), "n_steps": int(E.shape[0]),
            "why_not_pretrained": ("huggingface.co was unreachable from the execution environment "
                                   "(connection timeout), so no sentence encoder could be downloaded; "
                                   "the rolling-diversity statistics are unchanged"),
            "seconds": time.time() - t0, "built_at": time.strftime("%Y-%m-%d %H:%M:%S")}, fh, indent=2)
    print(f"wrote {out}: {E.shape} in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
