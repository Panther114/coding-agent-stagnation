import json, sys
p = sys.argv[1] if len(sys.argv) > 1 else "results/rebuild/route_modes.json"
d = json.load(open(p, encoding="utf-8"))
print("top-level keys:", list(d.keys()))
for k, v in d.items():
    if isinstance(v, (int, float, str)):
        print(f"  {k} = {v}")
    elif isinstance(v, list):
        print(f"  {k}: list[{len(v)}]")
    elif isinstance(v, dict):
        print(f"  {k}: dict keys={list(v.keys())[:14]}")
print()
for k in ("verdict", "labels", "base_rates", "calibration", "decision_curve", "summary"):
    if k in d:
        print("=" * 90)
        print(k.upper())
        s = json.dumps(d[k], indent=1, ensure_ascii=False)
        print(s[:2600])
