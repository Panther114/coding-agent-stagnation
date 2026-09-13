"""Probe the candidate cross-scaffold corpora *without* downloading them.

For each candidate dataset this reports, mechanically:

* the parquet shard inventory and byte sizes (from the HF API),
* the schema of the first shard (read over HTTP range requests, so a 1.9 GB
  file costs a few hundred kilobytes),
* the literal ``[File: ... (N lines total)]`` footer, or an equivalent
  structural marker naming an edited file with a measurable size,
* a sample of the raw observation text around that footer.

Nothing is written outside ``data/raw/xscaffold/`` and ``results/rebuild/xscaffold_probe.json``.
No existing file is modified.

    python scripts/xscaffold_probe.py
    python scripts/xscaffold_probe.py --corpus swegym
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"
CACHE = ROOT / "data" / "raw" / "xscaffold"

# --------------------------------------------------------------------------------------
# The corpora under test, in the priority order the study assigned.
# --------------------------------------------------------------------------------------

CORPORA: Dict[str, Dict[str, str]] = {
    "nebius_openhands": {
        "repo": "nebius/SWE-rebench-openhands-trajectories",
        "scaffold": "OpenHands (SWE-rebench, 67k)",
    },
    "swegym": {
        "repo": "SWE-Gym/OpenHands-Sampled-Trajectories",
        "scaffold": "OpenHands (SWE-Gym, 6k)",
    },
    "pi": {
        "repo": "whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces",
        "scaffold": "PI agent (swe-rebench-v2)",
    },
    "smithmarines": {
        "repo": "Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k",
        "scaffold": "mini-swe-agent-plus (bash-only)",
    },
    "thoughtworks": {
        "repo": "thoughtworks/agentic-coding-trajectories",
        "scaffold": "multi-framework (agent_framework column)",
    },
}

# --------------------------------------------------------------------------------------
# Structural markers: the SWE-agent footer, and everything else that names a file with
# a measurable size.  Each entry is (name, regex, description).
# --------------------------------------------------------------------------------------

MARKERS: List[Dict[str, str]] = [
    {
        "name": "swe_agent_footer",
        "re": r"\[File:\s*[^\]]*?\((\d+) lines? total\)\]",
        "desc": "SWE-agent editor footer: names the file and its total line count",
    },
    {
        "name": "openhands_editor_block",
        "re": r"\[File:\s*[^\]\n]{1,300}\]",
        "desc": "any [File: ...] header, with or without a line count",
    },
    {
        "name": "openhands_file_line",
        "re": r"^\s*\d+\|.*$",
        "desc": "OpenHands numbered read with a pipe gutter ('12|code')",
    },
    {
        "name": "colon_numbered_lines",
        "re": r"^\s*\d+[:|]\s*\S",
        "desc": "numbered source lines (SWE-agent '12:code' or OpenHands '12|code')",
    },
    {
        "name": "bash_output_marker",
        "re": r"\[(?:File|Output|Result):",
        "desc": "bracketed tool-result header",
    },
    {
        "name": "ellipsis_truncation",
        "re": r"<\.\.\. \d+ lines? (?:hidden|omitted) \.\.\.>|\.\.\. \(\d+ more lines?\)",
        "desc": "explicit truncation notice that states how many lines were elided",
    },
]


def _compile(mk: Dict[str, str]):
    return re.compile(mk["re"], re.M)


def flatten_strings(obj: Any, prefix: str = "", depth: int = 0, max_depth: int = 6) -> Dict[str, str]:
    """Every string leaf of a nested JSON structure, keyed by its path.

    The five corpora store the trajectory under different column names and different
    nesting, so the probe does not assume a schema: it walks whatever is there.
    """
    out: Dict[str, str] = {}
    if depth > max_depth:
        return out
    if isinstance(obj, str):
        out[prefix or "$"] = obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten_strings(v, f"{prefix}.{k}" if prefix else str(k), depth + 1, max_depth))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.update(flatten_strings(v, f"{prefix}[{i}]", depth + 1, max_depth))
    return out


def open_remote(path_or_url: str):
    """A seekable file object over HTTP range requests (no full download)."""
    import fsspec

    fs = fsspec.filesystem("http", block_size=2 * 1024 * 1024)
    return fs.open(path_or_url)


def sample_shard(url: str, n_rows: int = 40):
    """Read the first ``n_rows`` rows of a remote parquet with range requests."""
    import pyarrow.parquet as pq

    with open_remote(url) as fh:
        pf = pq.ParquetFile(fh)
        meta = {
            "num_rows": pf.metadata.num_rows,
            "num_row_groups": pf.metadata.num_row_groups,
            "num_columns": pf.metadata.num_columns,
        }
        schema = [(fld.name, str(fld.type)) for fld in pf.schema_arrow]
        # take rows from the first row group only
        batch = next(pf.iter_batches(batch_size=n_rows))
        rows = batch.to_pylist()
    return meta, schema, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None, help="probe only this corpus key")
    ap.add_argument("--rows", type=int, default=40)
    ap.add_argument("--limit-shards", type=int, default=1)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    from huggingface_hub import HfApi

    api = HfApi()
    report: Dict[str, Any] = {}

    keys = [args.corpus] if args.corpus else list(CORPORA)
    for key in keys:
        spec = CORPORA[key]
        repo = spec["repo"]
        print(f"\n{'='*78}\n{key}  ->  {repo}\n{'='*78}")
        entry: Dict[str, Any] = {"repo": repo, "scaffold": spec["scaffold"]}
        try:
            info = api.dataset_info(repo, files_metadata=True)
        except Exception as e:
            print(f"  API FAILED: {type(e).__name__}: {str(e)[:200]}")
            entry["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            report[key] = entry
            continue

        sibs = [(s.rfilename, getattr(s, "size", None)) for s in (info.siblings or [])]
        parqs = [(n, sz) for n, sz in sibs if n.endswith(".parquet")]
        parqs.sort()
        entry["n_files"] = len(sibs)
        entry["n_parquet"] = len(parqs)
        entry["parquet_bytes_total"] = sum(sz or 0 for _n, sz in parqs)
        entry["parquet_files"] = [{"name": n, "bytes": sz} for n, sz in parqs[:80]]
        cd = info.card_data
        try:
            cd = dict(cd) if cd is not None else {}
        except Exception:
            cd = {}
        entry["card_data"] = {
            k: (v if isinstance(v, (str, int, float, bool, list, type(None))) else str(v))
            for k, v in cd.items()
        }
        print(f"  {len(parqs)} parquet files, "
              f"{entry['parquet_bytes_total']/1e9:.2f} GB total")
        for n, sz in parqs[:6]:
            print(f"    {n}  {(sz or 0)/1e6:8.1f} MB")
        if len(parqs) > 6:
            print(f"    ... {len(parqs)-6} more")

        if not parqs:
            print("  no parquet; cannot range-read")
            report[key] = entry
            continue

        # ---- schema + rows, over range requests only ------------------------------
        try:
            url = f"https://huggingface.co/datasets/{repo}/resolve/main/{parqs[0][0]}"
            meta, schema, rows = sample_shard(url, args.rows)
        except Exception as e:
            print(f"  RANGE READ FAILED: {type(e).__name__}: {str(e)[:200]}")
            entry["error"] = f"range-read: {type(e).__name__}: {str(e)[:300]}"
            report[key] = entry
            continue
        entry["first_shard"] = {"name": parqs[0][0], "meta": meta,
                                "schema": [{"name": n, "type": t} for n, t in schema]}
        print(f"  first shard {parqs[0][0]}: {meta['num_rows']:,} rows, "
              f"{meta['num_row_groups']} row groups")
        print("  schema:")
        for n, t in schema:
            print(f"    {n:<28} {t[:90]}")

        # ---- marker scan over every string leaf of every sampled row --------------
        leaves: List[tuple] = []       # (row_idx, path, text)
        for i, r in enumerate(rows):
            for p, s in flatten_strings(r).items():
                leaves.append((i, p, s))
        entry["n_string_leaves_sampled"] = len(leaves)
        entry["sample_row_keys"] = sorted(rows[0].keys()) if rows else []

        marker_stats: Dict[str, Any] = {}
        examples: Dict[str, Any] = {}
        for mk in MARKERS:
            rx = _compile(mk)
            hits_total = 0
            leaves_with = 0
            first = None
            for i, p, s in leaves:
                ms = list(rx.finditer(s))
                if not ms:
                    continue
                leaves_with += 1
                hits_total += len(ms)
                if first is None:
                    m = ms[0]
                    lo = max(0, m.start() - 220)
                    hi = min(len(s), m.end() + 220)
                    first = {
                        "row": i, "path": p, "match": m.group(0)[:300],
                        "context": s[lo:hi],
                    }
            marker_stats[mk["name"]] = {
                "desc": mk["desc"],
                "regex": mk["re"],
                "leaf_hits": leaves_with,
                "leaf_rate": round(leaves_with / max(len(leaves), 1), 4),
                "total_matches": hits_total,
            }
            if first:
                examples[mk["name"]] = first
        entry["markers"] = marker_stats
        entry["marker_examples"] = examples
        print("\n  markers over %d string leaves:" % len(leaves))
        for k, v in marker_stats.items():
            flag = "PRESENT " if v["leaf_hits"] else "absent  "
            print(f"    {flag} {k:<26} leaves {v['leaf_hits']:>5}  "
                  f"({v['leaf_rate']:.1%})  matches {v['total_matches']}")
            if k in examples:
                print(f"              literal: {examples[k]['match'][:160]!r}")

        # ---- a compact structural summary of the first row's message container -----
        if rows:
            e_summ: Dict[str, Any] = {}
            for k, v in rows[0].items():
                if isinstance(v, str):
                    e_summ[k] = {"type": "str", "len": len(v), "head": v[:200]}
                elif isinstance(v, (list, tuple)):
                    e_summ[k] = {"type": "list", "len": len(v),
                                 "item0_keys": (sorted(v[0].keys())
                                                if v and isinstance(v[0], dict) else None)}
                elif isinstance(v, dict):
                    e_summ[k] = {"type": "dict", "keys": sorted(v.keys())}
                else:
                    e_summ[k] = {"type": type(v).__name__, "value": v}
            entry["row0_summary"] = e_summ
            print("\n  row 0 columns:")
            for k, v in e_summ.items():
                print(f"    {k:<28} {json.dumps(v, default=str)[:220]}")

        report[key] = entry

    (OUT / "xscaffold_probe.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nwrote {OUT / 'xscaffold_probe.json'}")


if __name__ == "__main__":
    main()
