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
    """The paper may write a rate as 0.550, 0.5504 or 55.0% -- all the same number.

    Only these exact renderings count; this is not a fuzzy match, so a wrong decimal still fails.
    """
    if quoted in tex:
        return True
    if isinstance(value, (int, float)):
        if f"{float(value):.4f}" in tex:
            return True
        if 0.0 <= float(value) <= 1.0 and pct(value) in tex:
            return True
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

# --- live experiment (every condition, valid episodes only) ---
live48 = load(LIVE / "live_arms_valid.json")
for arm in ("hinted", "unhinted", "masked", "verify", "nudge"):
    a = (live48.get("per_arm") or {}).get(arm)
    if not a:
        continue
    chk(f"live {arm} success", a["success"], P(a["success"]))
    chk(f"live {arm} reached gold", a["reached_gold"], P(a["reached_gold"]))
# the pairwise tests the report actually quotes (the rest exist in the artifact; requiring the
# prose to enumerate all ten pairs would be noise, not verification)
REPORTED_PAIRS = ("hinted_vs_masked", "masked_vs_verify", "hinted_vs_unhinted",
                  "unhinted_vs_verify", "nudge_vs_unhinted", "nudge_vs_verify",
                  "masked_vs_unhinted")
for pair, p in (live48.get("pairwise") or {}).items():
    if pair not in REPORTED_PAIRS:
        continue
    chk(f"live p {pair.replace('_', ' ')}", p["p_fisher_two_sided"],
        f"{p['p_fisher_two_sided']:.3f}")
chk("live n raw", live48["n_raw"], str(live48["n_raw"]))
chk("live n dropped", live48["n_dropped_fail_before_false"],
    str(live48["n_dropped_fail_before_false"]))

# --- the router applied to the live runs (a negative) ---
dep = load(LIVE / "live_router_deployment.json")
chk("live router deployed AUC", dep["fractions"]["0.2"]["auc_router"],
    P(dep["fractions"]["0.2"]["auc_router"]))
chk("live router best baseline", max(dep["fractions"]["0.2"]["baselines"].values()),
    P(max(dep["fractions"]["0.2"]["baselines"].values())))

# --- cross-set transfer (the headline #5 numbers) ---
# The paper's transfer table quotes the verdict block of route_modes_transfer.json directly, plus
# the four directional cells at the deployed 0.20 checkpoint.  Adding these checks is what caught
# an earlier version of the table that quoted numbers appearing in the artifact only by accident.
xfer = load(RES / "route_modes_transfer.json")
for tgt, key in (("y_fail", "failure"), ("y_wrong_fix", "mode")):
    v = xfer["verdict"][tgt]
    for name, field in (("within", "within_own_rates_mean"), ("cross", "cross_own_rates_mean"),
                        ("worst cell", "cross_own_rates_min"),
                        ("position", "cross_position_mean"), ("agentstop", "cross_agentstop_mean")):
        chk(f"transfer {key} {name}", v[field], P(v[field]))
    chk(f"transfer {key} gain", v["own_minus_agentstop"],
        f"+{v['own_minus_agentstop']:.4f}")
    c20 = xfer["targets"][tgt]["0.2"]["cross"]
    for pair in ("A_shards0_3->B_shards4_7", "A_shards0_3->C_shards8_11",
                 "B_shards4_7->A_shards0_3", "C_shards8_11->B_shards4_7"):
        chk(f"transfer {key} {pair.split('->')[0][:1]}->{pair.split('->')[1][:1]} @0.20",
            c20[pair]["own_rates"], P(c20[pair]["own_rates"]))
chk("transfer n cross cells", 24, "24")

# --- cross-scaffold transfer (the negative result) ---
xsc = load(RES / "router_xscaffold.json")
for name, c in xsc["corpora"].items():
    v = c["variants"]["bridgeable"]["0.20"]
    chk(f"{name} transferred AUC", v["auc_router"], P(v["auc_router"]))
    chk(f"{name} in-target OOF", v["in_target_oof_auc"], P(v["in_target_oof_auc"]))

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
