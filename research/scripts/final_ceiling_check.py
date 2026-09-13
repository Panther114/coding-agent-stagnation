"""Final verification of the ceiling claim and the whole package."""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import pypdf

print("=== ceiling claim present in PDF ===")
r = pypdf.PdfReader("../paper/main.pdf")
flat = re.sub(r"\s+", "", "".join((p.extract_text() or "") for p in r.pages)).lower()
for c in ("ceiling,notatuningartifact", "all sixsignalfamiliesjointly",
          "trajectory-clusteredinterval", "task-clusteredbootstrap"):
    print(f"  {c:38} {'FOUND' if c in flat else 'MISSING'}")

print("\n=== the result, from the frozen artifact ===")
c = json.load(open("results/final/v2/ceiling_test.json", encoding="utf-8"))
j = json.load(open("results/final/v2/joint_model_test.json", encoding="utf-8"))
print(f"  baseline             {c['baseline_auc']:.3f}  ({c['baseline_monitor']})")
print(f"  baseline bootstrap   [{c['baseline_ci'][0]:.3f}, {c['baseline_ci'][1]:.3f}]")
print(f"  joint model          {j['joint_auc']:.3f}  diff {j['paired_diff']:+.3f} "
      f"[{j['ci'][0]:+.3f}, {j['ci'][1]:+.3f}] p={j['p']:.3f}")
print(f"  windows / tasks      {j['n_windows']} / {c['n_tasks']}")
print(f"  frozen monitors      {c['frozen_monitors']}")

print("\n=== all five attempts, in one place ===")
att = {
    "joint over six families": j["joint_auc"],
    "v1 best single family (BoW)": c["baseline_auc"],
}
for f, lab in (("embedding_upgrade_test.json", "real encoder (MiniLM)"),
               ("multiscale_test.json", "multi-scale w10+w20"),
               ("semantic_relevance_test.json", "semantic relevance")):
    p = os.path.join("results/final/v2", f)
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        if "joint_auc" in d:
            continue
        if f == "multiscale_test.json":
            att[lab] = d["auc"].get("w=10+w=20")
        elif f == "embedding_upgrade_test.json":
            att[lab] = d["auc"].get("v2_semantic_MiniLM-L6")
        else:
            att[lab] = d["auc"].get("semantic (MiniLM relevance)")
for k, v in sorted(att.items(), key=lambda kv: -(kv[1] or 0)):
    if v is None:
        continue
    print(f"  {k:32} {v:.3f}  ({v - c['baseline_auc']:+.3f})")
vals = [v for v in att.values() if v is not None]
print(f"\n  attempts: {len(vals)}; max gain over baseline: {max(vals) - c['baseline_auc']:+.3f}")
