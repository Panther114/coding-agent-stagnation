"""Extract readable text from the compiled PDF, to confirm numbers are really rendered.

Usage: python scripts/pdf_text_probe.py paper/main.pdf [needle ...]
"""
from __future__ import annotations

import re
import sys
import zlib


def streams(path: str):
    data = open(path, "rb").read()
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        raw = m.group(1)
        try:
            yield zlib.decompress(raw)
        except zlib.error:
            continue


def text_of(path: str) -> str:
    chunks = []
    for s in streams(path):
        if b"Tj" not in s and b"TJ" not in s:
            continue
        for m in re.finditer(rb"\((?:[^()\\]|\\.)*\)", s):
            t = m.group(0)[1:-1]
            t = t.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            chunks.append(t.decode("latin-1"))
    return " ".join(chunks)


def main() -> None:
    path = sys.argv[1]
    text = text_of(path)
    print(f"extracted {len(text)} characters of text")
    needles = sys.argv[2:] or ["0.742", "0.620", "0.678", "23.8", "88.1", "0.70", "1500", "654"]
    for n in needles:
        print(f"  {'FOUND   ' if n in text else 'MISSING '} {n}")
    print("\nsample:", text[:400].replace("  ", " "))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
