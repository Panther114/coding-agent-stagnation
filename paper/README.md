# The report — what is in this folder, and how to build it

**`main.tex` is the whole report in one file**: cover page, abstract, contents, body, references
page, and the two-page Chinese acknowledgement. There is no `\input` and no `.bib` — this folder is
self-contained, and `main.tex` is the only `.tex` file in it.

## Upload to Overleaf

1. Overleaf → New Project → Upload Project → drop **this whole folder** (or a zip of it).
2. **Menu → Compiler → XeLaTeX.** This is the one setting that matters. pdfLaTeX cannot set the
   Chinese cover page or acknowledgement and stops with `Unicode character 第 (U+7B2C)`.
3. **Compile twice** — the table of contents resolves on the second pass.

The font block selects itself, so the same file builds on Overleaf and on Windows:

```latex
\IfFontExistsTF{Noto Serif CJK SC}{ ...Noto CJK... }{ ...SimSun / Microsoft YaHei / SimHei... }
```

Overleaf ships the Noto CJK family; a Windows box has SimSun. Nothing to change either way — but if
you hard-code a font name later, it will only compile in one of the two places.

## What is canonical

**`paper/main.tex` in the repository is the source of truth.** The number audit
(`research/scripts/audit_paper_numbers.py`) reads that exact path and compares every number in it
against the artifact that produced it; it has already caught five real errors in our own draft. If
you rewrite in Overleaf, **paste the finished file back to `paper/main.tex`** and re-run the gates:

```bash
cd research
python scripts/run_rebuild_tests.py && python scripts/check_rebuild_consistency.py && \
python scripts/audit_claims.py && python scripts/audit_summary.py && \
python scripts/check_doc_references.py && python scripts/audit_paper_numbers.py
python scripts/verify_pdf.py ../paper/main.pdf
```

## Folders

| path | what |
|---|---|
| `main.tex` | the whole report, one file, builds with `xelatex` |
| `main.pdf` | the compiled report (12 pages) |
| `figures/` | seven figures: PDF (vector — use these) and PNG (preview only) |
| `data/` | `TABLES.md` (pre-rendered tables), `numbers.csv` (every number, machine-readable), `INDEX.md` (claim → value → artifact), `MANIFEST.json`. A copy of `research/EXPORT/` |
| `ESSAY.md` | the same text in markdown, for rewriting in your own voice |
| `ACKNOWLEDGEMENT_AND_AI_DISCLOSURE.md` | the acknowledgement + AI-use disclosure in markdown, with the fill-in fields marked |

The report currently includes **no figures** — the seven files are here so you can place them while
rewriting. Paste these blocks where you want them:

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig1_measurement_trap.pdf}
  \caption{Left: measured against each run's own final patch, failed runs look \emph{better} at localisation than solved ones. Right: measured against an independent gold patch the ordering reverses, in all three disjoint shard sets.}
  \label{fig:fig1_measurement_trap}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig2_router_vs_field.pdf}
  \caption{Means over the 24 cross-set cells. On the mode question every published family sits at or below the chance line while the router reaches 0.732.}
  \label{fig:fig2_router_vs_field}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig3_transfer_grid.pdf}
  \caption{Each bar is a model trained on one shard set and scored on another; the dashed line is the within-set mean. Cross-set performance equals within-set performance.}
  \label{fig:fig3_transfer_grid}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig4_calibration.pdf}
  \caption{The sequential rule is controlled at every level on the mean; the detection rate it buys is modest and is reported as such.}
  \label{fig:fig4_calibration}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig5_decision_curve.pdf}
  \caption{Scoring 1 for a correct route and $\lambda$ for a wrong one, on runs that failed. The router beats always-verify, random and always-search at every checkpoint and every cost setting.}
  \label{fig:fig5_decision_curve}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig6_cross_scaffold.pdf}
  \caption{The same features fitted inside each scaffold (green) reach 0.65--0.76; transferred from SWE-agent (red) they reach 0.32--0.50, at or below the fixed baselines. The generality claimed in this report is therefore bounded to one scaffold's shards.}
  \label{fig:fig6_cross_scaffold}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig7_live_conditions.pdf}
  \caption{Only the comparisons involving \emph{masked} reach significance. Both runtime interventions point the right way but neither is individually significant at this sample size.}
  \label{fig:fig7_live_conditions}
\end{figure}
```

## Before you submit

* fill the bracketed cover-page fields (school, province, instructor, Chinese names) — see
  `research/docs/SUBMISSION_CHECKLIST.md`
* build the final PDF here, then run 查重 **on that PDF**
* keep the final `.tex` in the repository, at this path, so the number audit stays live

## What used to be here

`paper/` once held two papers: an early Terminal-Bench draft split across `sections_*.tex` with
generated macro files, and the current single-file report under `paper/v2/`, plus an upload bundle
under `paper/overleaf/` that duplicated it. The draft and its macro files now live in
`research/archive/paper_v1/`; the bundle is gone because this folder *is* the bundle. Nothing was
lost — the old paths are in the git history.
