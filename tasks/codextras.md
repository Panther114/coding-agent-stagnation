# codextras experiment battery — instructions, rubric, results

Arms: one TRIPLE per task: `src-codextras-<TASK>-ctrl` (Standard control) vs `src-codextras-<TASK>-ptc` (PTC baseline) vs `src-codextras-<TASK>-exp` (plugin-on-PTC). PTC arms run with the PTC agent preset; headline contrast is exp-vs-PTC.
Both are byte-identical clones at the SAME base commit; run the SAME task in both.
Agent workspace-write is confined to the arm dir. Agent edits = `git status`/`git diff`
vs HEAD (HEAD is the problematic commit; history present, fix purged — verify any time:
`git cat-file -t <fix-sha>` must fail).

 Hermetic: `bun test` only. No network during runs (tests need none).

## §2A — Agent brief, Task A (paste into chat with workspace set to the A arm dir)

> hey the gateway keeps blowing up on some upstream responses with 'response is not a
> JSON object'. i think the desktop client might be sending zstd-encoded bodies? not sure.
> figure it out and fix it. bun test should be fully green when you're done, and don't
> touch anything under test/ — fix src/ only.

## §2B — Agent brief, Task B (paste into chat with workspace set to the B arm dir)

> when upstream cuts the stream mid-response the gateway just dies silently, and i've
> also noticed the model catalog keeps resurrecting models i deleted. surface the
> upstream errors properly instead of swallowing them, and stop the catalog from
> bringing back removed models. bun test green when done, don't touch test/.

## Battery (evaluator-only below this line)

### Task A — zstd bodies / non-JSON responses (ACTIVE)
- Base: `65a9b48` (= arm HEAD). Sealed gold: `37fc365` (content purged from arms).
- Oracle: copy `test/gateway.test.mjs` from the gold commit over the arm, run `bun test`.
- F2P (must flip): `sessionHash: absent without config…` + `zstd request bodies decode
  before parsing (Codex Desktop)` — 2 fail on base, 41/41 pass on gold (verified 2026-09-13).
- P2P: remaining 39 stay green.

### Task B — stream disconnects / upstream errors (ACTIVE)
- Base: `5f69296`. Sealed gold: `65a9b48`.
- F2P: 2 fail on base (incl. `removed declared models do not resurrect…`), 38/38 on gold
  (verified 2026-09-13). Dirs `src-codextras-B-{ctrl,exp}` at base, gold purged (verified).

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
| 3 | ctrl | B | | /2 | | | | | | |
| 4 | exp | B | | /2 | | | | | | |
| 5 | ptc | A | | TBD | | 71804 | 22852 | 1217003 | 4min | 26 calls; F2P/P2P pending |
| 6 | ptc | B | | /2 | | | | | | |
