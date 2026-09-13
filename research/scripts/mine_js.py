import re
import sys

path = sys.argv[1]
s = open(path, encoding="utf-8", errors="replace").read()
urls = sorted(set(re.findall(r"https?://[a-zA-Z0-9._\-/]+", s)))
print("--- absolute urls (%d) ---" % len(urls))
for u in urls[:120]:
    print(u)
print("--- relative routes mentioning pdf/paper/arxiv/api ---")
pat = re.compile(r"""["'`](/[a-zA-Z0-9._\-/{}$]*(?:pdf|paper|arxiv|api)[a-zA-Z0-9._\-/{}$]*)["'`]""")
paths = sorted(set(pat.findall(s)))
for p in paths[:120]:
    print(p)
