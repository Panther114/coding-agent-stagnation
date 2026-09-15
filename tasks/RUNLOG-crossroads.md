# Run log: Crossroads gate trial ("Round 8")

Pre-reg: `tasks/PREREG-crossroads.md`. Treatment code per episode in `plugin` col.

## Task A (codextras-A, base 65a9b48) — episodes + spend + log-analysis complete; SUCCESS Yes×5 via executed oracle (see †)

Log analysis (5 blinded analysts, shared rubric, strict definitions — silent: 4+
calls no new file/test/error/progress; noisy: same tool failing 2+ consecutively):

| arm | calls | failed | stall episodes | trap verdict |
|---|---|---|---|---|
| std | 105 | 0 | none (15- and 11-exec bash probe runs, each distinct hypotheses) | NO_STALL |
| ptc | 63 | 2 isolated (#8, #14) | none | NO_STALL |
| ping | 40 | 1 (#14) | none; no ack/discontinuity at pulses #10/#20 | NO_STALL |
| rev | 36 | 2 non-consecutive | none; post-#10 reads→probes, post-#20 diagnose→fix pivots (unattributable — reasoning/injected text excluded) | NO_STALL |
| bptc | 29 | 0 | none; 4 batchable streaks, NO post-streak batch increase | NO_STALL (+mechanism miss) |

Cross-cutting, all verified from exports:
- **Streak nudge never fired anywhere**: 5 failures in 273 analyst-counted calls,
  none consecutive-identical. Answers the dormant-mechanism question definitively.
- **Blinding held**: zero tag remarks in any arm (tags appear in title/user lines only).
- **Dose-vs-content undecidable here**: within-PTC cost monotone (64→41→37→30)
  fits interruption-count (0,2,2,≤3) AND content (none, none, review, batch-advice)
  equally; n=1 cannot separate. B is the tiebreak draw, not the judge.
- **Batch mechanism unproven**: bptc leads on cost with no observable batching
  response — its win is unattributed to batching (interruption-consistent).
- **Focus-narrowing pattern, now success-backed**: treated arms fixed 1 file
  (server.mjs) AND solved; controls sprawled 3-4 files + scaffolding AND solved.
  Narrower diffs for the same Yes — a real efficiency-of-fix effect.

**Verdict on codextras-A as stagnation evidence: RETIRED.** 5/5 NO_STALL under
strict definitions — no agent stuck, nothing un-stuck. Cost findings stand as
cost findings (relabeled, not withdrawn). Stagnation claims require trap-first
tasks (see forward plan in chat 2026-09-15). bstd export still missing (6th
analysis pending). † Executed scoring (2026-09-15, independent scorer): `bun compile`
+ live Codex zstd request that failed on base — all five A arms Yes. Gold-overlay
F2P/P2P never run on arms; success cells below reflect the executed method.

Operator-reported 2026-09-15 (transcribed verbatim into table; success by executed
oracle † — all Yes, see codextras.md grid):

| arm | calls | total tok | cache hit | uncached in | cached in | out | billed-proxy¹ |
|---|---|---|---|---|---|---|---|
| std | 95 | 8,998,883 | 97% | 306,582 | 8,637,310 | 54,991 | 1,225,304 |
| ptc | 64 | 5,961,289 | 96% | 234,556 | 5,683,008 | 43,725 | 846,582 |
| ping | 41 | 2,588,491 | 94% | 158,468 | 2,401,689 | 28,334 | 426,971 |
| rev | 37 | 2,362,851 | 92% | 184,565 | 2,149,845 | 28,441 | 427,991 |

¹ billed-proxy = uncached + out + 0.1×cached (typical cache-read discount;
provider pricing unconfirmed — ranking only). Deltas: calls std→rev −61%,
total −74%, billed-proxy −65%. Note ping≡rev on billed-proxy (427k vs 428k —
dead tie) while rev leads on calls (37 vs 41) and total; ping leads uncached
(158k vs 185k). n=1 per arm: treat sub-gaps as noise until B lands.

| arm | dir | preset | tag | plugin | success | notes |
|---|---|---|---|---|---|---|
| std | src-codextras-A-std | Standard | none (tagless) | 0.3.0 | Yes† | worktree: M compaction.mjs, native.mjs, server.mjs; ?? encoding.mjs |
| ptc | src-codextras-A-ptc | PTC | none (tagless) | 0.3.0 | Yes† | worktree: M compaction.mjs, convert/json.mjs, server.mjs, util.mjs (+219) |
| ping | src-codextras-A-ping | PTC | cx-1 | 0.3.0 | Yes† | worktree: M server.mjs only (+89/-3) |
| rev | src-codextras-A-rev | PTC | cx-2 | 0.3.0 | Yes† | worktree: M server.mjs only (+82/-3); operator live during run |

Worktree snapshot frozen 2026-09-14/15 ( Sleeping: dirs untouched since).
Note the shape contrast: std/ptc sprawled across 3-4 files (+untracked scaffolding);
ping/rev each made one focused server.mjs change — and all four solved.
Success = executed live-request oracle † (gold overlay never run on arms).

Row 0 live-fire: covered by operator's running (pulse/review seen in-session).

## Task B (codextras-B, base 5f69296) — pending

| arm | dir | preset | tag | plugin | tokens in/out | turns | success | notes |
|---|---|---|---|---|---|---|---|---|
| std | src-codextras-B-std | Standard | cx-0 | 0.3.0 | | | | |
| ptc | src-codextras-B-ptc | PTC | cx-0 | 0.3.0 | | | | |
| ping | src-codextras-B-ping | PTC | cx-1 | 0.3.0 | | | | |
| rev | src-codextras-B-rev | PTC | cx-2 | 0.3.0 | | | | |

## Batch lane (v0.4.0 required — reinstall + restart before ANY batch episode)

| arm | dir | preset | tag | plugin | tokens in/out | turns | success | notes |
|---|---|---|---|---|---|---|---|---|
| bstd | ~~src-codextras-A-bstd~~ DELETED by operator 2026-09-15 | Standard | cx-3 | 0.4.0 | 64 calls; 4,948,591 tot (98% hit; 107,540 un + 4,800,960 ca + 40,091 out); billed-proxy 627,727 — SINGLE-SOURCE, no log export, no suite verification possible | own-suite UNKNOWN (unverifiable post-deletion) | ⚠️ interaction cell destroyed: batch-without-PTC now operator-reported spend only; rebuild (fresh clone + run + export + suite) if batch claim pursued |
| bptc | src-codextras-A-bptc | PTC | cx-3 | 0.4.0 | 30 calls; 1,389,016 tot (95% hit; 71,827 un + 1,296,446 ca + 20,743 out); billed-proxy 222,215 | Yes† (executed live-request oracle) | worktree: M server.mjs only (+46/-3); test/ untouched by agent |
| bstd | src-codextras-B-bstd | Standard | cx-3 | 0.4.0 | | | | built 2026-09-15, pristine at 5f69296, gold purged |
| bptc | src-codextras-B-bptc | PTC | cx-3 | 0.4.0 | | | | built 2026-09-15, pristine at 5f69296, gold purged |

Batch questions: bstd-vs-A-std (turn/cost delta where opportunity space is
largest); bptc-vs-A-ptc (does batch advice add anything once PTC compresses?);
both-vs-A-rev (cost of success: cheapest successful arm?). p2pmmo/nsui3 lanes
open only if codextras (v1 + batch) is interesting in full.

## Masked-A lane ("A2", trap-first calibration; plugin 0.4.0)

Dirs `src-codextras-A-m{std,ptc,ping,rev}`: pristine clones at `65a9b48` + identical
`check.sh` (md5-verified), gold `37fc365` purged in all 4 (verified at creation).
Gatekeeper smoke-tested on base: `bun test` 38/38 → `RESULT: 0 failed, 38 passed`.
⚠️ Base own-suite is GREEN at base — own-suite green can never count as success;
F2P needs the gold file, for every arm including these.

| arm | dir | preset | tag | status |
|---|---|---|---|---|
| mstd | src-codextras-A-mstd | Standard | cx-0 | RUN — 63 calls; 3,902,417 tot (97%; 132,357 un + 3,734,629 ca + 35,431 out); billed-proxy 541,251. Worktree: M compaction.mjs. Export MISSING — analysis pending |
| mptc | src-codextras-A-mptc | PTC | cx-0 | RUN — 32 calls; billed-proxy 299,714. Worktree: M server.mjs. Analysis: NO_STALL, mask-compliant (3× check.sh, 1 test read, 0 bypass), compensated via bun -e probes |
| mping | src-codextras-A-mping | PTC | cx-1 | RUN — 48 calls; billed-proxy 469,868. Worktree: M compaction.mjs. Analysis: NO_STALL, compliant (3× check.sh), pulses no visible footprint |
| mrev | src-codextras-A-mrev | PTC | cx-2 | RUNNING — Branch-A review answered substantively mid-run (re-anchor, widen search, no fix yet); worktree: no edits yet (check.sh only). Export MISSING — analyze on completion |

Masked-vs-unmasked billed-proxy: mstd 541k vs std 1,225k (−56%); mptc 300k vs
ptc 847k (−65%); mping 470k vs ping 427k (+10%, noise). Masking costs LESS
(counts-only starves context — no traceback dumps) while hiding information:
trap≠costly, trap=information-poor. Within-masked monotone mptc<mping<mstd
replicates unmasked ordering — cost finding replicated under a new condition.
NOTE: operator ran full masked battery before mstd-promotion verdict (pre-reg
deviation, recorded); promotion question now answered jointly by analysis.

## Trap-hunt loop (goal, bridge-operated; effort medium unless noted)

Effort policy: medium/high (economic simulation); xhigh only post-proof.
Bridge exposes NO temperature control → variance via repeats/variants only;
golden reproducibility claims adjusted accordingly (STUCK on original + variant,
not 3/3 identical-temp draws). Oracle source: USER step (default).

| screen | dir | base | preset/tag/effort | session | status |
|---|---|---|---|---|---|
| B-masked std pilot (family 1, screen 1) | src-codextras-B-mstd | 5f69296 | Standard/cx-0/medium | sb-b178576e | COMPLETE — claimed both fixed, check.sh 0/35 (base total unknown). Native-log timeline: 37 calls, 0 failures; #1-20 ~17 distinct files (check.sh read FIRST — compliant, no direct bun test); plan #21; fix #22-33 (3 files +158/-12 corroborated); single check.sh #34. Rubric: NO_STALL. Family-1 screen fails. |
| B-masked std HIGH confirmation (family 1, screen 2) | src-codextras-B-mstd-hi | 5f69296 | Standard/cx-0/high, reworded brief | sb-48d06db1 | COMPLETE — claimed both fixed, check.sh 0/35. Native-log timeline: 62 calls, 0 failures; #1-25 search (~15 distinct files, check.sh read first — compliant); #26-44 fix; #45-62 verify with SECOND fix pass #51-55 after mid check (counts-driven iteration working). Rubric: NO_STALL. effort objection closed. |

FAMILY 1 (masked+multi-bug) RETIRED 0/5: A-masked mstd/mptc/mping + B-masked medium/high, all NO_STALL, all compliant. Masking hides information but does not trap frontier models at any tested effort/preset/task. Next: family 2 (decoy-rich) design.

## Manual rut-rescue protocol (operator-run, Standard preset, MINIMAL reasoning)

Playground: `src-codextras-A-rutsrc` (frozen source, NEVER run) + `src-codextras-A-rutwork`
(the playground; same dir reused → identical absolute paths across runs).
Reset between runs (check.sh is untracked — re-copied each reset):
`rm -rf tasks/src-codextras-A-rutwork && git clone -q file://$PWD/tasks/src-codextras-A-rutsrc tasks/src-codextras-A-rutwork && cp tasks/src-codextras-A-rutsrc/check.sh tasks/src-codextras-A-rutwork/check.sh`
Generator may use any dirt (false hints, masking); test validity comes from
rubric-verified stuckness only. NEVER instruct looping/failing — smooth solves are
discarded generator runs (recorded, not hidden).
INDUCING BRIEF (cx-0): gateway zstd brief + "we've confirmed the problem is in
src/adapter.mjs" (false; true locus server.mjs) + check.sh lines + don't-touch-test.
ARMING RULE (pre-registered, mechanical, same all arms): arm when the last 8 execs
show no new file touched AND no check.sh improvement AND no error. 40 execs without
meeting it = generator failure (discard, record). Operator bias removed by rule.
RESCUE (one user message, tag locks from there, counters restart, fires +10 execs):
control `[cx-0] continue` / ping `[cx-1] continue` / rev `[cx-2] continue` /
batch `[cx-3] continue`. Record from arming: turns-to-first-new-evidence,
post-arm stall episodes (rubric), check.sh trajectory, gold oracle (operator step).
