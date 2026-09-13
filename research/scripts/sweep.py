"""Multi-backend novelty sweep.

Backends: openalex (reliable here), semanticscholar (heavily rate-limited).

Usage:
  python sweep.py openalex "<query>" [n]
  python sweep.py s2 "<query>" [n]
  python sweep.py bank                 # run the full query bank on openalex
"""
import sys
import json
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

SELECT = "id,doi,title,display_name,publication_year,publication_date,type,authorships,primary_location,best_oa_location,abstract_inverted_index,cited_by_count"


def get(url, tries=3, timeout=60):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


def unabstract(inv):
    if not inv:
        return None
    pos = []
    for w, idxs in inv.items():
        for i in idxs:
            pos.append((i, w))
    pos.sort()
    return " ".join(w for _, w in pos)


def show_openalex(q, n):
    url = ("https://api.openalex.org/works?search=%s&per-page=%d&select=%s"
           % (urllib.parse.quote(q), n, SELECT))
    d = get(url)
    print("QUERY: %s" % q)
    print("TOTAL MATCHING IN OPENALEX: %s" % d.get("meta", {}).get("count"))
    for w in d.get("results", []):
        au = [a["author"]["display_name"] for a in (w.get("authorships") or [])][:6]
        pl = w.get("primary_location") or {}
        src = pl.get("raw_source_name") or (pl.get("source") or {}).get("display_name")
        print("-" * 90)
        print("TITLE : %s" % w.get("display_name"))
        print("YEAR  : %s   TYPE: %s   CITED: %s" % (w.get("publication_year"), w.get("type"), w.get("cited_by_count")))
        print("VENUE : %s" % src)
        print("DOI   : %s" % w.get("doi"))
        print("URL   : %s" % (pl.get("landing_page_url")))
        print("AUTH  : %s" % ", ".join(au))
        ab = unabstract(w.get("abstract_inverted_index"))
        if ab:
            print("ABS   : %s" % (ab[:900] + ("..." if len(ab) > 900 else "")))
    print("=" * 90)


def show_s2(q, n):
    url = ("https://api.semanticscholar.org/graph/v1/paper/search?query=%s&limit=%d"
           "&fields=title,year,venue,abstract,externalIds,citationCount,publicationTypes"
           % (urllib.parse.quote(q), n))
    d = get(url, tries=6, timeout=60)
    print("QUERY(s2): %s  TOTAL: %s" % (q, d.get("total")))
    for p in d.get("data", []):
        print("-" * 90)
        print("TITLE : %s" % p.get("title"))
        print("YEAR  : %s   VENUE: %s   CITED: %s" % (p.get("year"), p.get("venue"), p.get("citationCount")))
        print("IDS   : %s" % p.get("externalIds"))
        ab = p.get("abstract")
        if ab:
            print("ABS   : %s" % (ab[:800] + ("..." if len(ab) > 800 else "")))
    print("=" * 90)


BANK = [
    'all:"semantic livelock"',
    'abs:"agent stagnation"',
    'abs:"progress estimation" AND abs:"coding agent"',
    'abs:"loop detection" AND abs:"LLM agent"',
    'abs:"wasted computation" AND abs:"agent"',
    'abs:"coding agent" AND abs:"stagnation"',
    'abs:"software agent" AND abs:"stuck detection"',
    'abs:"early termination" AND abs:"coding agent"',
    'abs:"reference-free" AND abs:"agent trajectory"',
    'abs:"trajectory prefix" AND abs:"software engineering agent"',
    'abs:"task progress" AND abs:"autonomous software engineering"',
    'abs:"goal-conditioned progress" AND abs:"agent"',
    'abs:"process reward" AND abs:"coding agent"',
    'abs:"agent failure prediction" AND abs:"SWE-bench"',
]


def strip_arxiv_syntax(q):
    """OpenAlex uses plain search; drop the field prefixes."""
    out = q
    for pfx in ('all:', 'abs:', 'ti:'):
        out = out.replace(pfx, '')
    out = out.replace(' AND ', ' ').replace('"', '')
    return out.strip()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    mode = sys.argv[1]
    if mode == "bank":
        for q in BANK:
            try:
                show_openalex(strip_arxiv_syntax(q), 6)
            except Exception as e:
                print("FAILED %s: %s" % (q, e))
            time.sleep(1.5)
        return 0
    q = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    if mode == "openalex":
        show_openalex(q, n)
    elif mode == "s2":
        show_s2(q, n)
    else:
        print("unknown backend")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
