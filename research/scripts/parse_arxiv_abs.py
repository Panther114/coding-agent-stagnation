"""Extract title/abstract/authors from saved arXiv abs HTML pages.

Usage: python parse_arxiv_abs.py <dir-with-saved-arxiv-pages>
"""
import glob
import json
import os
import re
import sys

TAG = re.compile(r"<[^>]+>")


def clean(s: str) -> str:
    s = TAG.sub(" ", s)
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"\s+", " ", s).strip()


def parse(path: str) -> dict:
    html = open(path, "r", encoding="utf-8", errors="ignore").read()
    out = {"file": os.path.basename(path)}
    m = re.search(r'<meta name="citation_title" content="([^"]*)"', html)
    out["title"] = m.group(1) if m else clean((re.search(r"<title>(.*?)</title>", html, re.S) or [None, ""])[1] if re.search(r"<title>(.*?)</title>", html, re.S) else "")
    authors = re.findall(r'<meta name="citation_author" content="([^"]*)"', html)
    out["authors"] = authors
    m = re.search(r'<meta name="citation_date" content="([^"]*)"', html)
    out["date"] = m.group(1) if m else ""
    m = re.search(r'<blockquote class="abstract[^"]*">(.*?)</blockquote>', html, re.S)
    out["abstract"] = clean(m.group(1)).replace("Abstract:", "").strip() if m else ""
    m = re.search(r'<td class="tablecell subjects">(.*?)</td>', html, re.S)
    out["subjects"] = clean(m.group(1)) if m else ""
    m = re.search(r'<meta name="citation_pdf_url" content="([^"]*)"', html)
    out["pdf"] = m.group(1) if m else ""
    # detect "not found" pages
    out["not_found"] = ("No paper found" in html) or ("not found" in out.get("title", "").lower()) or not out["abstract"]
    return out


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(sys.argv[1], "*arxiv*"))):
        rows.append(parse(path))
    for r in rows:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        print("-" * 100)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
