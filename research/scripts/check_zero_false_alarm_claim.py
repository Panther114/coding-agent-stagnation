"""Which artifact actually contains the zero-false-alarm result?

HANDOFF, REBUILD_FINDINGS_V2 and GAP_ANALYSIS all attribute "0 false alarms from 1% to 20%
budgets at oracle-level recall" to ``waste_alarm.json`` / ``sustained_waste.json``.  Both were
regenerated and neither contains it: ``waste_alarm.json`` reports recall 0.331 at false alarms
0.009 and a median alarm at 100% of the run, and ``sustained_waste.json`` reports the degenerate
formulation at a 0.888 false-alarm rate.

This script searches every frozen artifact for a budget grid whose false-alarm rate is zero, so
the claim can be attributed to whatever actually produced it - or retired.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "rebuild"

FA_KEYS = re.compile(r'"(false_alarm[a-z_]*|fa[a-z_]*|fpr)"\s*:\s*([0-9.eE+-]+)')
BUDGET_KEYS = re.compile(r'"(budget|alpha|target_fa|max_fpr)"\s*:\s*([0-9.eE+-]+)')


def walk(node, path=""):
    if isinstance(node, dict):
        fas = {k: v for k, v in node.items()
               if isinstance(v, (int, float)) and re.fullmatch(r"false_alarm[a-z_]*|fa[a-z_]*|fpr", k)}
        buds = {k: v for k, v in node.items()
                if isinstance(v, (int, float)) and re.fullmatch(r"budget|alpha|target_fa|max_fpr", k)}
        if fas and buds:
            yield path, buds, fas
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


def main() -> None:
    found = {}
    for p in sorted(RES.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        recs = list(walk(d))
        zeros = [r for r in recs if all(abs(v) < 1e-9 for v in r[2].values())]
        grids = [r for r in recs if len(r[1]) >= 1 and len(r[2]) >= 1]
        if zeros:
            found[p.name] = {"n_budget_entries": len(grids),
                             "n_zero_fa": len(zeros),
                             "examples": [{"path": z[0], "budget": z[1], "fa": z[2]}
                                          for z in zeros[:3]]}
        if grids:
            print(f"{p.name}: {len(grids)} budget/FA entries, {len(zeros)} with zero FA")

    out = {
        "question": "does any frozen artifact contain '0 false alarms across 1-20% budgets "
                    "at oracle-level recall'?",
        "artifacts_with_zero_fa": found,
        "verdict": ("ATTRIBUTION ERROR: the artefacts named in the docs do not contain this "
                    "result" if not found else "found in: " + ", ".join(found)),
    }
    (RES / "zero_false_alarm_provenance.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n" + out["verdict"])
    if found:
        print(json.dumps(found, indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
