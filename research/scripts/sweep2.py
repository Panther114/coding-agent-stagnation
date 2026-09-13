"""Targeted novelty sweep over OpenAlex with title/abstract phrase filters.

Usage: python sweep2.py
"""
import json
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

SELECT = ("id,doi,title,display_name,publication_year,publication_date,type,"
          "authorships,primary_location,abstract_inverted_index,cited_by_count")


def get(url, tries=3, timeout=60):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
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


def run(label, filt, n=8, extra=""):
    url = ("https://api.openalex.org/works?filter=%s&per-page=%d&select=%s%s"
           % (urllib.parse.quote(filt, safe=":,.!|"), n, SELECT, extra))
    try:
        d = get(url)
    except Exception as e:
        print("### %s\n  FETCH FAILED: %s" % (label, e))
        return []
    res = d.get("results", [])
    print("### %s" % label)
    print("    filter=%s  total=%s" % (filt, d.get("meta", {}).get("count")))
    for w in res:
        au = [a["author"]["display_name"] for a in (w.get("authorships") or [])][:5]
        pl = w.get("primary_location") or {}
        src = pl.get("raw_source_name") or (pl.get("source") or {}).get("display_name")
        print("  - %s" % w.get("display_name"))
        print("      year=%s type=%s venue=%s doi=%s cited=%s" % (
            w.get("publication_year"), w.get("type"), src, w.get("doi"), w.get("cited_by_count")))
        print("      url=%s" % pl.get("landing_page_url"))
        print("      auth=%s" % ", ".join(au))
        ab = unabstract(w.get("abstract_inverted_index"))
        if ab:
            print("      abs=%s" % (ab[:700] + ("..." if len(ab) > 700 else "")))
    print()
    return res


QUERIES = [
    ("title: agent stagnation",
     'title.search:agent stagnation'),
    ("title: stagnation + agent/LLM",
     'title.search:stagnation,title.search:agent'),
    ("abs: semantic livelock",
     'abstract.search:semantic livelock'),
    ("title: livelock + LLM",
     'title.search:livelock'),
    ("abs: coding agent stagnation",
     'abstract.search:coding agent stagnation'),
    ("abs: agent wandering",
     'abstract.search:agent wandering'),
    ("title: progress monitor + coding agent",
     'title.search:progress,title.search:coding agent'),
    ("abs: loop detection LLM agent",
     'abstract.search:loop detection LLM agent'),
    ("title: wasted computation agent",
     'title.search:wasted computation'),
    ("abs: early termination software agent",
     'abstract.search:early termination software agent'),
    ("title: stuck / agent",
     'title.search:stuck agent'),
    ("abs: reference-free progress",
     'abstract.search:reference-free progress agent'),
    ("abs: trajectory prefix failure prediction",
     'abstract.search:trajectory prefix failure prediction'),
    ("title: trajectory diagnostics coding agent",
     'title.search:trajectory diagnostics'),
]

if __name__ == "__main__":
    for label, filt in QUERIES:
        run(label, filt)
        time.sleep(1.2)
