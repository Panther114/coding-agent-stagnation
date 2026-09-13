"""Diagnose the masked run: 0/48 success with `turns=None` smells like a harness fault, not a result."""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "results" / "live" / "episodes_masked.jsonl"
recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"episodes: {len(recs)}")

errs = collections.Counter()
for r in recs:
    e = str(r.get("error") or "")
    errs[e[:90] or "(no error)"] += 1
print("\nerror counts:")
for k, v in errs.most_common(8):
    print(f"  {v:>3}  {k}")

print("\nfield sample:")
for r in recs[:3]:
    print("  ", {k: r.get(k) for k in ("task_id", "arm", "n_turns", "success",
                                       "reached_gold", "test_files_removed", "n_empty",
                                       "error", "fail_before")})

n_trans = sum(len(r.get("transcript") or []) for r in recs)
print(f"\ntotal transcript entries across all episodes: {n_trans}")

print("\n=== first episode with a transcript ===")
for r in recs:
    tr = r.get("transcript") or []
    if tr:
        print("task:", r.get("task_id"), "turns:", r.get("n_turns"))
        for t in tr[:6]:
            print(f"  t{t.get('turn')} cmd={t.get('cmd')!r} "
                  f"obs={str(t.get('obs'))[:160]!r}")
        break
else:
    print("  NO episode has any transcript -> every episode died before the first tool call")
    print("\n  raw first record:")
    print(json.dumps(recs[0], ensure_ascii=False)[:900])
