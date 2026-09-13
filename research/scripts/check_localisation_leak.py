"""Why did every live run find the right file?  Check what the test output reveals.

The 48-task live experiment found the gold file in 100% of runs, which made the router's SEARCH
branch untestable.  The hypothesis is that the verifier itself gives the location away: pytest
prints the failing test's node id, and the test file imports the buggy module, so the agent can
read the answer off the failure message without diagnosing anything.

This checks that against real episode transcripts before any experiment is built on it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "results" / "live"
sys.stdout.reconfigure(encoding="utf-8")

p = LIVE / "episodes48.jsonl"
recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"episodes: {len(recs)}")

# what does the agent see when it runs the tests?
shown = 0
names_module = 0
total_tests = 0
for r in recs:
    for t in r.get("transcript", []):
        if t.get("cmd") != "test":
            continue
        obs = str(t.get("obs") or "") + str(t.get("obs_full") or "")
        total_tests += 1
        gold = str(r.get("gold_file") or "")
        stem = Path(gold).stem
        if stem and stem in obs:
            names_module += 1
        if shown < 3 and obs.strip():
            print("\n--- test observation seen by the agent ---")
            print(obs[-700:])
            shown += 1
print(f"\ntest observations: {total_tests}")
print(f"  ...that literally name the gold module: {names_module} "
      f"({names_module / max(total_tests,1):.1%})")

# does the FIRST failing node id name the module?
pat = re.compile(r"(?:FAILED|ERROR)\s+(\S+)")
first_hit = 0
n = 0
for r in recs:
    for t in r.get("transcript", []):
        if t.get("cmd") != "test":
            continue
        obs = str(t.get("obs") or "") + str(t.get("obs_full") or "")
        m = pat.search(obs)
        n += 1
        if m:
            node = m.group(1)
            if Path(node.split("::")[0]).stem.replace("test_", "") in Path(
                    str(r.get("gold_file") or "")).stem or \
               Path(str(r.get("gold_file") or "")).stem in node:
                first_hit += 1
        break
print(f"  episodes whose first test obs exposes a node id tied to the gold module: "
      f"{first_hit}/{n}")

print("""
What this means for the experiment:
  If the test output names the module, then localisation is a string-match task, not a diagnostic
  one.  To test the router's SEARCH branch the verifier must stop giving the location away -- the
  agent should be told *that* tests fail, not *where*.  That is the 'masked' condition.
""")
