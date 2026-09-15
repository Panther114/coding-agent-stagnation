# dsh-error-shape-nudge

Second-consecutive-same-error advisory for DeepSeek Harness (`dsh >= 0.1.5-rc.1`).

## What it does

Watches every agent's tool results in `tools/post-execute`. When the **same tool fails
the same way twice in a row** — same exit code (`Exit Code: N` in bash-family output),
same `error.code`, else same first output line — it attaches one short nudge:

> Same error twice in a row (…).

The nudge tells the model to diagnose before re-running, and to prefer a
blocking/background wait over polling when it is waiting. It fires **once per streak**;
further identical failures stay silent until the streak breaks (success, different
error, or a user message).

It never blocks, vetoes, rewrites, or delays anything — purely advisory. Every code path
delegates via `next()` and is exception-guarded, so the plugin cannot break the loop.

## Install (local, offline)

```bash
cd /Users/will/.dsh/profiles/web
# add to package.json dependencies + dsh.profile.bundles, then:
pnpm install
# after any version bump: plain pnpm install/update will report "up to date"
# while leaving a STALE copy (verified 0.3.0 stuck twice). Refresh with:
rm -rf node_modules/dsh-error-shape-nudge && pnpm install
# then verify: node -p "require('./node_modules/dsh-error-shape-nudge/package.json').version"
# must print the bumped version, and diff of lib/index.js vs the repo must be empty.
```

Live `patchReload` picks it up without restarting the app. Remove the two lines and
re-run `pnpm install` to uninstall.

## Why this shape

- Counting in post-execute (not pre-execute) so denied/failed calls count — a model
  hammering a failing call is exactly the loop worth breaking.
- Per-agent `WeakMap` chains: one agent's streak never trips another's.
- Signature is outcome-based (`tool + error code`), not call-based: it fires on the
  *failure repeating*, even when the model rephrases arguments between attempts.
- Cost: zero tokens before the second identical failure; one short message per streak.

## Crossroads stall-gate (v0.4.0, trial arms)

Fixed-checkpoint periodic review + batch-opportunity arm. Spec:
`work/crossroads-r1/SPEC.md` (repo `coding-agent-stagnation`, branch `will/dev`).
Arm via session tag or env, same code all arms — no reinstall, no second plugin,
no restart to switch arms:

```
[cx-0]  gate off (streak nudge only)      -- first tag in a session locks it
[cx-1]  content-free checkpoint pulse     -- fires after execs 10 and 20
[cx-2]  mode-routed autoreview            -- fires after execs 10 and 20
[cx-3]  batch-opportunity nudge           -- 3 same-tool/all-read non-error
                                             execs in a row earn one one-line
                                             parallel-block suggestion; once per
                                             streak, max 3 per session
```

Paste the tag as the first line of the brief. Tags are opaque by design
(blinding hygiene; mapping lives in `tasks/PREREG-crossroads.md`). Without any
tag, `CROSSROADS_ARM=off|ping|review|batch` (process env) applies; default `off`.
Routing is transcript-state only (<2 edits with targets → LOST screen, else
WRONG-FIX screen, both + new-evidence tail). Reviews are advisories in the same
channel as the streak nudge. Covariates log via `ctx.logger.info` with a
`[crossroads]` JSON prefix (includes `src: tag|env`). A user message restarts
counters but a locked arm persists. Checkpoint counts are post-execute events,
not model turns (batch sub-calls each count — uniform across arms).
