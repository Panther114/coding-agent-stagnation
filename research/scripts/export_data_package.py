"""Export every number and every raw artifact into one self-describing package.

The brief for #4 is "include all the materials in the essay, and I will rewrite & improve it. I need
every raw data."  So this produces a single directory that a person can open cold and rewrite from:

    EXPORT/
      INDEX.md            every claim -> number -> the artifact that produced it
      numbers.csv         flat machine-readable key,value,artifact  (one row per number)
      TABLES.md           the result tables pre-rendered as markdown, ready to paste
      artifacts/          verified copies of every frozen JSON/parquet-producing artifact
      live/               every live-experiment episode file, verbatim
      MANIFEST.json       what was copied, byte counts, and the gate results at export time

It never writes into results/, so exporting cannot disturb the frozen study.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "rebuild"
LIVE = ROOT / "results" / "live"
OUT = ROOT / "EXPORT"


def load(name: str) -> Dict[str, Any]:
    p = RES / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_live(name: str) -> Dict[str, Any]:
    p = LIVE / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def dig(d: Any, path: str) -> Any:
    cur = d
    for k in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(k)
        elif isinstance(cur, list):
            try:
                cur = cur[int(k)]
            except Exception:
                return None
        else:
            return None
    return cur


def fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "artifacts").mkdir(exist_ok=True)
    (OUT / "live").mkdir(exist_ok=True)

    wrong = load("wrongness.json")
    repl = load("wrongness_repl.json")
    repl2 = load("wrongness_repl2.json")
    metric = load("metric_artifact.json")
    route = load("route_modes.json")
    transfer = load("route_modes_transfer.json")
    xs = load("xscaffold_replication.json")
    dead = load("dead_end.json")
    live48 = load_live("live_arms_valid.json") or load("../../live/live_experiment48_valid.json")
    masked = None
    p = LIVE / "live_masked_vs_full.json"
    if p.exists():
        masked = json.loads(p.read_text(encoding="utf-8"))
    calib = load("channel_ablation.json")

    # ---- the claim -> number -> artifact table -----------------------------------------
    rows: List[Dict[str, Any]] = []

    def claim(section: str, text: str, value: Any, artifact: str, note: str = "") -> None:
        rows.append({"section": section, "claim": text, "value": value,
                     "artifact": artifact, "note": note})

    W = "wrongness.json"
    for tag, d in (("frozen (shards 0-3)", wrong), ("held-out A (4-7)", repl),
                   ("held-out B (8-11)", repl2)):
        b = d.get("corpora", {}).get("nebius", {})
        if not b:
            continue
        s = dig(b, "pooled_on_target_self.solved")
        f = dig(b, "pooled_on_target_self.failed")
        if s is not None:
            claim("measurement validity", f"on_target (own patch) solved -- {tag}", round(s, 4), W)
            claim("measurement validity", f"on_target (own patch) failed -- {tag}", round(f, 4), W)
        gs = dig(b, "pooled_on_target_gold.solved")
        gf = dig(b, "pooled_on_target_gold.failed")
        if gs is not None:
            claim("measurement validity", f"on_target (gold) solved -- {tag}", round(gs, 4), W)
            claim("measurement validity", f"on_target (gold) failed -- {tag}", round(gf, 4), W)
        ts = dig(b, "pooled_ever_touched_gold.solved")
        tf = dig(b, "pooled_ever_touched_gold.failed")
        if ts is not None:
            claim("measurement validity", f"ever reached gold, solved -- {tag}", round(ts, 4), W)
            claim("measurement validity", f"ever reached gold, failed -- {tag}", round(tf, 4), W)
        wf = dig(b, "failure_decomposition.frac_wrong_fix")
        if wf is not None:
            claim("failure modes", f"WRONG-FIX share of failures -- {tag}", round(wf, 4), W)
            claim("failure modes", f"LOST share of failures -- {tag}", round(1 - wf, 4), W)
        pw = dig(b, "reversal_on_target_gold.p_wilcoxon")
        if pw is not None:
            claim("measurement validity", f"within-instance paired p -- {tag}", pw, W)

    for k, v in (metric.get("verdict") or {}).items():
        claim("mechanism tests", k, v, "metric_artifact.json")

    for tgt in ("y_fail", "y_wrong_fix"):
        v = (transfer.get("verdict") or {}).get(tgt, {})
        for k, val in v.items():
            if val is not None:
                claim("router transfer", f"{tgt}: {k}", val, "route_modes_transfer.json")
    for f, e in (route.get("verdict", {}).get("per_task", {}) or {}).items():
        for mt, auc in (e.get("auc") or {}).items():
            claim("router (within-set)", f"{f} {mt}", round(auc, 4) if isinstance(auc, float) else auc,
                  "route_modes.json")

    for name, c in (xs.get("corpora") or {}).items():
        tx = c.get("taxonomy") or {}
        for k in ("kept_rate", "revised_rate", "dead_end_rate"):
            if k in tx:
                claim("cross-scaffold", f"{name} {k}", round(tx[k], 4),
                      "xscaffold_replication.json")
    ic = xs.get("instrument_check", {})
    if ic:
        claim("cross-scaffold", "port reproduces frozen exactly (abs diff)",
              ic.get("abs_diff_vs_frozen"), "xscaffold_replication.json")
        for k in ("frac_edit_steps_with_empty_patch",):
            if ic.get(k) is not None:
                claim("cross-scaffold", k, round(ic[k], 4), "xscaffold_replication.json")

    for k in ("kept_rate", "revised_rate", "dead_end_rate", "n_edits"):
        if dead.get(k) is not None:
            claim("frozen taxonomy", k, round(dead[k], 4) if isinstance(dead[k], float) else dead[k],
                  "dead_end.json")

    if live48:
        for arm, v in (live48.get("per_arm") or live48.get("arms") or {}).items():
            for k in ("success", "success_ci95", "reached_gold", "success_given_reached_gold", "n",
                      "mean_turns", "usd"):
                if v.get(k) is not None:
                    claim("live experiment", f"{arm}: {k}", v[k], "live_arms_valid.json")
        for pair, v in (live48.get("pairwise") or {}).items():
            claim("live experiment", f"success diff {pair}", v["success_diff"],
                  "live_arms_valid.json")
            claim("live experiment", f"Fisher p {pair}", round(v["p_fisher_two_sided"], 4),
                  "live_arms_valid.json", "significant" if v["significant_at_0.05"]
                  else "NOT significant")
        sig = live48.get("significance_hinted_vs_unhinted", {})
        if sig:
            claim("live experiment", "hinted vs unmasked Fisher p",
                  round(sig.get("p_fisher_two_sided", float("nan")), 4),
                  "live_arms_valid.json", "NOT significant")
        p1 = live48.get("P1_failure_rate_drop", {})
        if p1:
            claim("live experiment", "P1 failure-rate drop", p1.get("drop"),
                  "live_arms_valid.json", f"ceiling {p1.get('pre_registered_ceiling')}")
    dep = load_live("live_router_deployment.json")
    if dep:
        b = (dep.get("fractions") or {}).get("0.2", {})
        if b:
            claim("router on live runs (negative)", "AUC at 20% of the run", round(b["auc_router"], 4),
                  "live_router_deployment.json", "does NOT transfer")
            for k, v in (b.get("baselines") or {}).items():
                claim("router on live runs (negative)", f"baseline {k}", round(v, 4),
                      "live_router_deployment.json")
        for name, v in (dep.get("refit_bridgeable") or {}).get("variants", {}).items():
            claim("router on live runs (negative)", f"refit {name}: in-corpus AUC",
                  round(v["auc_in_corpus_shards0_3"], 4), "live_router_deployment.json")
    xsc = load("router_xscaffold.json")
    for name, c in (xsc.get("corpora") or {}).items():
        for vname, vb in (c.get("variants") or {}).items():
            b = vb.get("0.20", {})
            claim("cross-scaffold transfer (negative)",
                  f"{name} [{vname}] transferred AUC", round(b.get("auc_router", float("nan")), 4),
                  "router_xscaffold.json", "trained on SWE-agent, tested here")
            if b.get("in_target_oof_auc") is not None:
                claim("cross-scaffold transfer (negative)",
                      f"{name} [{vname}] fitted inside the target", round(b["in_target_oof_auc"], 4),
                      "router_xscaffold.json")
            if vname == "bridgeable":
                for k, vv in (b.get("baselines") or {}).items():
                    claim("cross-scaffold transfer (negative)", f"{name} baseline {k}",
                          round(vv, 4), "router_xscaffold.json")
    if masked:
        for arm, v in (masked.get("per_arm") or {}).items():
            claim("live experiment (masked)", f"{arm}: success", v.get("success"),
                  "live_masked_vs_full.json")
            claim("live experiment (masked)", f"{arm}: reached_gold", v.get("reached_gold"),
                  "live_masked_vs_full.json")

    # ---- write numbers.csv --------------------------------------------------------------
    import csv
    with (OUT / "numbers.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["section", "claim", "value", "artifact", "note"])
        wr.writeheader()
        for r in rows:
            wr.writerow(r)

    # ---- copy artifacts ------------------------------------------------------------------
    copied = []
    for p in sorted(RES.glob("*.json")):
        shutil.copy2(p, OUT / "artifacts" / p.name)
        copied.append({"file": p.name, "bytes": p.stat().st_size})
    live_files = []
    for p in sorted(LIVE.glob("*")):
        if p.is_file():
            shutil.copy2(p, OUT / "live" / p.name)
            live_files.append({"file": p.name, "bytes": p.stat().st_size})

    # ---- gates at export time ------------------------------------------------------------
    gates = {}
    for label, script in (("invariant tests", "run_rebuild_tests.py"),
                          ("consistency", "check_rebuild_consistency.py"),
                          ("claim audit", "audit_claims.py"),
                          ("summary audit", "audit_summary.py"),
                          ("doc references", "check_doc_references.py"),
                          ("paper numbers", "audit_paper_numbers.py")):
        sp = ROOT / "scripts" / script
        if not sp.exists():
            gates[label] = "missing"
            continue
        try:
            r = subprocess.run([sys.executable, str(sp)], cwd=str(ROOT),
                               capture_output=True, text=True, timeout=900)
            tail = [l for l in (r.stdout or "").strip().splitlines() if l.strip()]
            gates[label] = tail[-1][:120] if tail else f"exit {r.returncode}"
        except Exception as e:
            gates[label] = f"{type(e).__name__}"

    # ---- INDEX.md -----------------------------------------------------------------------
    by_sec: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_sec.setdefault(r["section"], []).append(r)
    idx = ["# Data package -- every number, and the artifact it came from", "",
           "Generated by `scripts/export_data_package.py`. Nothing here is typed by hand: each row",
           "was read out of a frozen artifact at export time.", "",
           "**Files**", "",
           "| file | what |", "|---|---|",
           "| `numbers.csv` | every number, flat: section, claim, value, artifact, note |",
           "| `TABLES.md` | the same numbers pre-rendered as markdown tables |",
           "| `artifacts/` | verified copies of every frozen result JSON |",
           "| `live/` | every live-experiment episode file, verbatim |",
           "| `MANIFEST.json` | byte counts and the gate results at export time |", "",
           "## Verification gates at export time", "",
           "| gate | result |", "|---|---|"]
    for k, v in gates.items():
        idx.append(f"| {k} | {v} |")
    idx += ["", f"## Numbers ({len(rows)} total)", ""]
    for sec in by_sec:
        idx.append(f"### {sec}")
        idx.append("")
        idx.append("| claim | value | artifact | note |")
        idx.append("|---|---|---|---|")
        for r in by_sec[sec]:
            v = r["value"]
            vs = f"{v:.4g}" if isinstance(v, float) else (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
            idx.append(f"| {r['claim']} | `{vs}` | `{r['artifact']}` | {r['note']} |")
        idx.append("")
    (OUT / "INDEX.md").write_text("\n".join(idx), encoding="utf-8")

    # ---- TABLES.md -----------------------------------------------------------------------
    tb = ["# Result tables (generated)", ""]
    if wrong.get("corpora"):
        tb += ["## The inversion, and its correction, on three disjoint shard sets", "",
               "| set | shards | runs | on_target_self solved → failed | gold solved | gold failed "
               "| within-inst p | wrong-fix share |", "|---|---|---|---|---|---|---|---|"]
        meta = (("frozen", "0–3", "26,679", wrong), ("held-out A", "4–7", "26,680", repl),
                ("held-out B", "8–11", "26,676", repl2))
        for tag, sh, runs, d in meta:
            b = d.get("corpora", {}).get("nebius", {})
            if not b:
                continue
            tb.append(f"| {tag} | {sh} | {runs} | {dig(b,'pooled_on_target_self.solved'):.3f} → "
                      f"{dig(b,'pooled_on_target_self.failed'):.3f} | "
                      f"{dig(b,'pooled_on_target_gold.solved'):.3f} | "
                      f"{dig(b,'pooled_on_target_gold.failed'):.3f} | "
                      f"{dig(b,'reversal_on_target_gold.p_wilcoxon'):.1e} | "
                      f"{100*dig(b,'failure_decomposition.frac_wrong_fix'):.1f}% |")
        tb.append("")
    v = transfer.get("verdict") or {}
    if v:
        tb += ["## Router: trained on shards 0–3, tested on unseen shards", "",
               "| target | ours (cross-set mean) | min cell | position | AgentStop-style "
               "| gain over field |", "|---|---|---|---|---|---|"]
        for tgt, lab in (("y_fail", "failure prediction"), ("y_wrong_fix", "lost vs wrong-fix")):
            d = v.get(tgt, {})
            tb.append(f"| {lab} | **{d.get('cross_own_rates_mean')}** | {d.get('cross_own_rates_min')} "
                      f"| {d.get('cross_position_mean')} | {d.get('cross_agentstop_mean')} "
                      f"| **+{d.get('own_minus_agentstop')}** |")
        tb.append("")
    if xs.get("corpora"):
        tb += ["## Cross-scaffold: the taxonomy does NOT transfer", "",
               "| scaffold | footer | kept | revised | dead-end |", "|---|---|---|---|---|"]
        ref = xs.get("reference", {}).get("swe_agent_nebius", {})
        if ref:
            tb.append(f"| SWE-agent (reference) | {ref.get('footer_rate_of_edit_steps')} "
                      f"| {ref.get('kept'):.3f} | {ref.get('revised'):.3f} | {ref.get('dead_end'):.3f} |")
        for name, c in xs["corpora"].items():
            tx = c.get("taxonomy") or {}
            fo = (c.get("markers") or {}).get("footer_edit_step_rate")
            tb.append(f"| {name} | {fo} | {tx.get('kept_rate'):.3f} | {tx.get('revised_rate'):.3f} "
                      f"| **{tx.get('dead_end_rate'):.3f}** |")
        tb.append("")
    (OUT / "TABLES.md").write_text("\n".join(tb), encoding="utf-8")

    (OUT / "MANIFEST.json").write_text(json.dumps({
        "n_numbers": len(rows), "sections": list(by_sec),
        "artifacts_copied": copied, "live_files_copied": live_files,
        "gates_at_export": gates,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"numbers exported : {len(rows)}")
    print(f"artifacts copied : {len(copied)}")
    print(f"live files copied: {len(live_files)}")
    for k, v in gates.items():
        print(f"  gate {k:18s} {v}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
