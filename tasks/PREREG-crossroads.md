# Pre-reg: Crossroads gate trial ("Round 8") — PTC / ping / review + batch lane

Frozen 2026-09-14 (round 5); batch lane appended round 6 (v0.4.0).
Treatment code: `dsh-error-shape-nudge` v0.3.0 (selftest 19/19, mock-ctx) for
v1 arms; **v0.4.0 required for any `[cx-3]` episode** (re-run installer one-liner
+ `pnpm install` + app restart first; verify installed version reads 0.4.0).
Live-fire verification (app reload + injection seen) is REQUIRED before any
episode below counts — record it in the run log.

## Arms (dir suffix → agent preset → session tag; no env, no restarts)

| dir suffix | preset | tag (1st line of brief) | role |
|---|---|---|---|
| `-std` | Standard | `[cx-0]` | control: status-quo ante |
| `-ptc` | PTC | `[cx-0]` | dense baseline (cost contrast lives here) |
| `-ping` | PTC | `[cx-1]` | interruption control (same checkpoints/channel/length) |
| `-rev` | PTC | `[cx-2]` | treatment: mode-routed autoreview |
| `-bstd` | Standard | `[cx-3]` | batch lane: batch-opportunity nudge, widest opportunity space |
| `-bptc` | PTC | `[cx-3]` | batch lane: batch nudge on top of PTC compression |

Tags are opaque to the model by design (blinding hygiene); this table is the
sealed mapping — do not explain tags in chat. First tag in a session locks it;
all 8 episodes (+ scratch verify) run interleaved under one app launch.
Headline contrasts: **rev-vs-ping** (does review content add success beyond
interruption? — Round 7's open ambiguity), std-vs-ptc (cost replication).
The streak nudge stays ON in all arms as background constant (deployed default);
arms differ only in gate content. Old `-ctrl`/`-exp` dirs are RETIRED
(contaminated worktrees / legacy batch-first treatment) — do not run here.

## Tasks (one task per comparison; never pool difficulties)

- codextras-A (base `65a9b48`, gold `37fc365`, F2P=2 → 41/41 verified): all 4 arms.
- codextras-B (base `5f69296`, gold `65a9b48`, F2P=2 → 38/38 verified): all 4 arms.
- codextras-A batch lane: `-bstd` + `-bptc` dirs (pristine clones at `65a9b48`,
  gold purged — verified at creation). Comparators are the finished A arms, no
  re-runs. Questions: bstd-vs-A-std (turn/cost delta, widest opportunity);
  bptc-vs-A-ptc (anything left once PTC compresses?); cheapest successful arm.
- p2pmmo-A, nsui3-A: CONDITIONAL on oracle confirmation / gold decision. Not in v1.
  p2pmmo/nsui3 batch lanes open only if codextras (v1 + batch) is interesting.

That is 8 episodes + 2 batch episodes, one run per dir, temp 0. No re-runs in a
used dir (fresh clone for any repeat — repeats add ~nothing at temp 0 anyway).

## Outcomes

- Primary: task success = F2P flips AND P2P holds, oracle procedure per
  `tasks/codextras.md` (gold test file copied over arm, `bun test`).
- Secondary: tokens in/out + turns + minutes (DSH UI table, per episode);
  `[crossroads]` covariate lines (branch, editsWT, verbs, reads, errSeen).
- Mechanism: treatment × covariate-quartile interaction on success (prediction:
  review helps high-locality / low-evidence runs; ping helps nothing differentially).

## Statistics and honesty about power

- Per-arm success with Wilson intervals; rev-vs-ping discordance within-task.
- With 2 tasks, the binary success contrast is near-uninformative by itself —
  pre-declared: v1's informative readouts are COST (continuous) + MECHANISM
  covariates + feasibility. A success-signal claim needs the scale-up (≥12 tasks
  or external replication); v1 success data is reported, not claimed on.
- Cost contrast std-vs-ptc IS powered (continuous, paired): expect replication
  of ~2× turn/cost reduction.

## Kill criteria (SPEC §6, binding)

(a) rev ≡ ping on success AND cost → kill review content, report interruption effect;
(b) benefit confined to visibly-failing runs → reject the silent-stagnation construct;
(c) success drop in low-signature solved quartile → kill universal application.
Any kill is a finding, written up, not a failed experiment.

## Masked-A lane ("A2", trap-first calibration)

Rationale: codextras-A proved no-trap unmasked (5/5 NO_STALL) — consistent with
the report's leakage finding (filenames hand over location). Masked-A removes
the leak to *manufacture* the trap: same base `65a9b48`, same gold, same oracle;
only test *observation* changes. Dirs `src-codextras-A-m{std,ptc,ping,rev}`
(pristine clones + `check.sh`, gold purged — verified at creation).
- `check.sh` (repo root, additive, P2P-safe): runs `bun test` internally, prints
  only `RESULT: N failed, M passed`, always exits 0. Comments sanitized (boring
  by design — must not advertise what's hidden). Same md5 in all 4 dirs.
- Masked brief = §2A with 2 lines changed: verify via `./check.sh` (never `bun
  test` directly — check.sh is the project runner and reports counts); rest
  verbatim incl. "don't touch test/".
- Test files stay readable (mirrors report's masked condition: knowing the suite
  ≠ knowing which fail). Direct `bun test` is forbidden by brief, not by force;
  the log shows every call, so a bypassing episode is visibly invalid → excluded.
- Promotion rule (binding): run `mstd` pilot ONLY first → blinded stall rubric.
  STALL → full masked battery. NO_STALL → kill masked-SWE direction, rethink domains.
- Scoring note: base own-suite is 38/38 GREEN at base — own-suite green is
  expected even with no fix. Success = gold-file F2P flip exclusively; never
  read own-suite green as success.

## Run protocol (human operator — user runs agents, fills tables)

Per episode, in order:
1. Workspace = the arm dir. Confirm `git status` clean (else STOP — wrong dir).
2. Empty session → preset (Standard for `-std`, PTC otherwise). No env needed.
3. Paste the tag line for the arm, then the §2 brief from `tasks/codextras.md`
   for the task. No extra hints, no mid-run steering, no evaluator-section
   leakage (brief = §2 quote only), and never explain what the tag means.
4. On completion: record tokens/turns/minutes + copy `[crossroads]` lines +
   note branch fired (A/B) from the transcript. Do NOT inspect gold.
5. Scoring (assistant, post-hoc): oracle F2P/P2P per task; gold stays sealed
   (verify any time: `git cat-file -t <gold-sha>` must fail inside arm dirs).

## Run log

| date | task | arm | preset | env method | live-fire? | tokens in/out | turns | success | notes |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

- Row 0 must be the live-fire verification (review seen @exec 10 in `-rev`,
  pulse seen in `-ping`, silence in `-std`/`-ptc`) before episodes count.
