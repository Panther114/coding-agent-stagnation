# Human check — a hand-readable sample of the rebuild's mechanical labels

**Why this file exists.** The rebuild replaced AI-judged progress labels with mechanical
ones (did the workspace move?), which removes the original study's biggest limitation.
One objection survives: telemetry says whether something *changed*, not whether the agent
was *doing something sensible*. Only a person can check that.

**What to do.** Read the trajectory for each row below (the annotation card is named in
the table and lives in `data/annotations/tb2/cards_dense/`), decide whether the window is
stagnant or productive, and write your verdict in the `human_label` column of
`results/rebuild/human_check_sample.csv`. Do not look at the other two columns until you
have committed to your own — that is the point of the exercise.

**What it produces.** Your verdicts give two numbers the paper cannot currently state:
human-vs-stored-judgement agreement (how good the AI codebook was) and
human-vs-mechanical agreement (whether the mechanical definition matches a person). If the
second is clearly higher, the rebuild's label is validated by human judgement, not by
assumption.

**Selection.** 12 windows, half stored-STAGNANT and half stored-PRODUCTIVE,
drawn with a fixed seed (20260913) from the 386 windows that carry both a judgement and a mechanical label. Deterministic and
reproducible.

On this sample the mechanical label agrees with the stored judgement on **66.7%** of rows, against **66.9%** (AUC 0.669) over the whole
matched set — so the sample is representative rather than cherry-picked.

| # | task | run | t | window | quiet share | stored judgement | mechanical | card |
|---|---|---|---|---|---|---|---|---|
| 1 | build-pov-ray | `oboi8x8` | 24 | 10 steps | 0.00 | PRODUCTIVE | productive | `d_tb2_build-pov-ray__oboi8x8_24` |
| 2 | cobol-modernization | `z8rbv6p` | 39 | 10 steps | 0.30 | PRODUCTIVE | productive | `d_tb2_cobol-modernization__z8rbv6p_39` |
| 3 | compile-compcert | `qeLnFSj` | 60 | 10 steps | 0.50 | STAGNANT | productive | `d_tb2_compile-compcert__qeLnFSj_60` |
| 4 | crack-7z-hash | `Mp364LH` | 27 | 10 steps | 0.00 | STAGNANT | productive | `d_tb2_crack-7z-hash__Mp364LH_27` |
| 5 | extract-moves-from-video | `vRcGj7U` | 45 | 10 steps | 0.80 | STAGNANT | STAGNANT | `d_tb2_extract-moves-from-video__vRcGj7U_45` |
| 6 | feal-linear-cryptanalysis | `L3Ts8kn` | 12 | 10 steps | 0.30 | STAGNANT | productive | `d_tb2_feal-linear-cryptanalysis__L3Ts8kn_12` |
| 7 | feal-linear-cryptanalysis | `jbbLGgC` | 27 | 10 steps | 1.00 | STAGNANT | STAGNANT | `d_tb2_feal-linear-cryptanalysis__jbbLGgC_27` |
| 8 | financial-document-processor | `ygK3UcB` | 57 | 10 steps | 1.00 | STAGNANT | STAGNANT | `d_tb2_financial-document-processor__ygK3UcB_57` |
| 9 | git-leak-recovery | `3MYVn6Q` | 39 | 10 steps | 0.80 | PRODUCTIVE | STAGNANT | `d_tb2_git-leak-recovery__3MYVn6Q_39` |
| 10 | install-windows-3.11 | `2UtJ22k` | 9 | 10 steps | 0.20 | PRODUCTIVE | productive | `d_tb2_install-windows-3.11__2UtJ22k_9` |
| 11 | install-windows-3.11 | `mUYmJ4a` | 12 | 10 steps | 0.20 | PRODUCTIVE | productive | `d_tb2_install-windows-3.11__mUYmJ4a_12` |
| 12 | make-doom-for-mips | `DU5GBNE` | 24 | 10 steps | 0.10 | PRODUCTIVE | productive | `d_tb2_make-doom-for-mips__DU5GBNE_24` |

## How to score it

```powershell
cd research
# after filling in the human_label column of false/true (or 0/1):
python scripts/score_human_sample.py
```

## What it cannot settle

Twelve windows cannot validate 236,137 labels. What they can do is establish *whether the
mechanical definition and a person's reading agree at all*; if they disagree systematically,
the rebuild's target is wrong and every number above it changes. That is why this sample is
worth more than its size suggests.
