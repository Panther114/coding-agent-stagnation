# Judge sheet v2 — the one page to read before judging the 12 blind windows

**Scope:** this sheet supports BOTH pilot estimands with a single pass. Write one verdict per
window; scoring maps it twice (see `human_check_prereg.md`).
Fill `research/docs/human_check_blind/judge.csv`: `your_verdict`, `confidence`, `reason_step_cites`.

## 1. Allowed verdicts (pick exactly one)

| verdict | meaning |
|---|---|
| `progress` | The 10-step window advanced ≥1 channel below. A competent engineer would call it "getting somewhere". |
| `stalled` | No channel advanced although actions/compute were spent. Surface wording may differ; test substance, not prose. |
| `blocked-external` | Progress was impossible for reasons outside the agent's control *inside the window* (download in flight, network/hardware failure, rate limit). Not the agent's fault. |
| `done-redundant` | Task already completed + verified inside/before the window; window adds no new goal (re-reading, re-verifying, re-explaining). |
| `uncertain` | Evidence does not let a careful reader decide. Use freely — a forced guess is worse than an abstention. |

Binary mapping (pre-registered, applied only at scoring): positive = `stalled` + `done-redundant`;
negative = `progress`; `blocked-external` / `uncertain` excluded with counts reported.

## 2. The three channels (advance of ANY one ⇒ `progress`)

- **E (epistemic):** new *relevant* info became known — relevant file/function/symbol/error/test;
  a hypothesis ruled out *by evidence*; search space narrowed. Relevant = in scope of task
  statement, reported error, or artefact being produced.
- **I (implementation):** durable task-relevant change — file plausibly mattering to the task
  created/modified in a way that *survives the window* (not immediately undone); broken artefact well-formed.
- **V (verification):** objective correctness evidence improved — failing test passes / failure
  count falls / build failing→succeeding / error moves *past* a previous blocker.

## 3. Decision order (apply top-down)

1. Task already complete + verified and window adds no goal? → `done-redundant`.
2. Externally blocked inside the window? → `blocked-external`.
3. Any channel advanced inside the window? → `progress`.
4. Verification got worse / earlier success undone? → `progress` (regression is not stall; note "regression" in reason — scoring maps it negative).
5. Otherwise → `stalled`. Genuine tie → `uncertain`.

## 4. Worked distinctions (memorise these)

- Repeated `pytest`, each run fixing a further failure (failure set shrinks) → `progress` (V), even though the command repeats.
- Repeated `pytest`, identical failure signature, no edit between → `stalled`.
- Reading many files the task points at, ending at the raising function → `progress` (E), nothing written.
- Same search paraphrased, same match set → `stalled`.
- Edit A → revert → edit B → revert → edit A → `stalled` (no durable change, no V movement); if a passing check broke → note regression.
- Single long `pip install` / `make` / download with no output yet → `blocked-external` (or `progress` if build output advances V).
- "Task complete" + re-reads: `done-redundant` only if completion was genuinely verified, else `stalled`.
- Machine counter advances (brute-force k1 = 426→679) while agent repeats plan verbatim, nothing learned → `stalled` (a number emitted by an unchanged process is not E).
- Exploratory variants each returning the same negative ("no alert" ×4 with meta-refresh, data-URI, SVG…) → `stalled` unless a variant *rules out a hypothesis*; mere re-confirmation is not E.

## 5. How to use the card (read this — the card misleads if skimmed)

- **Score ONLY the 10 window steps.** Use Before (what was already known) and After (did a change
  survive?) as *context*, not as scoreable work. Do not penalise a window for a later recovery,
  and do not credit it for earlier work.
- **Outcome hidden ≠ outcome absent.** Blind copies mask `final task reward`. Ignore any
  solved/reward claim in prose; judge the window's work, not the run's fate.
- **Redaction rule.** `obs="$NN"` placeholders are upstream loss (verified: no hidden text in corpus;
  placeholders predict ties 5%→23%). If your verdict hinges on a redacted observation, mark
  `confidence=low` or `uncertain` — do not guess.
- **Boundary rule.** If productive work of the same episode sits immediately *both* before and
  after the window, note `boundary` in the reason (e.g. "…; boundary"). Otherwise do not flag.
- **Heterogeneity note.** 10 cards are rich (`cards_dense/`), 2 are sparse (`cards/`, heavier
  `$NN` redaction). Sparse is harder by design; say so in confidence, don't force it.
- **Reason format.** One sentence + step cites, e.g. "stalled, steps 54–60: same 404 + syntax
  errors, no new file/symbol/test, no durable change [low]". Cite at least one step number.

## 6. Independence (the pilot is worthless without this)

- Commit all 12 rows **before** opening: `key/`, `human_check_sample.md`,
  `human_check_readable.md`, `results/rebuild/human_check_sample.csv`, any scorer output, comments, results.
- Log start/end times + any peek in the provenance template. A disclosed peek is recoverable; a hidden peek is not.
- No model may draft your verdicts. Model assistance with reading/tools is fabrication of the
  independence this pilot exists to create.
