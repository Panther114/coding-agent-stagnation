"""Generate the probe_numbers.json the paper's new limitation macros read from.

Collects the numbers established by the v2 rebuild probes into one frozen artifact, so the paper
never hand-types them.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np

OUT = "results/final/v2/probe_numbers.json"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

SUCCESS = [
    re.compile(r"<returncode>\s*0\s*</returncode>", re.I),
    re.compile(r"\b(?:all\s+)?\d+\s+passed\b", re.I),
    re.compile(r"\btests? (?:passed|ok)\b", re.I),
    re.compile(r"build (?:succeeded|complete|completed successfully)", re.I),
]
PYTEST = re.compile(r"\b(?:all\s+)?\d+\s+passed\b", re.I)
BUILD = re.compile(r"build (?:succeeded|complete|completed successfully)", re.I)

runs = []
for line in open("data/processed/tb2/sample_trajectories.jsonl", encoding="utf-8"):
    t = json.loads(line)
    obs = [s.get("obs") or "" for s in t["steps"]]
    if not obs:
        continue
    runs.append({"reward": t["reward"], "obs": obs})

print(f"runs: {len(runs)}")


def n_ev(obs, pats):
    return sum(1 for o in obs if any(p.search(o) for p in pats))


no_event = sum(1 for r in runs if n_ev(r["obs"], SUCCESS) == 0)
pytest_runs = sum(1 for r in runs if any(PYTEST.search(o) for o in r["obs"]))
build_runs = sum(1 for r in runs if any(BUILD.search(o) for o in r["obs"]))

fail = [n_ev(r["obs"], SUCCESS) for r in runs if r["reward"] != 1]
pass_ = [n_ev(r["obs"], SUCCESS) for r in runs if r["reward"] == 1]

# within-run flip rate at K=3, on runs with >= 2 events
flips = []
for r in runs:
    n = len(r["obs"])
    if n < 15:
        continue
    ev = [any(p.search(o) for p in SUCCESS) for o in r["obs"]]
    if sum(ev) < 2:
        continue
    nxt = None
    g = [None] * n
    for i in range(n - 1, -1, -1):
        if ev[i]:
            nxt = i
        g[i] = None if nxt is None else nxt - i
    y = [1 if (x is not None and x <= 3) else 0 for x in g]
    flips.append(sum(1 for i in range(1, n) if y[i] != y[i - 1]) / max(1, n - 1))

# per-feature AUCs from the representation swap
up = json.load(open("results/final/v2/embedding_upgrade_test.json", encoding="utf-8"))
feat = up.get("per_feature", {})

out = {
    "runs_no_event_pct": f"{100*no_event/len(runs):.0f}",
    "runs_pytest_pct": f"{100*pytest_runs/len(runs):.0f}",
    "runs_build_pct": f"{100*build_runs/len(runs):.0f}",
    "events_fail_mean": f"{np.mean(fail):.1f}" if fail else "--",
    "events_pass_mean": f"{np.mean(pass_):.1f}" if pass_ else "--",
    "flips_k3": f"{np.mean(flips):.2f}" if flips else "--",
    "runs_with_two_events": len(flips),
    "feat_diversity": f"{feat.get('sem_diversity', float('nan')):.2f}",
    "feat_nearest": f"{feat.get('sem_nearest_sim', float('nan')):.2f}",
}
json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2)
print(json.dumps(out, indent=2))
print(f"\nwrote {OUT}")
