import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
cands = [
    os.path.expanduser("~/.cache/huggingface"),
    os.path.expanduser("~/.cache/torch"),
    os.path.expanduser("~/.cache/huggingface/hub"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "huggingface"),
    os.path.join(os.environ.get("USERPROFILE", ""), ".cache", "huggingface"),
]
print("huggingface caches:")
for c in cands:
    if c and os.path.isdir(c):
        try:
            entries = os.listdir(c)
        except Exception:
            entries = ["<unreadable>"]
        print(f"  {c}: {len(entries)} entries")
        for e in entries[:8]:
            print(f"      {e}")
    else:
        print(f"  {c}: missing")

# gensim data / any glove or word2vec files anywhere obvious
print("\nsearching for bundled vectors:")
roots = [os.getcwd(), os.path.expanduser("~"), os.path.join(os.environ.get("LOCALAPPDATA", ""))]
hits = []
for r in roots:
    if not r or not os.path.isdir(r):
        continue
    for dirpath, dirnames, filenames in os.walk(r):
        if len(hits) > 20 or dirpath.count(os.sep) - r.count(os.sep) > 4:
            dirnames[:] = []
            continue
        for fn in filenames:
            low = fn.lower()
            if any(k in low for k in ("glove", "word2vec", "fasttext", "model.safetensors",
                                      "pytorch_model.bin", "sentence-transformers")):
                hits.append(os.path.join(dirpath, fn))
for h in hits[:20]:
    print(f"  {h}")
print(f"total vector files found: {len(hits)}")
