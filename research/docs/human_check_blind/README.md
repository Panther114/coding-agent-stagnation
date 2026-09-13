# human_check_blind — blinding rules

- Judge works ONLY from `packet.md` + `cards/Bxx.md` + `judge.csv` + `../../docs/3-judge-sheet.md`.
- Sealed: `key/` (mapping + stored/mechanical labels + SHA). Opening it before committing
  all 12 verdicts invalidates the pilot. Record open time in the provenance log.
- Also sealed until committed: `docs/human_check_sample.md`, `docs/human_check_readable.md`,
  `results/rebuild/human_check_sample.csv`, any scoring script output.
- Card copies are redacted (`final task reward: [HIDDEN]`). If any outcome leaks through card
  prose, ignore it and note it in the reason column.
- 10/12 cards are `cards_dense/` (rich), 2/12 are `cards/` (sparse, heavier `$NN` redaction:
  orig n=3 compile-compcert, n=8 financial-document-processor). Difficulty differs by design;
  mark low confidence / uncertain rather than guessing through redaction.
- Fill every row: your_verdict ∈ {stalled|progress|blocked-external|done-redundant|uncertain},
  confidence ∈ {high|medium|low}, reason_step_cites = 1 sentence with step numbers.
- No model may fill `judge.csv`. A model-filled sheet is fabrication, not a result.
