"""Try alternative sources for word vectors, with short timeouts.

GloVe is a nice-to-have: the sentence encoder can already score relevance by embedding the task
statement and each discovered entity into the same space.  Word vectors would only help where a
discovery is a bare symbol with no context.  So try a few sources briefly and move on.
"""
from __future__ import annotations

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
CACHE = os.path.abspath("data/raw/models")
os.environ.setdefault("HF_HOME", CACHE)

CANDIDATES = [
    ("glove-wiki-gigaword-100", "gensim-data"),
    ("word2vec-google-news-300", "gensim-data"),
    ("fasttext-wiki-news-subwords-300", "gensim-data"),
]


def try_gensim() -> bool:
    try:
        import gensim.downloader as api
    except Exception as exc:
        print(f"  gensim unavailable: {exc}")
        return False
    for name, _ in CANDIDATES:
        try:
            t0 = time.time()
            print(f"  trying gensim-data {name} ...", flush=True)
            path = api.load(name, return_path=True)
            print(f"    OK {path} in {time.time()-t0:.0f}s ({os.path.getsize(path)/1e6:.0f} MB)")
            return True
        except Exception as exc:
            print(f"    failed: {type(exc).__name__}: {str(exc)[:100]}")
    return False


def try_hf_repos() -> bool:
    from huggingface_hub import hf_hub_download
    cands = [
        ("KandinskyVasya/glove.6B.100d", "glove.6B.100d.txt"),
        ("commoncrawl/glove.6B.100d", "glove.6B.100d.txt"),
    ]
    for repo, fn in cands:
        try:
            print(f"  trying HF {repo} ...", flush=True)
            p = hf_hub_download(repo_id=repo, filename=fn, cache_dir=CACHE, local_dir=CACHE)
            print(f"    OK {p} ({os.path.getsize(p)/1e6:.0f} MB)")
            return True
        except Exception as exc:
            print(f"    failed: {type(exc).__name__}: {str(exc)[:90]}")
    return False


def main() -> None:
    print("word-vector fallback hunt")
    if try_gensim():
        print("RESULT: word vectors secured via gensim-data")
        return
    if try_hf_repos():
        print("RESULT: word vectors secured via HF")
        return
    print("RESULT: no word vectors. The sentence encoder covers relevance; proceed without.")


if __name__ == "__main__":
    main()
