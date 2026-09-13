"""Extract text from a PDF using PyMuPDF.

Usage: python pdf2txt.py <in.pdf> <out.txt>
"""
import sys
import fitz

src, dst = sys.argv[1], sys.argv[2]
doc = fitz.open(src)
parts = []
for i, page in enumerate(doc):
    parts.append("\n\n========== PAGE %d ==========\n" % (i + 1))
    parts.append(page.get_text("text"))
txt = "".join(parts)
with open(dst, "w", encoding="utf-8") as f:
    f.write(txt)
print("%s: pages=%d chars=%d -> %s" % (src, doc.page_count, len(txt), dst))
