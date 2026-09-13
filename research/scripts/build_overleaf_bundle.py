"""Assemble `paper/overleaf/` — a folder that can be uploaded to Overleaf as-is.

Copies, never moves, so the repository layout and the six verification gates are untouched:

    paper/overleaf/
      main.tex                     the single self-contained report (no \\input, portable CJK fonts)
      README_OVERLEAF.md           how to upload, compile, and what is canonical
      figures/                     the seven report figures, PDF (vector) + PNG (preview)
      figures/legacy_v1/           the superseded v1 figures, kept for reference only
      figures_reference.tex        ready-to-paste figure environments for all seven
      data/                        TABLES.md, numbers.csv, INDEX.md — every number and its artifact
      ESSAY.md                     the same text in markdown, for rewriting
      ACKNOWLEDGEMENT_AND_AI_DISCLOSURE.md

    python scripts/build_overleaf_bundle.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT.parent / "paper" / "v2"
BUNDLE = ROOT.parent / "paper" / "overleaf"
EXPORT = ROOT / "EXPORT"

FIGURES = [
    ("fig1_measurement_trap", "The measurement trap, and its correction",
     "Left: measured against each run's own final patch, failed runs look \\emph{better} at "
     "localisation than solved ones. Right: measured against an independent gold patch the "
     "ordering reverses, in all three disjoint shard sets."),
    ("fig2_router_vs_field", "The router against every published family, on identical rows and folds",
     "Means over the 24 cross-set cells. On the mode question every published family sits at or "
     "below the chance line while the router reaches 0.732."),
    ("fig3_transfer_grid", "Six ordered train-to-test pairs",
     "Each bar is a model trained on one shard set and scored on another; the dashed line is the "
     "within-set mean. Cross-set performance equals within-set performance."),
    ("fig4_calibration", "Requested versus achieved false-alarm rate",
     "The sequential rule is controlled at every level on the mean; the detection rate it buys is "
     "modest and is reported as such."),
    ("fig5_decision_curve", "Value of routing, against every fixed policy",
     "Scoring 1 for a correct route and $\\lambda$ for a wrong one, on runs that failed. The router "
     "beats always-verify, random and always-search at every checkpoint and every cost setting."),
    ("fig6_cross_scaffold", "Where the method stops working",
     "The same features fitted inside each scaffold (green) reach 0.65--0.76; transferred from "
     "SWE-agent (red) they reach 0.32--0.50, at or below the fixed baselines. The generality claimed "
     "in this report is therefore bounded to one scaffold's shards."),
    ("fig7_live_conditions", "The live experiment: five conditions, 48 tasks",
     "Only the comparisons involving \\emph{masked} reach significance. Both runtime interventions "
     "point the right way but neither is individually significant at this sample size."),
]

README = """# Overleaf upload — what this folder is

`main.tex` here is the **whole report in one file**: cover page, abstract, contents, body,
references page, and the two-page Chinese acknowledgement. There is no `\\input`, so uploading
`main.tex` (plus `figures/` if you use the figures) is enough.

## Upload and compile

1. Overleaf → New Project → Upload Project → drop this folder (or select all files here).
2. **Menu → Compiler → XeLaTeX.** pdfLaTeX cannot set the Chinese cover page or acknowledgement and
   will stop with `Unicode character 第 (U+7B2C)`. This is the single most common failure here.
3. Compile twice — the table of contents resolves on the second pass.

The font block selects itself:

```latex
\\IfFontExistsTF{Noto Serif CJK SC}{ ...Noto CJK... }{ ...SimSun / Microsoft YaHei / SimHei... }
```

Overleaf has the Noto CJK family; a Windows machine has SimSun. Nothing to change either way — but
if you hard-code a font name later, it will only compile in one of the two places.

## What is canonical

`paper/v2/main.tex` in the repository is the source of truth, and the repository's number audit
(`research/scripts/audit_paper_numbers.py`) reads **that** path and checks every number in it against
the artifact that produced it — it has already caught five real errors in our own draft. If you edit
here, paste the finished file back to `paper/v2/main.tex` before the submission, and re-run:

```bash
cd research
python scripts/run_rebuild_tests.py && python scripts/check_rebuild_consistency.py && \\
python scripts/audit_claims.py && python scripts/audit_summary.py && \\
python scripts/check_doc_references.py && python scripts/audit_paper_numbers.py
cd ../paper/v2 && python verify_pdf.py
```

## Folders

| path | what |
|---|---|
| `main.tex` | the whole report, one file |
| `figures/` | seven figures, PDF (vector, use these) and PNG (preview) |
| `figures_reference.tex` | ready-to-paste `figure` environments for all seven — copy the blocks into the sections where you want them |
| `figures/legacy_v1/` | the **superseded** v1 figures. They belong to the earlier Terminal-Bench study and are NOT referenced by this report. Do not paste them in: they would contradict §4. |
| `data/` | `TABLES.md` (pre-rendered tables), `numbers.csv` (every number, machine-readable), `INDEX.md` (claim → value → artifact) |
| `ESSAY.md` | the same text in markdown, for rewriting in your own voice |
| `ACKNOWLEDGEMENT_AND_AI_DISCLOSURE.md` | the acknowledgement + AI-use disclosure in markdown, with the fill-in fields marked |

## Before you submit

* fill the bracketed fields (school, province, instructor, Chinese names) — see
  `research/docs/SUBMISSION_CHECKLIST.md`
* build the final PDF, then run 查重 **on that PDF**
* keep the final `.tex` in the repository so the number audit stays live

Rebuild this bundle after any edit to `paper/v2/`:

```bash
cd research && python scripts/build_overleaf_bundle.py
```
"""


def main() -> None:
    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    (BUNDLE / "figures" / "legacy_v1").mkdir(parents=True)
    (BUNDLE / "data").mkdir(parents=True)

    shutil.copy2(V2 / "main.tex", BUNDLE / "main.tex")
    shutil.copy2(V2 / "main.pdf", BUNDLE / "main_preview.pdf")
    for extra in ("ESSAY.md", "ACKNOWLEDGEMENT_AND_AI_DISCLOSURE.md"):
        if (V2 / extra).exists():
            shutil.copy2(V2 / extra, BUNDLE / extra)
    for name, _title, _cap in FIGURES:
        for ext in ("pdf", "png"):
            src = V2 / "figures" / f"{name}.{ext}"
            if src.exists():
                shutil.copy2(src, BUNDLE / "figures" / src.name)
    for src in sorted((ROOT.parent / "paper" / "figures").glob("*.png")):
        shutil.copy2(src, BUNDLE / "figures" / "legacy_v1" / src.name)
    for src in ("TABLES.md", "numbers.csv", "INDEX.md", "MANIFEST.json"):
        if (EXPORT / src).exists():
            shutil.copy2(EXPORT / src, BUNDLE / "data" / src)

    blocks = ["% Ready-to-paste figure environments.  Each number in the captions is the same value\n"
              "% the report's audit checks, so captions cannot drift from the text.\n",
              "\\usepackage{graphicx}   % already loaded by main.tex; listed here for completeness\n"]
    for name, title, cap in FIGURES:
        blocks.append(
            "\n% ---------------------------------------------------------------------------\n"
            f"% {title}\n"
            "% ---------------------------------------------------------------------------\n"
            "\\begin{figure}[t]\n  \\centering\n"
            f"  \\includegraphics[width=\\linewidth]{{figures/{name}.pdf}}\n"
            f"  \\caption{{{cap}}}\n  \\label{{fig:{name}}}\n\\end{{figure}}\n")
    (BUNDLE / "figures_reference.tex").write_text("".join(blocks), encoding="utf-8")
    (BUNDLE / "README_OVERLEAF.md").write_text(README, encoding="utf-8")

    n = sum(1 for _ in BUNDLE.rglob("*") if _.is_file())
    size = sum(f.stat().st_size for f in BUNDLE.rglob("*") if f.is_file())
    print(f"wrote {BUNDLE} — {n} files, {size / 1e6:.2f} MB")
    for f in sorted(BUNDLE.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(BUNDLE)}")


if __name__ == "__main__":
    main()
