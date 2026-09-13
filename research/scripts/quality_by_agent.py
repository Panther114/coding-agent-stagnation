"""Per-agent / per-task data-quality confound check."""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")

import loaders  # noqa: E402

PH = re.compile(r"^\$[0-9a-fA-F]{1,4}$")


def main():
    trajs = loaders.load_tb2()
    agg = collections.defaultdict(lambda: [0, 0.0, 0.0, 0, 0.0, 0])
    for t in trajs:
        a = agg[t.agent]
        a[0] += 1
        npl = sum(1 for s in t.steps if PH.match((s.observation or "").strip()))
        a[1] += npl / max(1, len(t.steps))
        msgs = [re.sub(r"\s+", " ", (s.text or "").strip()) for s in t.steps if (s.text or "").strip()]
        a[2] += (max(collections.Counter(msgs).values()) / len(msgs)) if msgs else 0.0
        a[3] += len(t.steps)
        a[4] += t.reward or 0
        notool = sum(1 for s in t.steps if not s.actions)
        a[5] += notool / max(1, len(t.steps))
    print(f"{'agent':<20}{'n':>7}{'ph_obs':>8}{'maxrep':>8}{'meansteps':>11}{'passrate':>10}{'notool':>8}")
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        print(f"{k:<20}{v[0]:7d}{v[1]/v[0]:8.3f}{v[2]/v[0]:8.3f}{v[3]/v[0]:11.1f}{v[4]/v[0]:10.3f}{v[5]/v[0]:8.3f}")


if __name__ == "__main__":
    main()
