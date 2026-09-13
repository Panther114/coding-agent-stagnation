import json
d = json.load(open("results/rebuild/route_modes.json", encoding="utf-8"))
v = d["verdict"]

print("=== published bar comparison ===")
print(json.dumps(v.get("published_bar"), indent=1, ensure_ascii=False)[:2000])

print()
print("=== y_mode: predict LOST vs WRONG-FIX among failed runs ===")
ym = v["per_task"].get("y_mode", {})
for frac, tv in ym.items():
    print(f"\n-- prefix fraction {frac}  n={tv.get('n')}  base_rate(wrong_fix)={tv.get('base_rate'):.3f}")
    auc = tv.get("auc", {})
    for k in sorted(auc, key=lambda k: -auc[k]):
        print(f"     {k:22s} AUC={auc[k]:.4f}")
    r5 = tv.get("recall_at_5pct", {})
    r10 = tv.get("recall_at_10pct", {})
    if r5:
        print("     recall@5% :", {k: round(x, 3) for k, x in sorted(r5.items(), key=lambda kv: -kv[1])[:4]})
    if r10:
        print("     recall@10%:", {k: round(x, 3) for k, x in sorted(r10.items(), key=lambda kv: -kv[1])[:4]})

print()
print("=== y_fail summary (best method vs baselines) ===")
yf = v["per_task"].get("y_fail", {})
for frac, tv in yf.items():
    auc = tv.get("auc", {})
    best = max(auc, key=lambda k: auc[k]) if auc else None
    print(f"  f={frac}: best={best} {auc.get(best, float('nan')):.4f} | "
          f"position={auc.get('position', float('nan')):.4f} | "
          f"agentstop={auc.get('agentstop_shape', float('nan')):.4f} | "
          f"ngram={auc.get('ngram_loop', float('nan')):.4f}")

print()
print("=== decision curve (gated) ===")
print(json.dumps(d.get("decision_curve", {}).get("gated_all_runs"), indent=1, ensure_ascii=False)[:1400])
print()
print("=== integrity checks ===")
print(json.dumps(d.get("integrity_checks"), indent=1, ensure_ascii=False)[:1000])
print()
print("=== coverage ===")
print(json.dumps(d.get("coverage"), indent=1, ensure_ascii=False)[:800])
