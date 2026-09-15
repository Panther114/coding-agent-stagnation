# codextras experiment battery — instructions, rubric, results

Arms: one set per task: `src-codextras-<TASK>-std` (Standard control) vs `-ptc` (PTC baseline) vs `-ping` (PTC + content-free pulses) vs `-rev` (PTC + mode-routed review) vs `-bptc`/`-bstd` (batch-opportunity nudge). Same plugin build all arms, selected per session by opaque tag (`[cx-0..3]`, mapping sealed in `PREREG-crossroads.md`); PTC arms run with the PTC agent preset; headline contrasts rev-vs-ping (success) and std-vs-ptc (cost).
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
- Designed oracle (VERIFIED on gold, NEVER RUN on arms): copy `test/gateway.test.mjs`
  from the gold commit over the arm, run `bun test`.
- F2P (must flip): `sessionHash: absent without config…` + `zstd request bodies decode
  before parsing (Codex Desktop)` — 2 fail on base, 41/41 pass on gold (verified 2026-09-13).
- P2P: remaining 39 stay green.
- EXECUTED oracle (every reported success cell): `bun compile` the arm worktree, route a
  real Codex zstd request that failed on the base build — fixed iff it now succeeds.
  Production actually working outranks test-counting; all sessions were rated against this.

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

## Results — Task A (spend logged 2026-09-15 from DSH UI tables; success by EXECUTED oracle, see †)

| run | arm | task | model | F2P | P2P | in-tok | out-tok | cache-tok | wall | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | std | A | muse-spark-1.3 | Yes† | Yes† | 306582 | 54991 | 8637310 | | 95 calls; tagless (gate off); sprawl 3f+new file |
| 2 | ptc | A | muse-spark-1.3 | Yes† | Yes† | 234556 | 43725 | 5683008 | | 64 calls; tagless; sprawl 4f+219 |
| 3 | ping | A | muse-spark-1.3 | Yes† | Yes† | 158468 | 28334 | 2401689 | | 41 calls; `[cx-1]` + pulses verified in log; 1 file |
| 4 | rev | A | muse-spark-1.3 | Yes† | Yes† | 184565 | 28441 | 2149845 | | 37 calls; `[cx-2]` + reviews verified in log; 1 file |
| 5 | bptc | A | muse-spark-1.3 | Yes† | Yes† | 71827 | 20743 | 1296446 | | 30 calls; `[cx-3]` + batch notes verified; 1 file |
| 6 | std | B | | /2 | | | | | | NO RUNS — blank, not pending |
| 7 | ptc | B | | /2 | | | | | | NO RUNS — blank, not pending |
| 8 | ping | B | | /2 | | | | | | NO RUNS — blank, not pending |
| 9 | rev | B | | /2 | | | | | | NO RUNS — blank, not pending |

† Executed scoring (2026-09-15, independent scorer, operator-confirmed): `bun compile`
the arm worktree, route a real Codex zstd request that failed on the base build —
fixed iff it now succeeds. All five A arms: Yes. The designed gold-overlay oracle
(2 F2P → 41/41 on gold, verified 2026-09-13) was NEVER run on any arm; F2P/P2P cells
above therefore record the executed live-request verdict, not gold-overlay counts.

Masked-A lane (mstd/mptc/mping/mrev + check.sh gatekeeper) lives in `RUNLOG-crossroads.md`
with its own spend table; UNSCORED by any method to date (neither gold overlay nor
live-request oracle run on masked arms).

## Provenance notes (transcript-verified 2026-09-15, `sessions/`)

- Tags: `[cx-1]` present only in ping/mping logs, `[cx-2]` only in rev/mrev, `[cx-3]`
  only in bptc; std/ptc/mstd/mptc ran TAGLESS (gate off). No arm received another
  arm's content. Treatment texts verified in-log (pulses/reviews/batch notes).
- Streak nudge: ZERO firings in all 9 trial arms (no consecutive-identical failure
  in ~300 calls). Single firing in the whole corpus: `codextras-A-rutwork2-base`
  (operator's manual rut playground — mechanism existence proof, not trial data).
- `codextras-A-mrev.jsonl` is a COMPLETE 11-step session that ended right after
  answering the Branch-A review (turn completed, never reached fix): usable for
  review-response analysis only, not cost/success.
- `codextras-A-rutwork2-base.jsonl` (58 calls, later of two playground sessions;
  operator believes snapshot is rutwork2-base — unconfirmed): operator-built manual
  rut artifact whose base fork is the call point from which rescue runs launched;
  brief/conditions otherwise NOT on record — provenance incomplete; excluded
  from both batteries until a one-line provenance note lands.
