"""HTML -> plain text extractor for literature verification.

Usage: python h2t.py <in.html> <out.txt>
"""
import sys
import re
import html as H


def to_text(h):
    h = re.sub(r"(?is)<script.*?</script>", " ", h)
    h = re.sub(r"(?is)<style.*?</style>", " ", h)
    h = re.sub(r"(?is)<noscript.*?</noscript>", " ", h)
    h = re.sub(r"(?is)<svg.*?</svg>", " ", h)
    h = re.sub(r"(?is)<br\s*/?>", "\n", h)
    h = re.sub(r"(?is)</(p|div|li|h[1-6]|tr|td|th|section|article|blockquote|pre)>", "\n", h)
    t = re.sub(r"(?s)<[^>]+>", " ", h)
    t = H.unescape(t)
    t = t.replace("\xa0", " ")
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n[ ]+", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    lines = [ln.strip() for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    raw = open(src, "rb").read()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            h = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    out = to_text(h)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote %s lines=%d chars=%d" % (dst, out.count("\n") + 1, len(out)))


if __name__ == "__main__":
    main()
