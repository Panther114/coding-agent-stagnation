# dsh-batch-flow

Declarative batch tool-calls, reference-following reads, and per-rule metering for
DeepSeek Harness (`dsh >= 0.1.5-rc.1`). Advisory + metering only — never blocks.

## Tools

**`batch`** — run a declared list of tool calls in one model turn instead of many.
Spec: `{steps: [{tool, args?, expect?: {contains?, matches?, exitCode?}, id?}],
mode?: sequence|parallel, on_unexpected?: stop|continue}`.
Each step is validated; expectations are checked; `stop` (default) early-exits on the
first unsatisfactory step with a named reason. Parallel steps must be independent —
**no rollback** (same contract as PTC). One turn instead of N removes N−1 full-context
re-reads, which dominate spend.

**`read_plus`** — `read(path)` plus every local file it references (JS/TS
import/require/export-from, Python relative imports), in one result. Bounded (10 files,
20k chars each), cycle-guarded, stays inside the workspace root, skips binaries and
`node_modules`/`.git`. Kills import-chasing re-read chains.

## Metering

Per-agent counters (batches, batch calls, early exits, read_plus calls/files, nudges,
char volumes). Counts, not tokens — token totals come from the harness UI. Rules are
separately measurable so losers can be cut.

## Third-failure escalation

A post-execute observer counts consecutive identical error shapes per agent; at the 3rd
it attaches a diagnose-before-retry nudge (the sibling `dsh-error-shape-nudge` fires at
2; this one escalates when the nudge didn't stick). Fires once per streak, then silent.
Resets on success, new error, or user message.

## Install (local, offline)

Same as the sibling: add `file:` dep + bundle row in the profile `package.json`, run
`pnpm install` in the profile dir. Remove both to uninstall. Mounts at (re)start —
this profile does not hot-mount new bundles.
