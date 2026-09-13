# `Route` — a runnable demo

A runtime router for coding agents. It answers the one question a runtime has to act on:

> The agent is struggling. Is it **LOST** — it has not found the code that needs changing — or is it
> **WRONG-FIX** — it found the right code and its change does not work?

Those call for **opposite** interventions (supply a location, or force a re-check of the fix).
Published stagnation and loop detectors detect *that* an agent is stuck and carry no usable signal
about *how*: on identical rows and folds they score 0.41–0.54 on this question, i.e. at or below
chance. This router scores 0.73.

Everything below is offline, deterministic, needs no API key, and reads only public data already in
the repository.

## Run it

```bash
cd <repo root>
python demo/route.py --fit                 # train on shards 0-3, cache the model (~2 min)
python demo/route.py --summary             # held-out numbers, against the frozen artifact
python demo/route.py --list                # held-out runs, with their true failure mode
python demo/route.py --replay <run_id>     # step through one run, checkpoint by checkpoint
python demo/route.py --live research/results/live/episodes48.jsonl   # live episode outcomes
```

`--fit` writes `demo/_cache/router.pkl` (2.7 KB: two logistic heads over 34 rate features).
Nothing in the runtime path reads the run's length, its final patch, or its outcome.

## What `--summary` prints

```
router performance at 20% of the run, trained on shards 0-3

  heldout_B_shards4_7    n=19,648  y_fail AUC=0.696  lost-vs-wrongfix AUC=0.735
  heldout_C_shards8_11   n=21,079  y_fail AUC=0.722  lost-vs-wrongfix AUC=0.727
```

Those four numbers are **the same cells** as `results/rebuild/route_modes_transfer.json`
(`A_shards0_3 -> B_shards4_7` and `A_shards0_3 -> C_shards8_11`, fraction 0.20, method
`own_rates`), so `--summary` is a live reproduction of a frozen result rather than a separate
claim: the artifact says 0.6965 / 0.7346 and 0.7220 / 0.7274.

## What `--replay` prints

A real held-out run, 107 steps, the router deciding at four checkpoints:

```
=== replaying held-out run iterative__dvc-4034::swe-agent-llama-70b::f1d679f4cf12 ===
    107 steps total; router decides at 20% = step 21

  at  10% of the run:
      P(fail) = 0.946   P(wrong-fix | this is a failing run) = 0.290
      -> SEARCH (it has not found the code yet -- supply a location hint)
  ...
  at  60% of the run:
      P(fail) = 0.980   P(wrong-fix | this is a failing run) = 0.199
      -> SEARCH (it has not found the code yet -- supply a location hint)

  ground truth: reward=0 -> LOST
```

`--list` gives the run ids; `y=1` means WRONG-FIX, `y=0` means LOST.

## What is and is not claimed

- Trained and evaluated on **SWE-agent runs** (the Nebius SWE-agent trajectory corpus), split into
  three disjoint shard sets of ~26,700 runs each. Labels come from the dataset's own gold patch.
- The router read only the first *f* of the run (`f` = 0.10 / 0.20 / 0.40 / 0.60). The run's own
  length appears in no feature; `analyse_route_modes.py --selftest` proves that mechanically by
  corrupting every post-checkpoint step and asserting the features are unchanged.
- **Not claimed: generality across scaffolds.** A model trained on SWE-agent scores 0.319–0.495 on
  88,000 runs from three other scaffolds, versus 0.653–0.761 for the same features fitted inside
  those scaffolds. See `results/rebuild/router_xscaffold.json`. The transfer that holds is
  shard-level, not scaffold-independent.
- The demo's `--live` view reports recorded outcomes, not router scores: live episodes are stored as
  transcripts, and the bridge from transcript to per-step features is documented, with its limits,
  in `research/scripts/analyse_router_live.py`.
