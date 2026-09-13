"""Audit the rewritten paper's headline numbers against the artifacts that produced them.

A compiled PDF is not evidence that its numbers are right. This reads the numbers out of
`paper/v2/main.tex` and compares each to the artifact it claims to come from, so the paper cannot
drift from the frozen results the way an earlier executive summary did.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT.parent / "paper" / "v2" / "main.tex"
RES = ROOT / "results" / "rebuild"
LIVE = ROOT / "results" / "live"

tex = PAPER.read_text(encoding="utf-8")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


wrong = load(RES / "wrongness.json")["corpora"]["nebius"]
repl = load(RES / "wrongness_repl.json")["corpora"]["nebius"]
repl2 = load(RES / "wrongness_repl2.json")["corpora"]["nebius"]
artifact = load(RES / "route_modes.json")
live48 = load(LIVE / "live_experiment48_valid.json")
xs = load(RES / "xscaffold_replication.json")

P = lambda x: f"{float(x):.3f}"
checks = []


def pct(x):
    """The same quantity written as a percentage, for prose that uses '%'."""
    return f"{100 * float(x):.1f}"


def contains_quantity(quoted, value):
    """The paper may write a rate as 0.550 or as 55.0% -- both are the same number.

    Only these two exact renderings are accepted; this is not a fuzzy match, so a wrong
    decimal still fails the audit.
    """
    if quoted in tex:
        return True
    if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0:
        return pct(value) in tex
    return False


def chk(label, expected, quoted):
    present = contains_quantity(quoted, expected)
    checks.append((label, expected, quoted, present))


# --- measurement validity (frozen) ---
chk("on_target_self solved", wrong["pooled_on_target_self"]["solved"],
    P(wrong["pooled_on_target_self"]["solved"]))
chk("on_target_self failed", wrong["pooled_on_target_self"]["failed"],
    P(wrong["pooled_on_target_self"]["failed"]))
chk("on_target_gold solved", wrong["pooled_on_target_gold"]["solved"],
    P(wrong["pooled_on_target_gold"]["solved"]))
chk("on_target_gold failed", wrong["pooled_on_target_gold"]["failed"],
    P(wrong["pooled_on_target_gold"]["failed"]))
chk("wrong-fix share", wrong["failure_decomposition"]["frac_wrong_fix"],
    f"{100 * wrong['failure_decomposition']['frac_wrong_fix']:.1f}")
chk("ever touched gold solved", wrong["pooled_ever_touched_gold"]["solved"],
    P(wrong["pooled_ever_touched_gold"]["solved"]))
chk("ever touched gold failed", wrong["pooled_ever_touched_gold"]["failed"],
    P(wrong["pooled_ever_touched_gold"]["failed"]))

# --- held-out replication ---
chk("repl gold solved", repl["pooled_on_target_gold"]["solved"],
    P(repl["pooled_on_target_gold"]["solved"]))
chk("repl gold failed", repl["pooled_on_target_gold"]["failed"],
    P(repl["pooled_on_target_gold"]["failed"]))
chk("repl wrong-fix share", repl["failure_decomposition"]["frac_wrong_fix"],
    f"{100 * repl['failure_decomposition']['frac_wrong_fix']:.1f}")
chk("repl2 gold solved", repl2["pooled_on_target_gold"]["solved"],
    P(repl2["pooled_on_target_gold"]["solved"]))
chk("repl2 gold failed", repl2["pooled_on_target_gold"]["failed"],
    P(repl2["pooled_on_target_gold"]["failed"]))
chk("repl2 wrong-fix share", repl2["failure_decomposition"]["frac_wrong_fix"],
    f"{100 * repl2['failure_decomposition']['frac_wrong_fix']:.1f}")

# --- live experiment ---
chk("live hinted success", live48["arms"]["hinted"]["success"],
    P(live48["arms"]["hinted"]["success"]))
chk("live unhinted success", live48["arms"]["unhinted"]["success"],
    P(live48["arms"]["unhinted"]["success"]))
chk("live significance p", live48["significance_hinted_vs_unhinted"]["p_fisher_two_sided"],
    f"{live48['significance_hinted_vs_unhinted']['p_fisher_two_sided']:.3f}")

# --- cross-scaffold ---
for name, c in xs.get("corpora", {}).items():
    tx = c.get("taxonomy") or {}
    if "dead_end_rate" in tx:
        chk(f"{name} dead_end", tx["dead_end_rate"], P(tx["dead_end_rate"]))

bad = [c for c in checks if not c[3]]
for label, expected, quoted, present in checks:
    print(f"  {'ok  ' if present else 'MISS'} {label:34s} artifact={P(expected) if isinstance(expected,(int,float)) else expected:<8} quoted={quoted}")
print()
print(f"{len(checks) - len(bad)}/{len(checks)} paper numbers trace to an artifact")
if bad:
    print("MISSING FROM PAPER:")
    for b in bad:
        print("  -", b[0], "->", b[2])
