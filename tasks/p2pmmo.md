# p2pmmo battery — instructions, rubric, results

Arms: `src-p2pmmo-A-ctrl` vs `src-p2pmmo-A-exp`, both at `caa696a` (= parent of the fix).
History present; everything after base purged incl. origin refs
(verified: `git cat-file -t 7f42f0c` fails). Agent workspace-write confined to the arm dir.

Toolchain: `.tools` is a symlink to the hermetic vendored Go 1.27.1 (darwin/arm64).
Agents run with `GOROOT=<arm>/.tools/go GOTOOLCHAIN=local CGO_ENABLED=0` and a WRITABLE
`GOCACHE`/`GOMODCACHE` outside the repo (default user cache is fine on this machine).

## §2 — Agent brief (this section only is shown to the agent)

> Letter-gap burns are not reaching zeros: implement an observable burn sink (AddBurn /
> BurnTotal accounting with reads-burn and verdict legs) so burn conservation holds.
> Verify with `go test ./pkg/store/ ./pkg/server/`. Do not modify `*_test.go` files.

## Battery (evaluator-only below this line)

### Task A — burn sink (ACTIVE, oracle PREDICTED — see verification status)
- Base: `caa696a`. Sealed gold: `7f42f0c` (+276/−39: store/burn.go, schema, server reads;
  +148 lines across `verdict_burn_test.go`, `burn_test.go`).
- Oracle: copy the two `*_test.go` files from the gold commit over the arm, then
  `go test ./pkg/store/ ./pkg/server/`. P2P: full `go test ./...` stays green.
- ⚠️ VERIFICATION STATUS: F2P both-directions check did NOT complete in this environment
  (toolchain runaway, aborted before results). Before scoring any agent run, confirm:
  `go test` with overlaid gold tests FAILS on base (expect ≥1 fail in burn tests) and
  passes on gold. Do not score against an unconfirmed oracle. Command log goes here:

```
# run by: ______ on: ______
# base+gold-tests result: ______
# gold result: ______
```

## Scoring rubric

Solved iff overlaid gold tests go red→green AND full `go test ./...` stays green AND diff
is minimal (no test edits, no fixture regeneration). Cost from DSH per run.
Compare arms within-task only.

## Results (fill after scoring)

| run | arm | model | F2P | P2P | in-tok | out-tok | cache-tok | wall | notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ctrl | | | | | | | | |
| 2 | exp | | | | | | | | |
