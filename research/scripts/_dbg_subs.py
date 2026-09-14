import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
s = open("../archive/paper_v1/sections_results.tex", encoding="utf-8").read()
print("length:", len(s))
for m in re.finditer(r"\\subsection\{([^}]*)\}", s):
    print(m.start(), m.group(1))
