"""Additional targeted novelty sweep: more angles on online stagnation detection.

Usage: python sweep3.py
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


def run(label, filt, n=8):
    url = ("https://api.openalex.org/works?filter=%s&per-page=%d&select=%s"
           % (urllib.parse.quote(filt, safe=":,.!|"), n, SELECT))
    try:
        d = get(url)
    except Exception as e:
        print("### %s\n    FETCH FAILED: %s" % (label, e))
        return
    print("### %s   [total=%s]" % (label, d.get("meta", {}).get("count")))
    for w in d.get("results", []):
        au = [a["author"]["display_name"] for a in (w.get("authorships") or [])][:5]
        pl = w.get("primary_location") or {}
        src = pl.get("raw_source_name") or (pl.get("source") or {}).get("display_name")
        print("  - %s" % w.get("display_name"))
        print("      year=%s type=%s venue=%s cited=%s" % (
            w.get("publication_year"), w.get("type"), src, w.get("cited_by_count")))
        print("      url=%s" % pl.get("landing_page_url"))
        print("      auth=%s" % ", ".join(au))
        ab = unabstract(w.get("abstract_inverted_index"))
        if ab:
            print("      abs=%s" % (ab[:650] + ("..." if len(ab) > 650 else "")))
    print()


QUERIES = [
    ("abs: stuck detection LLM agent", 'abstract.search:stuck detection agent'),
    ("abs: agent progress estimation online", 'abstract.search:agent progress estimation online'),
    ("abs: marginal progress agent", 'abstract.search:marginal progress agent'),
    ("abs: no progress detection agent", 'abstract.search:no progress autonomous agent'),
    ("abs: context rot agent trajectory", 'abstract.search:context rot agent'),
    ("abs: coding agent loop repetition", 'abstract.search:coding agent repetitive loop'),
    ("abs: agent redundancy wasted steps", 'abstract.search:redundant steps agent wasted'),
    ("abs: runtime monitor agent trajectory", 'abstract.search:runtime monitor agent trajectory'),
    ("abs: task-relevant evidence agent", 'abstract.search:task-relevant evidence agent'),
    ("abs: semantic diversity embedding agent trajectory", 'abstract.search:semantic diversity agent trajectory'),
]

if __name__ == "__main__":
    for label, filt in QUERIES:
        run(label, filt)
        time.sleep(1.2)
