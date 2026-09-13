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
