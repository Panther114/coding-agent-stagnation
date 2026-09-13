import json, sys
p = sys.argv[1] if len(sys.argv) > 1 else "results/live/pilot_episodes.jsonl"
max_turns = int(sys.argv[2]) if len(sys.argv) > 2 else 12
recs = [json.loads(l) for l in open(p, encoding="utf-8")]
for r in recs:
    ran_out = r.get("n_turns", 0) >= max_turns
    print("=" * 92)
    print(f"{r['task_id'][:44]} | arm={r['arm']:8s} success={r.get('success')} "
          f"turns={r.get('n_turns')} edits={r.get('edits')} tests={r.get('test_calls')} "
          f"gold={r.get('reached_gold')} ran_out={ran_out}")
    for w in r.get("writes", []):
        print(f"   WRITE t{w['turn']} {w['path']} {w['bytes']}B fences={w.get('n_fences')}")
    for t in r.get("transcript", []):
        if t["cmd"] in ("test", "done"):
            o = str(t.get("obs_full") or t.get("obs") or "").replace("\n", " ")
            print(f"   {t['cmd'].upper():5s} t{t['turn']}: {o[-150:]}")
        elif t["cmd"] == "":
            print(f"   NOCCMD t{t['turn']}: {str(t.get('reply'))[:110]!r}")
