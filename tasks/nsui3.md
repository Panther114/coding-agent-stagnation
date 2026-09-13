# nsui3 battery — instructions, rubric, results

Arms: `src-nsui3-A-ctrl` (Standard) vs `src-nsui3-A-ptc` (PTC baseline) vs `src-nsui3-A-exp` (plugin-on-PTC), all at `b3910f6` (HEAD at materialization;
no future to purge — verified no other branches/tags). Agent workspace-write confined to
the arm dir. Agent edits = `git diff` vs HEAD.

⚠️ GUI tests pop real windows — runs need a GUI session, not headless SSH.
⚠️ NO sealed gold exists (the fix is unwritten): scoring is red-to-green + no-regressions
+ diff review, NOT gold comparison. Weaker oracle than codextras — disclosed, not hidden.

## §2 — Agent brief (paste into chat with workspace set to the arm dir)

> popover behavior seems off — i think after closing a popover it still reports as shown?
> there's a test for it somewhere (PopoverTest) that's red. can you look into the close
> behavior and fix it. run ./tests.sh to check, everything else should stay green, and
> don't touch the tests themselves. heads up the tests pop actual windows so run it
> where you can see the screen.

## Battery (evaluator-only below this line)

### Task A — popover close state (ACTIVE)
- Red assertion (deterministic 3/3 on Apple Silicon, GraalVM 25, verified 2026-09-13):
  `NSPopover final isShown false after close`; `PopoverTest` exits 1.
- Oracle: `./tests.sh` → assertion green AND no new failures (baseline: 1740 PASS / that 1 FAIL).
- Full suite takes minutes; single class: `java -XstartOnFirstThread
  --enable-native-access=ALL-UNNAMED -cp out/classes:out/tests nsui.tests.PopoverTest`.
- Runner flaw (disclose in paper if used): `tests.sh` prints ALL TESTS PASSED even with
  failures (WARN-and-continue). Score from assertion lines, never the footer.

### Staged (not yet materialized)
Suite-honesty milestone: runner fails red properly → integrate AppearanceTest + ~10 unlisted
test files → responder-cycle regression test from the live-observed bfc5da6 bug. Each stage
verifiable independently.

## Scoring rubric

Solved iff the red assertion turns green AND no previously-green assertion goes red AND the
diff is minimal (no assertion edits, no runner silencing). Cost from DSH per run.
Compare arms within-task only.

## Results (fill after scoring)

| run | arm | model | red→green? | regressions? | in-tok | out-tok | cache-tok | wall | notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ctrl | | | | | | | | |
| 2 | exp | | | | | | | | | |
| 3 | ptc | | | | | | | | | |
