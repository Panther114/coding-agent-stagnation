"""Add remaining prose aliases so every reference in the paper resolves.

Usage: python scripts/add_missing_aliases.py   # prints what is still unresolved
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPER = os.path.join(ROOT, "research", "archive", "paper_v1")
gen = open(os.path.join(PAPER, "generated_tb2.tex"), encoding="utf-8").read()
defined = {m.group(1) for m in re.finditer(r"\\newcommand\{\\(\w+)\}", gen)}
builtin = {"cite", "ref", "label", "begin", "end", "item", "textbf", "emph", "code", "evid",
           "ver", "rep", "nov", "work", "sem", "mon", "section", "subsection", "paragraph",
           "input", "includegraphics", "caption", "toprule", "midrule", "bottomrule",
           "multicolumn", "cmidrule", "textsc", "text", "mathrm", "Delta", "kappa", "times",
           "alpha", "beta", "quad", "vspace", "today", "maketitle", "appendix", "documentclass",
           "usepackage", "title", "author", "date", "bibliographystyle", "bibliography",
           "linewidth", "itemsep", "leftmargin", "topsep", "centering", "small", "tabular",
           "table", "figure", "description", "enumerate", "newcommand", "renewcommand",
           "graphicspath", "captionsetup", "label", "hline", "flushleft", "sffamily", "ttfamily",
           "textwidth", "textheight", "par", "noindent", "vskip", "hskip", "frac", "sqrt",
           "sum", "prod", "in", "to", "le", "ge", "approx", "sim", "propto", "infty"}
unresolved = {}
for f in sorted(os.listdir(PAPER)):
    if not f.endswith(".tex") or f.startswith(("generated_", "tables_")):
        continue
    s = open(os.path.join(PAPER, f), encoding="utf-8").read()
    # strip comments
    s = re.sub(r"(?m)^%.*$", "", s)
    for m in re.finditer(r"\\([A-Za-z][A-Za-z0-9]*)", s):
        n = m.group(1)
        if n in defined or n in builtin:
            continue
        if n.startswith("p") and n[1:] in defined:
            continue
        unresolved.setdefault(n, set()).add(f)
print(f"unresolved references: {len(unresolved)}")
for n, fs in sorted(unresolved.items()):
    print(f"  \\{n}  ({', '.join(sorted(fs))})")
