# codextras experiment battery — instructions, rubric, results

Arms: `src-codextras-ctrl/` (control harness) vs `src-codextras-exp` (treated harness).
Both are byte-identical clones at the SAME base commit; run the SAME task in both.
Agent workspace-write is confined to the arm dir. Agent edits = `git status`/`git diff`
vs HEAD (HEAD is the problematic commit; history present, fix purged — verify any time:
`git cat-file -t <fix-sha>` must fail).

 Hermetic: `bun test` only. No network during runs (tests need none).

## §2 — Agent brief (this section only is shown to the agent)

> The gateway crashes on some upstream responses ("response is not a JSON object") and
> mishandles some request bodies. Diagnose and fix so `bun test` is fully green.
> Do not modify `test/` — fix `src/` only.

## Battery (evaluator-only below this line)

### Task A — zstd bodies / non-JSON responses (ACTIVE)
- Base: `65a9b48` (= arm HEAD). Sealed gold: `37fc365` (content purged from arms).
- Oracle: copy `test/gateway.test.mjs` from the gold commit over the arm, run `bun test`.
- F2P (must flip): `sessionHash: absent without config…` + `zstd request bodies decode
  before parsing (Codex Desktop)` — 2 fail on base, 41/41 pass on gold (verified 2026-09-13).
- P2P: remaining 39 stay green.

### Task B — stream disconnects / upstream errors (STAGED, dirs not yet materialized)
- Base: `5f69296`. Sealed gold: `65a9b48`.
- F2P: 2 fail on base (incl. `removed declared models do not resurrect…`), 38/38 on gold
  (verified 2026-09-13). Materialize with the same recipe (clone → base branch → purge
  future → verify `git cat-file -t <gold>` fails).

## Scoring rubric

Quality (per run): F2P x/2 → P2P all-green? → diff review (minimal? no test edits?
no unrelated refactors?). A run counts as SOLVED iff F2P=2/2 AND P2P green.
Cost (user fills from DSH per run): input / output / cache tokens, wall time.
Headline per arm: solve rate + mean tokens per run + cost per solve. Compare arms
within-task only; never pool across tasks.

## Results (fill after scoring)

| run | arm | task | model | F2P | P2P | in-tok | out-tok | cache-tok | wall | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ctrl | A | | /2 | | | | | | |
| 2 | exp | A | | /2 | | | | | | |
