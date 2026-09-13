# Overleaf upload — what this folder is

`main.tex` here is the **whole report in one file**: cover page, abstract, contents, body,
references page, and the two-page Chinese acknowledgement. There is no `\input`, so uploading
`main.tex` (plus `figures/` if you use the figures) is enough.

## Upload and compile

1. Overleaf → New Project → Upload Project → drop this folder (or select all files here).
2. **Menu → Compiler → XeLaTeX.** pdfLaTeX cannot set the Chinese cover page or acknowledgement and
   will stop with `Unicode character 第 (U+7B2C)`. This is the single most common failure here.
3. Compile twice — the table of contents resolves on the second pass.

The font block selects itself:

```latex
\IfFontExistsTF{Noto Serif CJK SC}{ ...Noto CJK... }{ ...SimSun / Microsoft YaHei / SimHei... }
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
python scripts/run_rebuild_tests.py && python scripts/check_rebuild_consistency.py && \
python scripts/audit_claims.py && python scripts/audit_summary.py && \
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
