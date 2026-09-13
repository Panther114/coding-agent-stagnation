# Your task: judge 12 windows (~40 minutes)

We need the one thing only a person can do — decide, for 12 fixed agent trajectories, whether the
agent had stalled or was still making progress.

1. Open `windows_to_judge.csv`.
2. For each of the 12 rows, open the card file named in the `card` column. Each card is
   self-contained: the task the agent was given, the steps leading up to the window, and the
   window itself.
3. Write `stalled` or `progress` in the `your_verdict` column.
4. Send the completed CSV back.

## The one rule

Commit to all 12 verdicts **before** looking at anything else about these runs — no other file in
this repo, no comments, no results. The value of the exercise is entirely in your reading being
independent. If you do peek at something, just say so; that's recoverable, a hidden peek is not.

## What it is for

Your verdicts produce two numbers the paper cannot currently state: how well the AI-written
codebook agreed with a person, and whether the mechanical "the workspace did not move" label
matches a human reading. If the second is clearly higher than the first, the study's label is
validated by human judgement rather than by assumption.

Twelve windows cannot validate 236,137 labels. What they can do is show whether the definition
agrees with a person at all — and if it systematically does not, the label is wrong and every
number above it changes. That is why this is worth doing properly.

Background, to read *after* you have committed to your verdicts: `research/docs/human_check_sample.md`.
