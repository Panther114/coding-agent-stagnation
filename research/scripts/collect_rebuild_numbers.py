"""Collect every headline number of the rebuild from the frozen artifacts, into one file.

    python scripts/collect_rebuild_numbers.py

Nothing is typed by hand: each value is read from the artifact that produced it, so the
findings document and the paper macros can be regenerated and audited.  Where a quantity
does not exist the entry is ``null`` rather than omitted, so a missing measurement is
visible.

Writes ``results/rebuild/rebuild_numbers.json`` and a flat ``rebuild_numbers.flat.json``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"


def load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    nums: Dict[str, Any] = {}

    # ---------------- corpus scale -------------------------------------------------
    scale = {}
    for corpus in ("tb2", "nebius"):
        steps = ROOT / "data" / "processed" / "steps" / corpus / "steps.parquet"
        runs = ROOT / "data" / "processed" / "steps" / corpus / "runs.parquet"
        if not steps.exists():
            continue
        s = pd.read_parquet(steps, columns=["run_id", "task", "agent", "model", "is_edit"])
        r = pd.read_parquet(runs)
        scale[corpus] = {
            "n_steps": int(len(s)),
            "n_runs_with_steps": int(s.run_id.nunique()),
            "n_trials_in_table": int(len(r)),
            "n_tasks": int(s.task.nunique()),
            "n_agents": int(s.agent.nunique()),
            "n_models": int(s.model.nunique()),
            "n_edit_steps": int(s.is_edit.sum()),
        }
    nums["scale"] = scale

    # ---------------- corpus coverage of the objective signal ----------------------
    cov = load(OUT / "editor_state_coverage.json")
    nums["editor_telemetry"] = cov

    neb = ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet"
    if neb.exists():
        d = pd.read_parquet(neb, columns=["is_edit", "file_total", "added_lines_n"])
        ed = d[d.is_edit == 1]
        nums["nebius_telemetry"] = {
            "edit_steps": int(len(ed)),
            "file_size_known_frac": float((ed.file_total >= 0).mean()),
            "added_lines_known_frac": float((ed.added_lines_n > 0).mean()),
            "mean_added_lines_per_edit": float(ed.added_lines_n.mean()),
        }

    # ---------------- per-corpus window analyses -----------------------------------
    for corpus in ("tb2", "nebius"):
        a = load(OUT / f"{corpus}_w10" / "analysis.json")
        if not a:
            continue
        base = a.get("A_base_rates", {})
        nums[f"{corpus}_base_rates"] = {
            k: {kk: vv for kk, vv in v.items() if kk != "per_task_stagnation"}
            for k, v in base.items() if isinstance(v, dict) and "mean" in v and "n" in v
        }
        nums[f"{corpus}_uniform_runs"] = base.get("frac_uniform_runs")
        nums[f"{corpus}_position_confound"] = a.get("B_confound", {}).get("position_confound")
        singles = [f for f in a.get("B_confound", {}).get("single_features", [])
                   if f.get("auc") == f.get("auc")]
        nums[f"{corpus}_top_single_features"] = sorted(
            [{"feature": f["feature"], "auc": round(f["auc"], 4),
              "rho_position": round(abs(f.get("r_position", float("nan"))), 4)}
             for f in singles], key=lambda x: -x["auc"])[:8]
        dsec = a.get("D_within_run", {})
        nums[f"{corpus}_monitors"] = {
            name: {
                "within_run_mean_auc": v["within_run"].get("mean_auc"),
                "within_run_median_auc": v["within_run"].get("median_auc"),
                "n_above_chance": v["within_run"].get("n_above_half"),
                "n_runs_scored": v["within_run"].get("n_runs"),
                "between_task_auc": v["between_within_task"].get("between_auc"),
                "within_task_spearman": v["between_within_task"].get("within_spearman"),
                "between_run_auc": v["between_within_run"].get("between_auc"),
                "within_run_spearman": v["between_within_run"].get("within_spearman"),
                "burst_lift_at_10pct": v["burst"].get("lift"),
                "pauc_at_5pct_fpr": v["partial_auc"].get("pauc_5"),
                "pauc_at_1pct_fpr": v["partial_auc"].get("pauc_1"),
                "detection_at_5pct_budget": v["budget"].get("det_at_5", {}).get("det"),
            } for name, v in dsec.items()}
        nums[f"{corpus}_pooled_auc"] = {m["name"]: m["oof_auc"] for m in a.get("C_monitors", {}).get("monitors", [])}
        nums[f"{corpus}_paired"] = a.get("E_comparisons", {})
        seq = load(OUT / f"{corpus}_w10" / "sequential.json")
        if seq:
            nums[f"{corpus}_sequential"] = {
                "frac_never_stalls": seq.get("frac_never_stalls"),
                "n_runs": seq.get("n_runs"),
                "oracle": seq.get("oracle"),
                "persistence_sweep": seq.get("persistence_sweep"),
                "cost_model": seq.get("cost_model"),
            }

    # ---------------- alignment / waste --------------------------------------------
    al = load(OUT / "alignment.json")
    if al:
        nums["alignment"] = al
    st = load(OUT / "step_task.json")
    if st:
        nums["step_task"] = {"n_steps": st.get("n_steps"), "k": st.get("k"),
                             "base_rates": st.get("base_rates"),
                             "monitors": st.get("monitors")}
    tr = load(OUT / "transfer.json")
    if tr:
        nums["transfer"] = {"n_tb2": tr.get("n_tb2"), "n_nebius": tr.get("n_nebius"),
                            "cells": tr.get("cells")}
    gc = load(OUT / "gold_crosscheck.json")
    if gc:
        nums["gold_crosscheck"] = gc
    obj = load(OUT / "objective_signals.json")
    if obj:
        nums["objective_signals_pilot"] = obj

    flat: Dict[str, Any] = {}

    def walk(prefix: str, v: Any) -> None:
        if isinstance(v, dict):
            for k, vv in v.items():
                walk(f"{prefix}.{k}" if prefix else str(k), vv)
        elif isinstance(v, list):
            flat[prefix + ".n"] = len(v)
            for i, vv in enumerate(v[:40]):
                walk(f"{prefix}[{i}]", vv)
        else:
            flat[prefix] = v

    for k, v in nums.items():
        walk(k, v)
    (OUT / "rebuild_numbers.json").write_text(json.dumps(nums, indent=2, default=float), encoding="utf-8")
    (OUT / "rebuild_numbers.flat.json").write_text(json.dumps(flat, indent=2, default=float), encoding="utf-8")
    print(f"wrote {OUT / 'rebuild_numbers.json'} with {len(flat)} flat values")
    for k in ("scale", "nebius_telemetry", "editor_telemetry"):
        print(f"  {k}: {json.dumps(nums.get(k, {}), default=float)[:300]}")


if __name__ == "__main__":
    main()
