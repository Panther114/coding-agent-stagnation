"""Download raw trajectory datasets (parquet) from Hugging Face.

Usage: python download_data.py [--only tb2|nebius]
"""
import argparse
import json
import os
import sys
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

DATASETS = {
    "tb2": {
        "repo": "yoonholee/terminalbench-trajectories",
        "files": ["data/train-00000-of-00002.parquet", "data/train-00001-of-00002.parquet"],
    },
    "nebius": {
        "repo": "nebius/SWE-agent-trajectories",
        "files": [f"data/train-{i:05d}-of-00012.parquet" for i in range(12)],
    },
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def head_size(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
    with urllib.request.urlopen(req, timeout=40) as r:
        return int(r.headers.get("Content-Length", 0)), r.geturl()


def download(url: str, dest: str) -> None:
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as fh:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            got += len(chunk)
            if total:
                pct = 100.0 * got / total
                print(f"\r  {os.path.basename(dest)} {pct:5.1f}% ({got/1e6:.1f}/{total/1e6:.1f} MB)", end="")
    print()
    os.replace(tmp, dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    keys = [args.only] if args.only else list(DATASETS)
    manifest = {}
    for key in keys:
        spec = DATASETS[key]
        outdir = os.path.join(ROOT, "data", "raw", key)
        os.makedirs(outdir, exist_ok=True)
        manifest[key] = {"repo": spec["repo"], "files": []}
        for rel in spec["files"]:
            url = f"https://huggingface.co/datasets/{spec['repo']}/resolve/main/{rel}"
            dest = os.path.join(outdir, os.path.basename(rel))
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                print(f"have {dest} ({os.path.getsize(dest)/1e6:.1f} MB)")
            else:
                print(f"fetch {url}")
                download(url, dest)
            manifest[key]["files"].append(
                {"name": os.path.basename(dest), "bytes": os.path.getsize(dest), "url": url}
            )
    with open(os.path.join(ROOT, "data", "raw", "download_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
