"""Fetch URLs with a browser-like UA and report status/size/title.

Usage: python fetch_probe.py urls.txt [outdir]
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return resp.status, dict(resp.headers), data


def title_of(html: bytes) -> str:
    text = html.decode("utf-8", errors="ignore")
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def main():
    urls = [line.strip() for line in open(sys.argv[1], encoding="utf-8") if line.strip() and not line.startswith("#")]
    outdir = sys.argv[2] if len(sys.argv) > 2 else None
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    report = []
    for url in urls:
        entry = {"url": url}
        try:
            status, headers, data = fetch(url)
            entry["status"] = status
            entry["bytes"] = len(data)
            entry["ctype"] = headers.get("Content-Type", "")
            entry["title"] = title_of(data) if "html" in entry["ctype"] else ""
            if outdir:
                safe = re.sub(r"[^a-zA-Z0-9._-]", "_", url)[-120:]
                with open(os.path.join(outdir, safe), "wb") as fh:
                    fh.write(data)
                entry["saved"] = safe
        except urllib.error.HTTPError as exc:
            entry["status"] = exc.code
            entry["error"] = f"HTTPError {exc.code} {exc.reason}"
        except Exception as exc:  # noqa: BLE001
            entry["status"] = None
            entry["error"] = f"{type(exc).__name__}: {exc}"
        report.append(entry)
        print(json.dumps(entry, ensure_ascii=False))
    print("\n=== SUMMARY ===")
    for e in report:
        print(f"{e.get('status')}\t{e.get('bytes', '-')}\t{e['url']}\t{e.get('title','')[:90]}{e.get('error','')}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
