"""Diagnose the live episodes: how many turns are lost to unparseable replies, and why runs fail.

This exists because a harness that silently discards a large share of an agent's turns measures
protocol compliance rather than debugging ability, and would invalidate the experiment.
"""
import json
import sys
from collections import Counter

p = sys.argv[1] if len(sys.argv) > 1 else "results/live/pilot_episodes.jsonl"
max_turns = int(sys.argv[2]) if len(sys.argv) > 2 else 12
recs = [json.loads(l) for l in open(p, encoding="utf-8")]

tot = unparsed = 0
ran_out = 0
raw_cmds = Counter()
for r in recs:
    c = sum(1 for t in r.get("transcript", []) if t["cmd"] == "")
    n = len(r.get("transcript", []))
    tot += n
    unparsed += c
    if r.get("n_turns", 0) >= max_turns:
        ran_out += 1
    for t in r.get("transcript", []):
        raw_cmds[t["cmd"] or "<unparsed>"] += 1
    print(f"{str(r.get('task_id'))[:40]:40s} {str(r.get('arm')):8s} "
          f"turns={r.get('n_turns') if r.get('n_turns') is not None else '-':>2} "
          f"entries={n:2d} unparsed={c:2d} tamper={r.get('test_files_removed', 0)} "
          f"success={r.get('success')} "
          f"ran_out={r.get('n_turns', 0) is not None and r.get('n_turns', 0) >= max_turns}")

print()
print(f"episodes: {len(recs)}  ran out of turns: {ran_out}")
print(f"unparsed turns: {unparsed}/{tot} = {unparsed / max(tot, 1):.1%}")
print("command mix:", dict(raw_cmds))
print()
print("=== up to 6 unparsed replies ===")
shown = 0
for r in recs:
    for t in r.get("transcript", []):
        if t["cmd"] == "" and shown < 6:
            print(f"  [{r['arm']}] {str(t.get('reply'))[:220]!r}")
            shown += 1
