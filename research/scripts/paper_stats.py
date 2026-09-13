"""Summarise the compiled paper's structure: pages per section and total length.

Usage: python scripts/paper_stats.py ../paper/main.aux
"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
aux = open(sys.argv[1] if len(sys.argv) > 1 else "../paper/main.aux", encoding="utf-8",
           errors="ignore").read()
secs = re.findall(r"\\newlabel\{(sec:[^}]+)\}\{\{([^}]*)\}\{(\d+)\}", aux)
tabs = re.findall(r"\\newlabel\{(tab:[^}]+)\}\{\{([^}]*)\}\{(\d+)\}", aux)
figs = re.findall(r"\\newlabel\{(fig:[^}]+)\}\{\{([^}]*)\}\{(\d+)\}", aux)
print("sections and the page they start on:")
for name, title, page in sorted(secs, key=lambda t: int(t[2])):
    print(f"  p{page:>3}  {title}")
print(f"\ntables: {len(tabs)} -> " + ", ".join(f"{t[0]} p{t[2]}" for t in sorted(tabs, key=lambda x: int(x[2]))))
print(f"figures: {len(figs)} -> " + ", ".join(f"{f[0]} p{f[2]}" for f in sorted(figs, key=lambda x: int(x[2]))))
