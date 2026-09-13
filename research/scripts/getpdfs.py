"""Batch-download arXiv PDFs from the alphaxiv paper-asset mirror.

The local network resets TLS to arxiv.org (SNI blocking), so primary texts are
retrieved from alphaXiv's public PDF mirror. The exact URL used is recorded for
every fetched file in _cache/fetch_manifest.tsv.

Usage: python getpdfs.py <arxiv_id> [<arxiv_id> ...]
       python getpdfs.py --list ids.txt
"""
import os
import sys
import csv
import urllib.request
import urllib.error

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.abspath(os.path.join(HERE, "..", "_cache"))
PDFDIR = os.path.join(CACHE, "pdf")
MANIFEST = os.path.join(CACHE, "fetch_manifest.tsv")
os.makedirs(PDFDIR, exist_ok=True)


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/pdf,*/*",
        "Connection": "close",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def log(url, dest, status, note):
    newfile = not os.path.exists(MANIFEST)
    with open(MANIFEST, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        if newfile:
            w.writerow(["url", "local_path", "status", "note"])
        w.writerow([url, dest, status, note])


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: getpdfs.py <arxiv_id> [...]")
        return 2
    ids = []
    if args[0] == "--list":
        ids = [l.strip() for l in open(args[1], encoding="utf-8") if l.strip()]
    else:
        ids = args

    for aid in ids:
        url = "https://pdfs.assets.alphaxiv.org/%sv1.pdf" % aid
        dest = os.path.join(PDFDIR, "%s.pdf" % aid)
        try:
            status, ctype, data = fetch(url)
        except urllib.error.HTTPError as e:
            print("FAIL %s  HTTP %s" % (aid, e.code))
            log(url, dest, "HTTP %s" % e.code, "alphaxiv mirror")
            continue
        except Exception as e:
            print("FAIL %s  %s: %s" % (aid, type(e).__name__, e))
            log(url, dest, "ERR %s" % type(e).__name__, "alphaxiv mirror")
            continue
        if "pdf" not in ctype.lower():
            print("SKIP %s  content-type=%s" % (aid, ctype))
            log(url, dest, "BADCT %s" % ctype, "alphaxiv mirror")
            continue
        with open(dest, "wb") as f:
            f.write(data)
        print("OK   %s  bytes=%d -> %s" % (aid, len(data), dest))
        log(url, dest, "200", "alphaxiv mirror, content-type=%s" % ctype)
    return 0


if __name__ == "__main__":
    sys.exit(main())
