# Human pilot results — 12 blind windows, one independent reader

**Committed:** verdicts in chat 2026-09-13 (4 progress / 8 stalled), transcribed verbatim to
`docs/human_check_blind/judge.csv` (commit `8e4ef00`, key unopened at commit time).
**Scored once** with `scripts/score_human_sample_ci.py` (5000 bootstraps, seed 7):
`results/rebuild/human_check_blind_scored.json` (commit `ba34d03`).

## Headline (report intervals, never points — pre-reg)

| comparison | raw | 95% Wilson | κ | κ boot95 |
|---|---|---|---|---|
| human vs stored judgement | 10/12 (83.3%) | [55.2%, 95.3%] | +0.667 | [+0.226, +1.000] |
| human vs mechanical | 6/12 (50.0%) | [25.4%, 74.6%] | +0.100 | [−0.333, +0.526] |
| stored vs mechanical (same 12) | 8/12 (66.7%) | [39.1%, 86.2%] | — | — |

Difference (mech − stored): −0.333, boot95 [−0.583, −0.083]; McNemar b=0 (mech-only) / c=4
(stored-only), exact p=0.125. Stagnant rates: human 66.7% > stored 50.0% > mechanical 33.3% —
the reader is strictest, telemetry most lenient.

## Pre-reg verdicts

- **Falsification rule NOT triggered by the letter:** human–mechanical point is 50.0% (rule: <50%),
  and its CI [25%, 75%] contains the 66.7% sanity rate. But it sits exactly on the boundary —
  one window worse trips it. Report as "at the falsification boundary", not as comfort.
- **Hoped-for direction reversed:** the pre-reg asked whether mechanical would be *clearly higher*
  than stored. It is lower by 4 windows (−0.333). The bootstrap interval excludes zero but McNemar
  is n.s. (p=0.125, n=12) — call it suggestive, not conclusive.
- **Claim 1 (codebook fidelity):** AI-reader judgements reproduce this human's codebook reading
  substantially (κ≈0.67, lower bound 0.23). The codebook transfers from AI to human application.
- **Claim 2 (mechanical validity):** "workspace moved" agrees with a human at chance level
  (κ≈0.10, interval covers zero and goes negative). Telemetry is not validated as a progress
  measure by this pilot.

## Disagreement anatomy (the actual result — 6 rows)

**Human + stored vs mechanical (4 rows: McNemar c=4, all favour the readers):**

| row | window | human/stored | mechanical (quiet) | reading |
|---|---|---|---|---|
| B02 | crack-7z-hash t=27 | STAGNANT | productive (0.00!) | Zero-quiet window both call stall: wordlist creation + timed-out john runs + doc re-reads + blind guesses move the workspace every step while advancing nothing. Movement ≠ progress — the rebuild's central worry, confirmed by two independent readings. |
| B06 | compile-compcert t=60 | STAGNANT | productive (0.50) | 404s + repeated bash syntax errors; something changed, nothing learned. Same lesson. |
| B09 | feal-linear t=12 | STAGNANT | productive (0.30) | Infeasible brute force + interrupt-sending to a hung process; workspace churn without E/I/V. |
| B07 | git-leak-recovery t=39 | PRODUCTIVE | STAGNANT (0.80) | Opposite error: a genuinely durable change (history rewritten, secret purged, step 38) the telemetry calls quiet. Mechanical false *negative* — the single most important row for the paper's limitations. |

**Human vs both refs (2 rows — the reader's "too strict" self-flag):**

| row | window | human | both refs | reading |
|---|---|---|---|---|
| B05 | make-doom t=24 | STAGNANT | productive | Reads-only exploration (platform variants listed step 19, my_stdlib hunt 20–23). Readers credit E-channel; human credits nothing durable. This is the documented epistemic-value-of-exploration boundary dispute (`KEY_FINDINGS.md` §4 item 3, break-filter-js case) — a codebook ambiguity, not a reader error on either side. |
| B11 | install-windows t=9 | STAGNANT | productive | Steps 0–9: QEMU-not-found (exit 127, arguably a new error signature = E), env exploration, notes. Readers credit early localisation; human sees meta-prompts with no installs/services (those land steps 11+, outside the window). Heavy `$NN` redaction hides how much was actually learned — plausibly redaction-driven. |

## Strictness sensitivity (post hoc, labelled as such)

Flipping B05 + B11 to progress (the lenient re-read): human–stored → 12/12, human–mechanical →
8/12 (66.7% = exactly the stored–mechanical rate). The 4-row core (B02/B06/B09/B07, where
humans side with readers over telemetry on thrash-vs-movement) **survives the adjustment** —
the conclusion does not rest on the two strict calls.

## Sentences the paper may use

- "On 12 enriched blind windows, an independent codebook reading agreed with the stored
  AI-reader judgements on 10/12 (95% CI 55–95%, κ=0.67) and with the mechanical quiet-share
  target on 6/12 (CI 25–75%, κ=0.10); the paired difference is −0.33 (boot95 [−0.58, −0.08],
  McNemar p=0.13)."
- "All four human–stored agreements against telemetry are thrash-called-productive by movement
  (quiet 0.00–0.50) or patience-called-quiet (a history rewrite at quiet 0.80); both directions
  of mechanical error appear."
- "No gross invalidation (falsification rule not triggered), but no validation either: telemetry
  sits at the falsification boundary and at chance agreement with a human reader."

## Limits (unchanged from pre-reg)

n=12 enriched 50/50; single rater, no human–human ceiling; TB2-only; Wilson widths ±25–30 pts.
This is a falsification pilot, not a validation study.
