"""Secure every network-dependent asset now, into a local cache, while access holds.

Access to huggingface.co works but the CDN host and API keys do not, and the user warned this may
not persist.  So this script downloads everything the rebuild needs and verifies it loads from
disk, with retries.  Afterwards the whole pipeline must run offline.

Assets:
  1. a real sentence encoder  (semantic channel: "is behaviour still moving?")
  2. GloVe vectors            (semantic relevance: "is this discovery about the task?")
  3. annotated cross-corpus data, if a usable source exists

Usage: python scripts/secure_assets.py [--skip-data]
"""
from __future__ import annotations

import os
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8")

CACHE = os.path.abspath("data/raw/models")
os.makedirs(CACHE, exist_ok=True)
os.environ.setdefault("HF_HOME", CACHE)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", CACHE)
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

ENCODER = "sentence-transformers/all-MiniLM-L6-v2"
GLOVE_REPO = "stanfordnlp/glove"
GLOVE_FILE = "glove.6B.100d.txt"


def retry(fn, tries=4, wait=5.0, label=""):
    for i in range(1, tries + 1):
        try:
            return fn()
        except Exception as exc:
            print(f"    attempt {i}/{tries} failed: {type(exc).__name__}: {str(exc)[:120]}")
            if i == tries:
                raise
            time.sleep(wait * i)


def get_encoder() -> None:
    print(f"\n[1/3] sentence encoder {ENCODER}")
    from sentence_transformers import SentenceTransformer

    def load():
        return SentenceTransformer(ENCODER, cache_folder=CACHE, device="cpu")

    model = retry(load, label="encoder")
    v = model.encode(["rm -rf build", "delete the build directory"], normalize_embeddings=True)
    import numpy as np
    cos = float(np.dot(v[0], v[1]))
    print(f"    loaded; dim={v.shape[1]}; cos(paraphrase)={cos:.3f}  (should be high, ~0.6+)")
    # a sanity contrast: paraphrases should be closer than unrelated text
    v2 = model.encode(["the test suite now passes", "the parser is still crashing"],
                      normalize_embeddings=True)
    cos2 = float(np.dot(v2[0], v2[1]))
    print(f"    cos(opposite meaning)={cos2:.3f}  (should be lower than the paraphrase)")
    assert cos > cos2, "encoder does not distinguish meaning"
    print("    encoder verified")


def get_glove() -> None:
    print(f"\n[2/3] GloVe vectors {GLOVE_REPO}/{GLOVE_FILE}")
    dest = os.path.join(CACHE, GLOVE_FILE)
    if os.path.exists(dest) and os.path.getsize(dest) > 50_000_000:
        print(f"    already present: {os.path.getsize(dest)/1e6:.0f} MB")
        return
    from huggingface_hub import hf_hub_download

    def dl():
        return hf_hub_download(repo_id=GLOVE_REPO, filename=GLOVE_FILE,
                               repo_type="dataset", cache_dir=CACHE, local_dir=CACHE)

    path = retry(dl, label="glove")
    size = os.path.getsize(path)
    print(f"    downloaded to {path} ({size/1e6:.0f} MB)")
    # verify it parses and that semantic similarity actually works
    words = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip().split(" ")
            if len(parts) != 101:
                continue
            words[parts[0]] = parts[1:]
            if len(words) >= 50000:
                break
    print(f"    parsed {len(words)} vectors, dim {len(next(iter(words.values())))}")
    import numpy as np

    def vec(w):
        return np.array([float(x) for x in words[w]]) if w in words else None

    for a, b, c in (("server", "flask", "banana"), ("test", "pytest", "volcano"),
                    ("build", "compile", "symphony")):
        va, vb, vc = vec(a), vec(b), vec(c)
        if va is None or vb is None or vc is None:
            continue

        def cos(x, y):
            return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))

        near, far = cos(va, vb), cos(va, vc)
        flag = "ok" if near > far else "WEAK"
        print(f"    cos({a},{b})={near:+.2f} vs cos({a},{c})={far:+.2f}  {flag}")


def main() -> None:
    ok = {}
    for name, fn in (("encoder", get_encoder), ("glove", get_glove)):
        try:
            fn()
            ok[name] = True
        except Exception:
            ok[name] = False
            print(f"    FAILED: {name}")
            traceback.print_exc(limit=2)
    print("\n=== asset status ===")
    for k, v in ok.items():
        print(f"  {k:10} {'secured' if v else 'MISSING'}")
    print(f"cache: {CACHE}")
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(CACHE) for f in fs)
    print(f"cache size: {total/1e6:.0f} MB")


if __name__ == "__main__":
    main()
