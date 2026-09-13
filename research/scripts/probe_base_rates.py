"""Base rates: how many runs even contain verified success events?

Both candidate targets collapsed to whole-run properties.  Before choosing a third, establish the
base rate of the underlying events, because if events are absent from most runs no within-run
target can work on this corpus.
"""
from __future__ import annotations

import collections
import json
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding="utf-8")

PATTERNS = {
    "exit0": re.compile(r"<returncode>\s*0\s*</returncode>", re.I),
    "exit0_kw": re.compile(r"\{exit=0\}"),
    "pytest_all_pass": re.compile(r"\b\d+\s+passed\b", re.I),
    "tests_ok": re.compile(r"\btests? (?:passed|ok)\b", re.I),
    "build_ok": re.compile(r"build (?:succeeded|complete|completed successfully)", re.I),
}
PROC = "data/processed/tb2/sample_trajectories.jsonl"

runs = []
for line in open(PROC, encoding="utf-8"):
    t = json.loads(line)
    obs = [s.get("obs") or "" for s in t["steps"]]
    redacted = sum(1 for o in obs if re.fullmatch(r"\$[A-Za-z0-9]{1,4}", o.strip()))
    runs.append({"tid": t["traj_id"], "reward": t["reward"], "n": len(obs), "obs": obs,
                 "red": redacted})

print(f"runs: {len(runs)}; steps: {sum(r['n'] for r in runs)}")
print(f"redacted steps: {sum(r['red'] for r in runs)} "
      f"({100*sum(r['red'] for r in runs)/max(1,sum(r['n'] for r in runs)):.1f}%)")

print("\nevent counts per pattern, and how many runs contain at least one:")
for name, pat in PATTERNS.items():
    per_run = [sum(1 for o in r["obs"] if pat.search(o)) for r in runs]
    any_run = sum(1 for c in per_run if c)
    print(f"  {name:16} events={sum(per_run):6d}  runs_with_any={any_run:5d} "
          f"({100*any_run/len(runs):4.0f}%)")

# combined
def n_events(obs):
    return sum(1 for o in obs if any(p.search(o) for p in PATTERNS.values()))

counts = [n_events(r["obs"]) for r in runs]
print(f"\ncombined success events: {sum(counts)} across {len(runs)} runs")
print(f"  runs with 0 events : {sum(1 for c in counts if c == 0)} "
      f"({100*sum(1 for c in counts if c==0)/len(runs):.0f}%)")
print(f"  runs with 1-2      : {sum(1 for c in counts if 1 <= c <= 2)}")
print(f"  runs with >=3      : {sum(1 for c in counts if c >= 3)}")
print(f"  runs with >=5      : {sum(1 for c in counts if c >= 5)}")

print("\nmedian events per run by outcome:")
for lab, sel in (("reward=1 (solved)", [c for c, r in zip(counts, runs) if r["reward"] == 1]),
                 ("reward=0 (failed)", [c for c, r in zip(counts, runs) if r["reward"] != 1])):
    if sel:
        print(f"  {lab:18} n={len(sel):5d}  median={st.median(sel):5.0f}  mean={st.mean(sel):6.1f}")

# the redaction interaction: do redacted steps hide the events?
print("\nare events hidden by redaction? runs binned by redaction rate:")
for lo, hi in ((0, 0.1), (0.1, 0.3), (0.3, 0.6), (0.6, 1.01)):
    sel = [r for r in runs if lo <= (r["red"] / max(1, r["n"])) < hi]
    if not sel:
        continue
    ev = [n_events(r["obs"]) / max(1, r["n"]) for r in sel]
    print(f"  redaction {lo:.0%}-{hi:.0%}: {len(sel):4d} runs, "
          f"events per step {st.mean(ev):.3f}")
