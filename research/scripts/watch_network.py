"""Retry HF downloads in a loop; write a status file each attempt.

The machine went offline on 2026-09-10 and only part of each corpus was fetched:
  tb2     : 1 of 2 shards  (shard 1 absent -> ~half of 52,104 trials missing)
  nebius  : 4 of 12 shards (a 5th is truncated)

If the network returns, this fetches the missing files exactly like
scripts/download_data.py does. Safe to run for hours: it exits only when every
expected file is on disk, and it writes data/raw/network_watch.json on every poll
so any process can see the current state.

Usage:
  python scripts/watch_network.py --interval 120            # poll until complete
  python scripts/watch_network.py --once                    # single probe
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
STATUS = os.path.join(ROOT, "data", "raw", "network_watch.json")

# Endpoints to try, in order.  ``huggingface.co`` is DNS-poisoned on this network and times out,
# but the mirror is reachable and serves the same repositories byte-for-byte.  Probing only the
# canonical host produced a **false negative that cost three days of blocked work**: on
# 2026-09-13 the machine could reach hf-mirror.com (HTTP 200 in ~200 ms) the entire time this
# watcher was reporting ``network=False``.  Always probe the whole list before concluding offline.
ENDPOINTS = [
    ("hf-mirror", "https://hf-mirror.com"),
    ("huggingface", "https://huggingface.co"),
]
REACHABLE: dict[str, bool] = {}


def probe(host: str = None) -> bool:
    """True if ANY configured endpoint answers.  Records per-endpoint results in REACHABLE."""
    for name, base in ENDPOINTS:
        req = urllib.request.Request(base, headers={"User-Agent": UA}, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=10):
                REACHABLE[name] = True
                return True
        except Exception:
            REACHABLE[name] = False
    return False


def dataset_base() -> str:
    """The first reachable endpoint, so downloads go through the mirror rather than dead DNS."""
    for name, base in ENDPOINTS:
        if REACHABLE.get(name):
            return base
    return ENDPOINTS[0][1]


def missing() -> list[tuple[str, str, str]]:
    base = dataset_base()
    todo = []
    for key, spec in DATASETS.items():
        outdir = os.path.join(ROOT, "data", "raw", key)
        for rel in spec["files"]:
            dest = os.path.join(outdir, os.path.basename(rel))
            ok = os.path.exists(dest) and os.path.getsize(dest) > 1_000_000
            if not ok:
                url = f"{base}/datasets/{spec['repo']}/resolve/main/{rel}"
                todo.append((key, url, dest))
    return todo


def download(url: str, dest: str) -> bool:
    tmp = dest + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as r, open(tmp, "wb") as fh:
            total = int(r.headers.get("Content-Length", 0))
            got = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
        if total and got < total * 0.99:
            print(f"  short read {got}/{total} for {dest}", flush=True)
            return False
        # cheap integrity check: parquet magic
        with open(tmp, "rb") as fh:
            head = fh.read(4)
            fh.seek(-4, 2)
            tail = fh.read(4)
        if head != b"PAR1" or tail != b"PAR1":
            print(f"  not a parquet file: {dest}", flush=True)
            return False
        os.replace(tmp, dest)
        print(f"  fetched {dest} ({got / 1e6:.1f} MB)", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  download failed {os.path.basename(dest)}: {e}", flush=True)
        return False


def write_status(net: bool, todo_n: int, note: str) -> None:
    payload = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "network": net,
        "missing_files": todo_n,
        "note": note,
    }
    with open(STATUS, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=120.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    while True:
        todo = missing()
        net = probe()
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] network={net} missing={len(todo)}", flush=True)
        if not todo:
            write_status(net, 0, "complete")
            print("all files present; watcher exiting", flush=True)
            return
        if net:
            for _key, url, dest in todo:
                print(f"  fetching {os.path.basename(dest)}", flush=True)
                download(url, dest)
            todo = missing()
            if not todo:
                write_status(True, 0, "complete")
                return
        write_status(net, len(todo), "waiting" if not net else "partial")
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
