import json, sys
p = sys.argv[1] if len(sys.argv) > 1 else "results/live/smoke_episodes.jsonl"
recs = [json.loads(l) for l in open(p, encoding="utf-8")]
for r in recs:
    print("=" * 84)
    print(f"{r['arm']:8s} success={r['success']} turns={r['n_turns']} edits={r['edits']} "
          f"tests={r['test_calls']} gold={r['reached_gold']} route_fail={r.get('route_failures')}")
    for t in r["transcript"][:7]:
        arg = str(t.get("arg", ""))[:38]
        obs = str(t.get("obs", "")).replace("\n", " ")[:88]
        print(f"   t{t['turn']:<3} {t['cmd']:6s} {arg:38s} -> {obs}")
