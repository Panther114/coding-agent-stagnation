# Human pilot — blind packet (12 windows)

Blind order seed: `20260914` (shuffle of the 12 rows in `windows_to_judge.csv`).
Do NOT open `key/` until all 12 verdicts + confidences + reasons are committed and timestamped.
Do NOT open `research/docs/human_check_sample.md`, `human_check_readable.md`,
`research/results/rebuild/human_check_sample.csv`, or run any scoring script until committed.

For each row: open the blind card copy, apply `research/docs/judge_sheet_v2.md`,
fill `judge.csv` (`your_verdict`: stalled | progress | blocked-external | done-redundant | uncertain).

| blind_id | task | t | w | blind card |
|---|---|---|---|---|
| B01 | install-windows-3.11 | 12 | 10 | `cards/B01.md` |
| B02 | crack-7z-hash | 27 | 10 | `cards/B02.md` |
| B03 | extract-moves-from-video | 45 | 10 | `cards/B03.md` |
| B04 | cobol-modernization | 39 | 10 | `cards/B04.md` |
| B05 | make-doom-for-mips | 24 | 10 | `cards/B05.md` |
| B06 | compile-compcert | 60 | 10 | `cards/B06.md` |
| B07 | git-leak-recovery | 39 | 10 | `cards/B07.md` |
| B08 | build-pov-ray | 24 | 10 | `cards/B08.md` |
| B09 | feal-linear-cryptanalysis | 12 | 10 | `cards/B09.md` |
| B10 | financial-document-processor | 57 | 10 | `cards/B10.md` |
| B11 | install-windows-3.11 | 9 | 10 | `cards/B11.md` |
| B12 | feal-linear-cryptanalysis | 27 | 10 | `cards/B12.md` |
