"""Check that `paper/` is ready to drop into Overleaf, then zip it for upload.

`paper/` *is* the Overleaf project: one self-contained `main.tex`, its figures, and the supporting
markdown.  Nothing is assembled here any more — an earlier `build_overleaf_bundle.py` copied the
whole tree into `paper/overleaf/`, which just duplicated it.  This only asserts the properties
that make the folder upload-ready and then produces a single file to hand to Overleaf:

  * exactly one `.tex`, and it has no `\\input`, no `\\include` and no `.bib` dependency;
  * the seven figures are present, as PDF (what LaTeX uses) and PNG (what a human opens);
  * `main.pdf` is newer than `main.tex` — a stale PDF next to a fresh source is how a wrong
    number reaches a judge;
  * no LaTeX build junk is shipped.

Usage: python scripts/build_overleaf_zip.py
"""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # the acknowledgement heading is Chinese

ROOT = Path(__file__).resolve().parents[1]  # research/
PAPER = ROOT.parent / "paper"
OUT = ROOT / "EXPORT" / "overleaf_upload.zip"
JUNK = ("*.aux", "*.log", "*.out", "*.toc", "*.bbl", "*.blg", "*.synctex.gz")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def main() -> None:
    problems: list[str] = []

    tex = sorted(PAPER.glob("*.tex"))
    if [t.name for t in tex] != ["main.tex"]:
        problems.append(f"expected exactly one .tex (main.tex), found {[t.name for t in tex]}")

    main_tex = PAPER / "main.tex"
    src = main_tex.read_text(encoding="utf-8")
    for token, why in (("\\input{", "it would depend on another file"),
                       ("\\include{", "it would depend on another file"),
                       ("\\bibliography{", "it would need a .bib file"),
                       ("\\addbibresource", "it would need a .bib file")):
        if token in src:
            problems.append(f"main.tex contains {token!r} — {why}")
    if "致谢与人工智能使用声明" not in src:
        problems.append("main.tex has lost the Chinese acknowledgement heading")

    figdir = PAPER / "figures"
    pdfs = sorted(figdir.glob("*.pdf"))
    pngs = sorted(figdir.glob("*.png"))
    if len(pdfs) != 7:
        problems.append(f"expected 7 figure PDFs in figures/, found {len(pdfs)}")
    for pdf in pdfs:
        if not (figdir / f"{pdf.stem}.png").exists():
            problems.append(f"{pdf.name} has no PNG twin")

    main_pdf = PAPER / "main.pdf"
    if not main_pdf.exists():
        problems.append("main.pdf is missing — compile before uploading")
    elif main_pdf.stat().st_mtime < main_tex.stat().st_mtime:
        problems.append("main.pdf is OLDER than main.tex — recompile (xelatex, twice)")

    junk = [p.name for pat in JUNK for p in PAPER.glob(pat)]
    if junk:
        problems.append(f"build junk in the upload folder: {sorted(junk)}")

    print(f"paper/  ->  {PAPER}")
    print(f"  main.tex   {main_tex.stat().st_size:>9,} B   sha {sha(main_tex)}")
    if main_pdf.exists():
        print(f"  main.pdf   {main_pdf.stat().st_size:>9,} B   sha {sha(main_pdf)}")
    print(f"  figures/   {len(pdfs)} pdf + {len(pngs)} png")
    print(f"  .tex files {[t.name for t in tex]}")

    if problems:
        print("\nNOT UPLOAD-READY:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in PAPER.rglob("*") if p.is_file())
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(PAPER))
    print(f"\nupload-ready: {len(files)} files")
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1e6:.2f} MB)")
    print("\nOverleaf → New Project → Upload Project → this zip.")
    print("Then Menu → Compiler → XeLaTeX, and compile twice.")


if __name__ == "__main__":
    main()
