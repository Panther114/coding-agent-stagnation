"""Repair mangled macro names by matching against the generated macro list.

`fix_macro_prefixes.py` stripped leading p's too aggressively: \\ppairX -> \\airX. Reconstruct by
finding, for each undefined reference, the generated macro whose name ends with it.
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
have = sorted(set(re.findall(r"\\newcommand\{\\(\w+)\}", gen)), key=len, reverse=True)

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
          "tabularx", "booktabs", "float", "captionof", "author", "title", "date", "today",
          "maketitle", "bibliography", "bibliographystyle", "captionsetup", "textsc",
          "evid", "mon", "nov", "rep", "sem", "ver", "work", "st", "fmt", "ptag", "pn",
          "pmon", "preg", "pdet", "pdr", "pseq", "pair", "probe", "pvariance", "psub",
          "cal", "auc", "within", "rt", "abl", "cs", "pc", "ops", "doc", "tab", "fig"}

total = 0
for fn in FILES:
    p = os.path.join(PAPER, fn)
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8").read()
    used = sorted(set(re.findall(r"\\([A-Za-z]+)", t)), key=len, reverse=True)
    mapping = {}
    for u in used:
        if u in have or u in IGNORE:
            continue
        if ("p" + u) in have:
            mapping[u] = "p" + u
            continue
        # mangled: find a generated macro whose name ends with this reference
        cands = [g for g in have if g.endswith(u)]
        if len(cands) == 1:
            mapping[u] = cands[0]
        elif len(cands) > 1:
            # prefer the shortest superset (fewest spurious leading characters)
            mapping[u] = min(cands, key=len)
    if not mapping:
        continue
    for u, target in mapping.items():
        t = re.sub(r"\\" + re.escape(u) + r"(?![A-Za-z])", "\\\\" + target, t)
    open(p, "w", encoding="utf-8").write(t)
    total += len(mapping)
    print(f"  {fn}: {{ {', '.join(f'{k}->{v}' for k, v in list(mapping.items())[:6])} }}"
          f"{' ...' if len(mapping) > 6 else ''}")
print(f"total repaired: {total}")

still = []
for fn in FILES:
    p = os.path.join(PAPER, fn)
    if not os.path.exists(p):
        continue
    t = open(p, encoding="utf-8").read()
    for u in sorted(set(re.findall(r"\\([A-Za-z]+)", t))):
        if u not in have and u not in IGNORE and ("p" + u) not in have:
            if not any(g.endswith(u) for g in have):
                still.append((fn, u))
print(f"genuinely unresolved (no candidate): {len(still)}")
for fn, u in still[:12]:
    print(f"   {fn}: \\{u}")
