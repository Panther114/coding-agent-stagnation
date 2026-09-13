"""Diff two generated macro files, name by name.

Usage: python scripts/diff_macros.py paper/generated_tb2.tex.bak paper/generated_tb2.regen.tex
"""
from __future__ import annotations

import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
PAT = re.compile(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$")


def read(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        m = PAT.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def main() -> None:
    a, b = read(sys.argv[1]), read(sys.argv[2])
    print(f"{sys.argv[1]}: {len(a)} macros")
    print(f"{sys.argv[2]}: {len(b)} macros")
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    print(f"only in first : {len(only_a)} {only_a[:10]}")
    print(f"only in second: {len(only_b)} {only_b[:10]}")
    print(f"differing values: {len(diff)}")
    for k in diff[:25]:
        print(f"   {k:42} {a[k]}  ->  {b[k]}")


if __name__ == "__main__":
    main()
