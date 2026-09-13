"""OpenAlex helper: search works and print reconstructed abstracts + key metadata.

Usage:
  python oa.py search "<query>" [n]
  python oa.py arxiv <arxiv_id>          # looks up DOI 10.48550/arXiv.<id>
  python oa.py doi <doi>
  python oa.py title "<exact-ish title>" [n]
"""
import sys
import json
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# keep only fields we need, keeps responses small
SELECT = ",".join([
    "id", "doi", "title", "display_name", "publication_year", "publication_date",
    "type", "authorships", "primary_location", "best_oa_location", "locations",
    "abstract_inverted_index", "referenced_works_count", "cited_by_count",
    "biblio", "open_access", "indexed_in",
])


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def unabstract(inv):
    if not inv:
        return None
    pos = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    pos.sort()
    return " ".join(w for _, w in pos)


def brief(w):
    out = []
    out.append("TITLE: %s" % w.get("display_name"))
    out.append("YEAR: %s   DATE: %s   TYPE: %s" % (
        w.get("publication_year"), w.get("publication_date"), w.get("type")))
    out.append("DOI: %s   OPENALEX: %s" % (w.get("doi"), w.get("id")))
    auth = []
    for a in (w.get("authorships") or []):
        nm = (a.get("author") or {}).get("display_name")
        affs = a.get("raw_affiliation_strings") or []
        auth.append("%s%s" % (nm, (" [" + "; ".join(affs) + "]") if affs else ""))
    out.append("AUTHORS (%d): %s" % (len(auth), " | ".join(auth)))
    pl = w.get("primary_location") or {}
    src = (pl.get("source") or {}).get("display_name")
    out.append("VENUE(raw_source_name): %s" % pl.get("raw_source_name"))
    out.append("VENUE(source): %s" % src)
    out.append("PAGES: %s-%s  VOL: %s" % (
        (w.get("biblio") or {}).get("first_page"),
        (w.get("biblio") or {}).get("last_page"),
        (w.get("biblio") or {}).get("volume")))
    out.append("LANDING: %s" % pl.get("landing_page_url"))
    out.append("PDF: %s" % pl.get("pdf_url"))
    for loc in (w.get("locations") or []):
        out.append("  LOC: %s  pdf=%s" % (loc.get("landing_page_url"), loc.get("pdf_url")))
    out.append("CITED_BY: %s  REFS: %s" % (w.get("cited_by_count"), w.get("referenced_works_count")))
    ab = unabstract(w.get("abstract_inverted_index"))
    out.append("ABSTRACT:\n%s" % (ab if ab else "(none)"))
    return "\n".join(out)


def main():
    mode = sys.argv[1]
    if mode == "search":
        q = sys.argv[2]
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        url = ("https://api.openalex.org/works?search=%s&per-page=%d&select=%s"
               % (urllib.parse.quote(q), n, SELECT))
        d = get(url)
    elif mode == "title":
        q = sys.argv[2]
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        url = ("https://api.openalex.org/works?filter=title.search:%s&per-page=%d&select=%s"
               % (urllib.parse.quote(q), n, SELECT))
        d = get(url)
    elif mode == "arxiv":
        aid = sys.argv[2]
        doi = "10.48550/arxiv.%s" % aid.lower()
        url = ("https://api.openalex.org/works/doi:%s?select=%s" % (doi, SELECT))
        d = get(url)
        print(brief(d))
        return
    elif mode == "doi":
        url = ("https://api.openalex.org/works/doi:%s?select=%s" % (sys.argv[2], SELECT))
        d = get(url)
        print(brief(d))
        return
    else:
        print("unknown mode")
        return 2
    res = d.get("results", [])
    print("COUNT: %s  RETURNED: %d" % (d.get("meta", {}).get("count"), len(res)))
    for w in res:
        print("=" * 100)
        print(brief(w))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
