"""Minimal HTML -> text converter (no external deps).

Usage: python html2text.py <input.html> [output.txt]
"""
import re
import sys
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0
        self.block = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "table", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "table", "section"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        raw = " ".join(self.parts)
        raw = re.sub(r"[ \t\u3000]+", " ", raw)
        raw = re.sub(r"\n\s*\n\s*\n+", "\n\n", raw)
        return "\n".join(line.strip() for line in raw.split("\n") if line.strip())


def convert(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        html = fh.read()
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()


if __name__ == "__main__":
    out = convert(sys.argv[1])
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(out)
