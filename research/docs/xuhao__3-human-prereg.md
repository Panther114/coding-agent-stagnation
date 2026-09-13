# Pre-registration — 12-window blind human pilot

**Frozen:** 2026-09-13 · **Sample:** 12 windows, enriched 6 stored-STAGNANT + 6 stored-PRODUCTIVE
(seed 20260913), blind order reshuffled seed 20260914 (`docs/human_check_blind/`).
On-sample stored-vs-mechanical agreement 66.7% matches the 386-window population (66.9%, AUC 0.669),
so the sample is representative, not cherry-picked.

## Estimands (on the scored set: blocked-external / uncertain excluded, counts reported)

1. `human vs stored` raw agreement + Wilson 95% CI; Cohen's κ + bootstrap 95% CI.
2. `human vs mechanical` raw agreement + Wilson 95% CI; Cohen's κ + bootstrap 95% CI.
3. `stored vs mechanical` on the same scored set (sanity: expect ~67%).
4. Paired difference (mech − stored) + bootstrap 95% CI; McNemar exact p on discordant cells
   (mech-only b vs stored-only c).

## Decision rules (all must be reported; none may be softened post hoc)

- **Falsification (the pilot's power):** if `human vs mechanical` point agreement <50%, or its
  Wilson CI lies entirely below the stored-vs-mechanical sanity rate, the mechanical target is
  **grossly invalidated** — every number above it changes. Stop and report.
- **Non-validation (the pilot's limit):** with n≤12, Wilson widths are ~±25–30 pts and κ CIs span
  ~0.6 (verified: synthetic 9/12 gives diff CI [−0.17, +0.50], McNemar p=0.625). Therefore a
  1–2 window lead (e.g. 75% vs 58%) is **noise, not a win**. Never write "validated at X%".
- **Allowed positive language:** only "no gross invalidation on 12 enriched windows; disagreements
  were [list with step cites]" plus intervals. The value is the disagreement analysis, not the headline.
- **Exclusions:** report n_excluded with blind_ids + verdicts. If exclusions >3/12, the pilot is
  inconclusive by design (enrichment broken) — report as such.

## Analysis plan

Run once, after commitment: `score_human_sample_ci.py --judge <filled judge.csv> --key key/sealed_key.csv`.
Quote all four rows (points + CIs + κ + diff + McNemar), stagnant rates, and the per-row reason table.
One analysis, no peeking, no re-scoring after key open. Pre-reg violation = pilot void.
