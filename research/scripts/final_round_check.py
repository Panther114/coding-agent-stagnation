"""Final consolidated verification for this round."""
from __future__ import annotations

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import pypdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.normpath(os.path.join(ROOT, "..", "paper"))

print("=== 1. THE OBJECTIVE ===")
al = json.load(open(os.path.join(ROOT, "results/final/v2/alarm_artifact.json"), encoding="utf-8"))
nv = json.load(open(os.path.join(ROOT, "results/final/v2/nested_validation.json"), encoding="utf-8"))
det = al["detection_rate"]
fa = al["false_alarm_window_rate"]
print(f"  detector spec      : {al['monitor']}, smooth {al['k_smooth']}, k={al['k_sd']}, "
      f"open {al['open_frac']}")
print(f"  detection          : {det:.3f}  ({al['episodes_detected']}/{al['episodes']}) "
      f"-> {'PASS' if det > 0.50 else 'FAIL'} (>50% required)")
print(f"  false alarm/window : {fa:.3f} -> {'PASS' if fa < 0.20 else 'FAIL'} (<20% required)")
print(f"  nested held-out    : det {nv['detection']:.3f}, FA {nv['fa_window']:.3f} "
      f"-> {'PASS' if nv['detection'] > 0.50 and nv['fa_window'] < 0.20 else 'FAIL'}")
print(f"  median latency     : {al['median_latency_steps']:.0f} steps")
print(f"  OBJECTIVE          : {'MET' if det > 0.50 and fa < 0.20 else 'NOT MET'}")

print("\n=== 2. THE ESSAY ===")
r = pypdf.PdfReader(os.path.join(PAPER, "main.pdf"))
flat = re.sub(r"\s+", "", "".join((p.extract_text() or "") for p in r.pages)).lower()
print(f"  pages              : {len(r.pages)}")
for label, key in (("detector in abstract", "theadetectorremoves"),
                   ("53% detection", "53"),
                   ("17% false alarms", "17"),
                   ("label-free claim", "nousenolabels"),
                   ("limitation stated", "twoepisodesinfivearemissed"),
                   ("episode reframing", "stagnationisanepisode")):
    print(f"  {label:22} {'FOUND' if key in flat else 'MISSING'}")

print("\n=== 3. FIGURES ===")
from PIL import Image
import numpy as np
figdir = os.path.join(PAPER, "figures")
for n in sorted(os.listdir(figdir)):
    if not n.endswith(".png"):
        continue
    im = Image.open(os.path.join(figdir, n)).convert("L")
    a = np.asarray(im, dtype=np.float32) / 255.0
    h, w = a.shape
    asp = w / h
    print(f"  {n:28} {w}x{h}  aspect {asp:.2f}  ink {float((a<0.9).mean()):.3f}")

print("\n=== 4. INTEGRITY ===")
print(f"  gold windows       : {sum(1 for _ in open(os.path.join(ROOT, 'data/annotations/tb2/adjudicated.csv'), encoding='utf-8')) - 1}")
for f in ("stationary_stats.json", "nested_validation.json", "alarm_artifact.json",
          "regime_headline.json", "detector_frontier.json"):
    p = os.path.join(ROOT, "results/final/v2", f)
    print(f"  {f:28} {'present' if os.path.exists(p) else 'MISSING'}")
