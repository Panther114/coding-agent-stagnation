"""Add the \\pp prefix to every generated-macro reference in the paper text files."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
gen = open(os.path.join(ROOT, "paper", "generated_tb2.tex"), encoding="utf-8").read()
names = sorted({m.group(1) for m in re.finditer(r"\\newcommand\{\\(\w+)\}", gen)}, key=len, reverse=True)
print(f"generated macros: {len(names)}")
pat = re.compile(r"\\(?!ppx)(?:" + "|".join(names) + r")\b")
total = 0
for f in ("main.tex", "abstract.tex", "sections_intro.tex", "sections_related.tex",
          "sections_definition.tex", "sections_method.tex", "sections_setup.tex",
          "sections_results.tex", "sections_discussion.tex"):
    p = os.path.join(ROOT, "paper", f)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8").read()
    # first unwrap an earlier, wrong prefix if it is present, then apply the current one
    s = s.replace("\\ppx", "\x00").replace("\\pp", "\\").replace("\x00", "\\ppx")
    s2, n = pat.subn(lambda m: "\\ppx" + m.group(0)[1:], s)
    if n:
        open(p, "w", encoding="utf-8").write(s2)
        total += n
        print(f"  {f}: {n}")
print(f"total references prefixed: {total}")
