"""Fetch the cross-scaffold corpora into ``data/raw/xscaffold/<key>/``.

Only the parquet shards are pulled.  Sizes are printed first so the run can be
stopped before an unintended multi-gigabyte download; pass ``--max-shards`` to
take only a prefix of a sharded corpus.

    python scripts/xscaffold_download.py --corpus swegym
    python scripts/xscaffold_download.py --max-gb 3.0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "xscaffold"
OUT = ROOT / "results" / "rebuild"

CORPORA = {
    "nebius_openhands": "nebius/SWE-rebench-openhands-trajectories",
    "swegym": "SWE-Gym/OpenHands-Sampled-Trajectories",
    "pi": "whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces",
    "smithmarines": "Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k",
    "thoughtworks": "thoughtworks/agentic-coding-trajectories",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--max-shards", type=int, default=None)
    ap.add_argument("--max-gb", type=float, default=4.0,
                    help="stop before the running total of *this* invocation exceeds this")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()
    keys = [args.corpus] if args.corpus else list(CORPORA)
    ledger = []
    total = 0.0
    for key in keys:
        repo = CORPORA[key]
        info = api.dataset_info(repo, files_metadata=True)
        files = sorted((s.rfilename, getattr(s, "size", 0) or 0) for s in (info.siblings or [])
                       if s.rfilename.endswith(".parquet"))
        if args.max_shards:
            files = files[: args.max_shards]
        print(f"\n{key}: {repo} — {len(files)} shards, "
              f"{sum(s for _n, s in files)/1e9:.2f} GB")
        dest = CACHE / key
        dest.mkdir(parents=True, exist_ok=True)
        for name, size in files:
            if total + size / 1e9 > args.max_gb + 1e-9:
                print(f"  stop: budget {args.max_gb:.2f} GB reached ({total:.2f} GB)")
                break
            try:
                p = hf_hub_download(repo_id=repo, filename=name, repo_type="dataset",
                                    local_dir=str(dest))
                total += size / 1e9
                print(f"  ok  {name}  ({size/1e6:.1f} MB, running {total:.2f} GB)")
                ledger.append({"corpus": key, "repo": repo, "file": name,
                               "bytes": size, "local": str(p)})
            except Exception as e:
                print(f"  FAIL {name}: {type(e).__name__}: {str(e)[:200]}")
                ledger.append({"corpus": key, "repo": repo, "file": name,
                               "bytes": size, "error": f"{type(e).__name__}: {str(e)[:200]}"})
    (OUT / "xscaffold_download_ledger.json").write_text(
        json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"\nfetched {total:.2f} GB")


if __name__ == "__main__":
    main()
