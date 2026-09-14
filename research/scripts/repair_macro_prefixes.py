"""Repair the macro mangling the prefix-rewriter introduced, and verify no macro is undefined.

`fix_macro_prefixes.py` strips leading "pp"/"p" from macro references. For names that legitimately
begin with "p" -- pair*, probe*, pvariance* -- that turned \\ppairX into \\airX, destroying the
reference.

Fix: restore the correct p-prefixed form for any reference that is undefined as written but whose
p-prefixed form exists in generated_tb2.tex. Applied by direct comparison against the generated
macro list rather than by pattern, so it cannot over-rewrite again.
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(os.path.dirname(ROOT), "research", "archive", "paper_v1")
FILES = ("main.tex", "abstract.tex", "sections_intro.tex", "sections_related.tex",
         "sections_definition.tex", "sections_method.tex", "sections_setup.tex",
         "sections_results.tex", "sections_discussion.tex")

gen = open(os.path.join(PAPER, "generated_tb2.tex"), encoding="utf-8").read()
have = set(re.findall(r"\\newcommand\{\\(\w+)\}", gen))
print(f"generated macros: {len(have)}")

# LaTeX/amsmath commands and ordinary words that must not be treated as macros
IGNORE = {"begin", "end", "text", "emph", "textbf", "textit", "texttt", "code", "path",
          "section", "subsection", "paragraph", "label", "ref", "cite", "item", "centering",
          "caption", "includegraphics", "linewidth", "toprule", "midrule", "bottomrule",
          "Delta", "sigma", "mu", "alpha", "times", "approx", "pm", "leq", "geq", "in", "to",
          "and", "or", "quad", "qquad", "em", "en", "hline", "small", "footnotesize",
          "leftmargin", "itemsep", "topsep", "nolinkurl", "graphicspath", "documentclass",
          "usepackage", "newcommand", "renewcommand", "input", "pagestyle", "hspace", "vspace",
          "rule", "raisebox", "phantom", "resizebox", "put", "makebox", "par", "noindent",
          "tightlist", "normalsize", "large", "Large", "LARGE", "huge", "smallskip",
          "medskip", "bigskip", "appendix", "abstract", "keywords", "tabular", "array",
          "tabularx", "booktabs", "float", "captionof"}

fixed_total = 0
for fn in FILES:
    p = os.path.join(PAPER, fn)
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8").read()
    used = set(re.findall(r"\\([A-Za-z]+)", t))
    broken = [u for u in used
              if u not in have and u not in IGNORE and ("p" + u) in have]
    if not broken:
        continue
    for u in broken:
        t = re.sub(r"\\" + re.escape(u) + r"(?![A-Za-z])", "\\\\p" + u, t)
    open(p, "w", encoding="utf-8").write(t)
    fixed_total += len(broken)
    print(f"  {fn}: restored {sorted(broken)}")
print(f"total restored: {fixed_total}")

# report anything still undefined so nothing is left broken
still = []
for fn in FILES:
    p = os.path.join(PAPER, fn)
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8").read()
    for u in sorted(set(re.findall(r"\\([A-Za-z]+)", t))):
        if u not in have and u not in IGNORE and ("p" + u) not in have:
            still.append((fn, u))
print(f"still undefined: {len(still)}")
for fn, u in still[:20]:
    print(f"   {fn}: \\{u}")
