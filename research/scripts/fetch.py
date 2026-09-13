"""Minimal HTTP fetcher with browser UA, used for literature verification.

Usage:
  python fetch.py <url> <outfile> [--binary]
Prints a one-line status report to stdout.
"""
import sys
import os
import ssl
import gzip
import io
import urllib.request
import urllib.error

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",
}


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=HEADERS)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        import certifi  # noqa
    except Exception:
        pass
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
        enc = r.headers.get("Content-Encoding", "")
        if "gzip" in enc:
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        return r.status, dict(r.headers), raw


def main():
    if len(sys.argv) < 3:
        print("usage: fetch.py <url> <outfile> [--binary]")
        return 2
    url = sys.argv[1]
    out = sys.argv[2]
    binary = "--binary" in sys.argv
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    try:
        status, hdrs, raw = fetch(url)
    except urllib.error.HTTPError as e:
        print("HTTPERROR %s %s" % (e.code, url))
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        with open(out, "wb") as f:
            f.write(body)
        print("body_len=%d" % len(body))
        return 1
    except Exception as e:
        print("ERROR %s: %s %s" % (type(e).__name__, e, url))
        return 1
    mode = "wb" if binary else "wb"
    with open(out, mode) as f:
        f.write(raw)
    print("OK status=%s bytes=%d ctype=%s -> %s" % (
        status, len(raw), hdrs.get("Content-Type", "?"), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
