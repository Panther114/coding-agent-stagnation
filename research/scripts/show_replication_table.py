"""Print the three-way replication table from the three disjoint step tables."""
import json
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "results" / "rebuild"
SETS = [("frozen  shards 0-3", "wrongness.json"),
        ("heldout A shards 4-7", "wrongness_repl.json"),
        ("heldout B shards 8-11", "wrongness_repl2.json")]

rows = []
for name, f in SETS:
    d = json.loads((RES / f).read_text(encoding="utf-8"))["corpora"]["nebius"]
    rows.append({
        "name": name,
        "self_s": d["pooled_on_target_self"]["solved"],
        "self_f": d["pooled_on_target_self"]["failed"],
        "gold_s": d["pooled_on_target_gold"]["solved"],
        "gold_f": d["pooled_on_target_gold"]["failed"],
        "touch_s": d["pooled_ever_touched_gold"]["solved"],
        "touch_f": d["pooled_ever_touched_gold"]["failed"],
        "p": d["reversal_on_target_gold"].get("p_wilcoxon"),
        "ni": d["reversal_on_target_gold"].get("n_instances"),
        "wf": d["failure_decomposition"]["frac_wrong_fix"],
        "n": d["failure_decomposition"]["n_failed_runs_with_gold"],
    })

hdr = (f"{'set':22s} {'selfS':>6} {'selfF':>6} | {'goldS':>6} {'goldF':>6} | "
       f"{'touchS':>7} {'touchF':>7} | {'withinP':>9} {'inst':>5} | {'wrongfix':>9} {'n':>8}")
print(hdr)
print("-" * len(hdr))
for r in rows:
    print(f"{r['name']:22s} {r['self_s']:6.3f} {r['self_f']:6.3f} | {r['gold_s']:6.3f} "
          f"{r['gold_f']:6.3f} | {r['touch_s']:7.3f} {r['touch_f']:7.3f} | {r['p']:9.1e} "
          f"{r['ni']:5d} | {100 * r['wf']:8.1f}% {r['n']:8,d}")

gaps = [r["gold_s"] - r["gold_f"] for r in rows]
wfs = [100 * r["wf"] for r in rows]
print()
print(f"gold gap (solved-failed): " + " / ".join(f"{g:+.3f}" for g in gaps))
print(f"wrong-fix share          : " + " / ".join(f"{w:.1f}%" for w in wfs)
      + f"   (range {max(wfs) - min(wfs):.1f} points)")
print(f"total runs, 12/12 shards : {26679 + 26680 + 26676:,}")
