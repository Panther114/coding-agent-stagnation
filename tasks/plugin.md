# Batch-workflow plugin — outline (v1 BUILT 2026-09-13: plugins/dsh-batch-flow/)

## Goal
Cut per-task cost by collapsing multi-step mechanical work into fewer model turns,
without moving success rate. Mechanism: every model turn re-reads accumulated context
(measured 44:1 in/out); N calls in one turn instead of N turns removes N−1 re-reads.

## Non-goals
No autonomous stopping of runs. No block/deny on content (advisory + metering only).
No reimplementation of execution, scheduling, or policy — all inherited from the harness.

## Architecture: build ON PTC, not beside it
- Present as `code`/`both`; reuse `run_code` transport, generated SDK, nested-dispatch
  pipeline (pre/post-execute waterfalls), and the native parallel/exclusive scheduler
  (`isConcurrencySafe`, barriers, `maxParallelSubCalls`).
- **Version gate first**: confirm the installed DSH exposes `presentAs`, `codeRuntime`
  (TS worker or Python renderer), and the tool-presentation config. If any is absent,
  stop — do not polyfill the harness.
- Components (all new code is thin):
  1. **`batch` tool (declarative)**: model submits `{steps:[{tool,args,expect?}], mode:
     sequence|parallel, early_exit: <condition>, on_unexpected: stop|ask}`. Plugin
     compiles it to a `run_code` program (or drives nested dispatch directly where the
     API allows). No arbitrary model-written code for batched flows — auditable, bounded.
  2. **Reference-following read**: `read_plus(path)` returns file + resolved local
     imports/references in one result (kills re-read chains and import-chasing turns).
  3. **Metering**: per-batch input/output/cache tokens vs Standard-baseline projection;
     emitted as structured log for the experiment (this IS the cost readout).
  4. **Advisories** via post-execute `additionalContexts` (same channel as the shipped
     repeat reminder): sleep-poll → "background it or block with timeout"; hung-process
     pattern → "kill + blocking call"; verified-complete → "propose stop". Prescribe the
     alternative, never just "stop repeating".

## Detection rules (v1, all cheap string/state checks)
- Consecutive sleep/wait or repeated status-check with ~zero output novelty, sustained ≥K.
- Foreground process killed by interrupt after long run (C-c pattern).
- Verification green + no new goal for K steps (done-detection → stop proposal).
- Edit-size advisory on pre-execute (1-line edit ≈ 87% historical waste → "batch it?").

## Experiment mapping (3 arms, paired, within-task only)
- **ctrl** = Standard native (ecological baseline, what developers default to).
- **PTC** = primary comparator (isolates presentation/scheduler effect; replicates the
  field-missing PTC-vs-Standard measurement as a bonus contribution).
- **exp** = plugin-on-PTC (headline contrast: exp-vs-PTC; Standard as reference).
- Headline metric: spend per task with solve-rate non-inferiority (±5pp); baseline to
  beat ≈ $1.45/solve. Battery: codextras A/B (frozen), p2pmmo-A (oracle pending
  confirmation), nsui3-A (no-gold red-to-green). Enrich long/wait-prone tasks for power;
  meter NET savings (intervention text costs tokens too).

## Build order
1. Version-gate check on installed DSH (30 min; go/no-go).
2. Metering + `read_plus` (no behavior change; validates readout on frozen replays).
3. `batch` tool + advisories.
4. Replay firing rates on frozen trajectories → small-N live pilot → pre-reg full trial.

## Open questions
- Approval policy for `batch` contents (each step pre-approved, or whole-batch consent?).
- Barrier classification for batched edits (default exclusive unless proven safe?).
- `maxParallelSubCalls` tuning for read-heavy batches.
- Whether `both` mode confounds measurement (model may ignore the SDK) — default to `code`.
