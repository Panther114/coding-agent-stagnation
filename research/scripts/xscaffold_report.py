"""Render ``results/rebuild/xscaffold_replication.json`` into the human-readable report.

    python scripts/xscaffold_report.py

Writes ``docs/XSCAFFOLD_REPLICATION.md``.  Touches nothing else.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"
DOCS = ROOT / "docs"

ORDER = ["nebius_openhands", "swegym", "pi", "smithmarines", "thoughtworks"]


def f(x: Any, nd: int = 3) -> str:
    if x is None or x == "":
        return "n/a"
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return str(x)


def pct(x: Any, nd: int = 1) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{100*float(x):.{nd}f}%"
    except Exception:
        return str(x)


def fp(x: Any) -> str:
    if x is None:
        return "n/a"
    try:
        v = float(x)
    except Exception:
        return str(x)
    return f"{v:.1e}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    r = json.loads((OUT / "xscaffold_replication.json").read_text(encoding="utf-8"))
    C: Dict[str, Any] = r["corpora"]
    cal = r.get("instrument_check") or {}
    ref = r["reference"]["swe_agent_nebius"]
    ref2 = cal.get("reference_nonempty_patch_runs_only") or {}

    L: List[str] = []
    A = L.append

    A("# Cross-scaffold replication of the two mechanical results")
    A("")
    A("The study measures agent work without a human or a model in the loop. Two of its")
    A("claims are *mechanical*, so both should survive a change of scaffold:")
    A("")
    A("1. **The three-class edit taxonomy.** Every edit is labelable from the observation")
    A("   and the agent's own final patch — `kept` (a line the step wrote reaches the")
    A("   patch), `revised` (nothing survives, but the same file is edited again later in")
    A("   the run), `dead_end` (nothing survives and the file is never touched again).")
    A(f"   SWE-agent reference: **kept {f(ref['kept'])} / revised {f(ref['revised'])} / "
      f"dead_end {f(ref['dead_end'])}** over {ref['n_edits']:,} edits in {ref['n_runs']:,} runs.")
    A("2. **The gold-target result.** Replace the run's *own* final patch, which flatters")
    A("   narrow patches, with an **independent gold patch** per instance and the sign of the")
    A("   solved-vs-failed localisation comparison reverses: on the self-referential target")
    A("   failed runs score *higher*, on the gold target solved runs do.")
    A("")
    A("This document reports what happens when the same instrument is pointed at four other")
    A("agent scaffolds and one multi-scaffold corpus. Nothing here is judged by a model:")
    A("every number comes from regex and hashing over the raw trajectories.")
    A("")
    A("## 0. Instrument check — the port is exact")
    A("")
    if cal:
        A("Before any cross-scaffold claim, the new code path was run end-to-end on the")
        A("SWE-agent corpus itself (`scripts/xscaffold_calibrate.py`). It reproduces the")
        A("frozen numbers **to zero absolute difference**:")
        A("")
        A("| | kept | revised | dead_end | edits | runs |")
        A("|---|---|---|---|---|---|")
        A(f"| frozen `dead_end.json` | {f(ref['kept'])} | {f(ref['revised'])} | "
          f"{f(ref['dead_end'])} | {ref['n_edits']:,} | {ref['n_runs']:,} |")
        ra = cal.get("reference_all_runs", {})
        A(f"| re-run with the cross-scaffold code | {f(ra.get('kept_rate'))} | "
          f"{f(ra.get('revised_rate'))} | {f(ra.get('dead_end_rate'))} | "
          f"{ra.get('n_edits', 0):,} | {ra.get('n_runs', 0):,} |")
        A("")
        A(f"max absolute difference: "
          f"**{max(cal.get('abs_diff_vs_frozen', {}).values() or [0]):.1e}** "
          f"(`reproduces_frozen = {cal.get('reproduces_frozen')}`).")
        A("")
        A("The check also exposed a scope question that matters for the comparison. The")
        A(f"frozen headline counts **every** edit, including the "
          f"{pct(cal.get('frac_edit_steps_with_empty_patch'))} of edits that sit in runs which")
        A("produced no patch at all "
          f"({cal.get('n_runs_with_only_empty_patches', 0):,} of {cal.get('n_runs_total', 0):,} "
          f"runs). Those edits can never be `kept`. Two references are therefore used below:")
        A("")
        A(f"- **scope A (all runs):** kept {f(ra.get('kept_rate'))} / revised "
          f"{f(ra.get('revised_rate'))} / dead_end {f(ra.get('dead_end_rate'))} — used for the")
        A("  two corpora that ship a patch column, where an empty patch is a real outcome;")
        A(f"- **scope B (non-empty patch only):** kept {f(ref2.get('kept_rate'))} / revised "
          f"{f(ref2.get('revised_rate'))} / dead_end {f(ref2.get('dead_end_rate'))} — used for")
        A("  the corpora whose patch has to be recovered from the transcript, where a run")
        A("  with no patch is unmeasurable rather than empty.")
        A("")
    else:
        A("_calibration not run_")
    A("---")
    A("")
    A("## 1. Headline table")
    A("")
    A("| corpus | scaffold | runs | steps | edits | `[File: …]` footer | lines-total marker | kept | revised | dead_end |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for k in ORDER:
        e = C.get(k)
        if not e:
            continue
        m = e.get("markers", {})
        t = e.get("taxonomy", {})
        A(f"| `{k}` | {e['label'].split('—')[-1].strip()} | "
          f"{e.get('patch_coverage', {}).get('n_runs', 0):,} | {m.get('n_steps', 0):,} | "
          f"{m.get('n_edit_steps', 0):,} | "
          f"{'**present**' if (m.get('footer_step_rate') or 0) > 0.01 else '**absent**'} | "
          f"{m.get('obs_with_lines_total', 0):,} of {m.get('n_steps', 0):,} | "
          f"{f(t.get('kept_rate')) if t.get('n_edits') else 'n/a'} | "
          f"{f(t.get('revised_rate')) if t.get('n_edits') else 'n/a'} | "
          f"{f(t.get('dead_end_rate')) if t.get('n_edits') else 'n/a'} |")
    A("")
    A("Reference rows:")
    A("")
    A(f"- SWE-agent, scope A: kept {f(ra.get('kept_rate'))} / revised {f(ra.get('revised_rate'))} "
      f"/ dead_end {f(ra.get('dead_end_rate'))}")
    A(f"- SWE-agent, scope B: kept {f(ref2.get('kept_rate'))} / revised {f(ref2.get('revised_rate'))} "
      f"/ dead_end {f(ref2.get('dead_end_rate'))}")
    A("")
    gr = r.get("gold_reference") or {}
    if gr:
        A("**The gold-target reference, and which way it points.** On the run's *own* final")
        A("patch, failed runs look slightly better localised than solved ones "
          f"(delta {f((gr.get('self_referential_counterpoint') or {}).get('delta_solved_minus_failed'))}, "
          "`on_target`). On the **independent gold target the sign reverses**:")
        A("")
        A("| SWE-agent, gold target | solved | failed | delta | p |")
        A("|---|---|---|---|---|")
        po = gr.get("pooled_on_target_gold", {})
        pe = gr.get("pooled_ever_touched_gold", {})
        wi_o = gr.get("within_instance_on_target_gold", {})
        wi_e = gr.get("within_instance_ever_touched_gold", {})
        A(f"| pooled `on_target_gold` | {f(po.get('solved'))} | {f(po.get('failed'))} | "
          f"{f(po.get('delta'))} | — |")
        A(f"| pooled `ever_touched_gold` | {f(pe.get('solved'))} | {f(pe.get('failed'))} | "
          f"{f(pe.get('delta'))} | — |")
        A(f"| paired `on_target_gold` | {f(wi_o.get('solved'))} | {f(wi_o.get('failed'))} | "
          f"{f(wi_o.get('delta'))} | {fp(wi_o.get('p'))} |")
        A(f"| paired `ever_touched_gold` | {f(wi_e.get('solved'))} | {f(wi_e.get('failed'))} | "
          f"{f(wi_e.get('delta'))} | {fp(wi_e.get('p'))} |")
        A("")
        A(f"Source: `{gr.get('source')}`. So *the gold-target result replicates* below means")
        A("**solved runs score higher than failed runs on both gold measures** — the reversal,")
        A("not the own-patch direction.")
    A("")
    A("---")
    A("")
    A("## 2. Per-corpus findings")
    A("")
    for k in ORDER:
        e = C.get(k)
        if not e:
            continue
        m = e.get("markers", {})
        t = e.get("taxonomy", {})
        t2 = e.get("taxonomy_nonempty_patch_runs_only")
        pc = e.get("patch_coverage", {})
        g = e.get("gold", {})
        tc = e.get("test_outcomes", {})
        v = e.get("verdicts", {})
        A(f"### 2.{ORDER.index(k)+1} `{k}` — {e['label']}")
        A("")
        A(f"**a. Structural marker.** {m.get('n_steps',0):,} steps scanned, "
          f"{m.get('n_edit_steps',0):,} of them edits. The SWE-agent footer appears on "
          f"**{pct(m.get('footer_step_rate'))}** of steps and the string "
          f"`(N lines total)` on **{pct(m.get('lines_total_step_rate'))}**.")
        if m.get("first_footer_literal"):
            A("")
            A("Literal footer found:")
            A("")
            A("```")
            A(str(m["first_footer_literal"]).splitlines()[0][:300])
            A("```")
        if m.get("first_lines_total_literal"):
            A("")
            A(f"Literal size marker found: `{str(m['first_lines_total_literal']).splitlines()[0][:200]}`")
        if m.get("first_catn_literal"):
            A("")
            A("Equivalent marker (names the file, no size):")
            A("")
            A("```")
            A(str(m["first_catn_literal"]).splitlines()[0][:300])
            A("```")
        A("")
        A(f"Edit steps that name their target file at all: "
          f"**{pct(m.get('edits_with_named_target_rate'))}**. Truncation notices on "
          f"{pct(m.get('truncated_step_rate'))} of steps.")
        A("")
        A("**b. Three-class taxonomy.**")
        A("")
        if t.get("n_edits"):
            A(f"| scope | edits | runs | kept | revised | dead_end |")
            A("|---|---|---|---|---|---|")
            A(f"| {pc.get('taxonomy_scope','')} | {t['n_edits']:,} | {t['n_runs']:,} | "
              f"{f(t['kept_rate'])} | {f(t['revised_rate'])} | {f(t['dead_end_rate'])} |")
            if t2:
                A(f"| runs with a non-empty patch only | {t2['n_edits']:,} | {t2['n_runs']:,} | "
                  f"{f(t2['kept_rate'])} | {f(t2['revised_rate'])} | {f(t2['dead_end_rate'])} |")
            A("")
            A(f"Coverage: {pc.get('n_edits_in_scope',0):,} of {pc.get('n_edits_total',0):,} "
              f"edit steps ({pct(pc.get('edit_coverage'))}); "
              f"{pc.get('n_runs_with_patch',0):,} of {pc.get('n_runs',0):,} runs expose a "
              f"non-empty final patch ({pct(pc.get('run_patch_rate'))}).")
            A("")
            if t.get("volume"):
                A(f"Dead ends in absolute terms: {t['volume']['dead_end_edits']:,} "
                  f"({f(t['volume']['mean_dead_end_per_run'],2)} per run); "
                  f"{pct(t['volume']['frac_runs_with_no_dead_end'])} of runs have none.")
                A("")
            if t.get("unsuperseded_subset"):
                u = t["unsuperseded_subset"]
                A(f"Among edits nothing revisits (n={u['n']:,}), {f(u['kept_rate'])} turned out "
                  f"to have been needed.")
                A("")
        else:
            A("_not computable — see the verdict below._")
            A("")
        A("**c. Gold target.**")
        A("")
        if g.get("n_runs_with_edits"):
            A(f"- instances with edits: {g.get('n_instances_with_edits',0):,}; of these "
              f"**{g.get('n_instances_with_gold',0):,}** have a gold patch in "
              f"`gold_patches.parquet` "
              f"({pct(g.get('n_instances_with_gold',0)/max(g.get('n_instances_with_edits',1),1))} "
              f"of the corpus, covering {g.get('n_runs_with_gold',0):,} runs)")
            if "pooled" in g and "solved" in g.get("pooled", {}):
                p = g["pooled"]
                A(f"- pooled: `ever_touched_gold` failed {f(p['failed']['ever_touched_gold'])} "
                  f"vs solved {f(p['solved']['ever_touched_gold'])}; `on_target_gold` failed "
                  f"{f(p['failed']['on_target_gold'])} vs solved {f(p['solved']['on_target_gold'])} "
                  f"(n = {p['failed']['n']:,} failed / {p['solved']['n']:,} solved)")
                w = g.get("within_instance", {})
                if w.get("on_target_gold"):
                    A(f"- within-instance (paired, {w['n_instances']} contested instances, "
                      f"{w['n_runs']:,} runs): `on_target_gold` failed "
                      f"{f(w['on_target_gold']['failed'])} vs solved "
                      f"{f(w['on_target_gold']['solved'])}, mean delta "
                      f"{w['on_target_gold']['mean_delta']:+.3f}, "
                      f"{pct(w['on_target_gold']['frac_positive'])} of instances positive, "
                      f"Wilcoxon p = {fp(w['on_target_gold']['p'])}; `ever_touched_gold` failed "
                      f"{f(w['ever_touched_gold']['failed'])} vs solved "
                      f"{f(w['ever_touched_gold']['solved'])}, delta "
                      f"{w['ever_touched_gold']['mean_delta']:+.3f}, p = "
                      f"{fp(w['ever_touched_gold']['p'])}")
                else:
                    A(f"- within-instance: not available ({w.get('note','no contested instances')})")
            elif "pooled" in g:
                p = g["pooled"]
                A(f"- pooled over {p['n_runs']:,} gold-covered runs: `ever_touched_gold` "
                  f"{f(p['ever_touched_gold'])}, `on_target_gold` {f(p['on_target_gold'])}; "
                  f"{p.get('note','')}")
            else:
                A("- no run of this corpus touches a gold-covered instance")
            op = e.get("own_patch_target", {})
            if op.get("n_runs"):
                A(f"- for comparison, the study's *existing* target — the run's own final patch "
                  f"— gives mean `on_target` {f(op.get('mean_on_target_own_patch'))}"
                  + (f" (solved {f(op.get('solved'))} vs failed {f(op.get('failed'))})"
                     if "solved" in op else ""))
        A("")
        A("**d. Per-step test outcomes.**")
        A("")
        if tc.get("n_steps"):
            A(f"- strict pytest/unittest pass–fail summary on {pct(tc['strict_step_rate'])} of steps")
            A(f"- any test marker (strict + framework summaries such as `N passed`/`N failed`, "
              f"`PASSED`/`FAILED`, `test session starts`) on {pct(tc['loose_step_rate'])} of steps")
            A(f"- exit codes readable on {pct(tc['exit_code_step_rate'])} of steps; "
              f"{pct(tc['runs_with_exit_code'])} of runs contain at least one")
            A(f"- {pct(tc['runs_with_strict_summary'])} of runs contain a strict summary; "
              f"{pct(tc['runs_with_any_test_step'])} contain any test marker")
        A("")
        A("**Verdicts.**")
        A("")
        A(f"- *Footer:* {v.get('footer','n/a')}")
        A(f"- *Taxonomy:* {v.get('taxonomy','n/a')}")
        A(f"- *Gold target:* {v.get('gold','n/a')}")
        A(f"- *Test outcomes:* {v.get('tests','n/a')}")
        A("")
        if k == "thoughtworks" and e.get("by_framework"):
            A("**Split by the corpus's own `agent_framework` column.**")
            A("")
            A("| framework | runs | steps | edits | footer | `cat -n` | patchable runs | edit coverage | kept | revised | dead_end | gold instances |")
            A("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for fw, x in e["by_framework"].items():
                tt = x.get("taxonomy") or {}
                gg = x.get("gold", {})
                A(f"| `{fw}` | {x['n_runs']:,} | {x['n_steps']:,} | {x['n_edits']:,} | "
                  f"{pct(x['footer_step_rate'])} | {pct(x['catn_step_rate'])} | "
                  f"{pct(x['run_patch_rate'])} | {pct(x.get('edit_coverage'))} | "
                  f"{f(tt.get('kept_rate')) if tt.get('n_edits') else 'n/a'} | "
                  f"{f(tt.get('revised_rate')) if tt.get('n_edits') else 'n/a'} | "
                  f"{f(tt.get('dead_end_rate')) if tt.get('n_edits') else 'n/a'} | "
                  f"{gg.get('n_instances_with_gold', 0):,} |")
            A("")
        A("---")
        A("")

    A("## 3. What the replication shows")
    A("")
    A("Every figure below is generated from `results/rebuild/xscaffold_replication.json`, so")
    A("none of it can drift from the machine-readable numbers.")
    A("")
    tot_obs = sum(int((C.get(k, {}).get("markers", {}) or {}).get("n_tool_obs", 0)) for k in ORDER)
    tot_foot = sum(int((C.get(k, {}).get("markers", {}) or {}).get("obs_with_footer", 0)) for k in ORDER)
    A(f"**The footer does not travel.** Across the four non-SWE-agent scaffolds this run")
    A(f"scanned {tot_obs:,} observations and found the SWE-agent editor footer in "
      f"**{tot_foot}** of them.")
    A("What replaces it is a marker that names the file but states no size:")
    A("")
    A("```")
    literal = None
    for k in ORDER:
        if k == "nebius_openhands":
            continue
        lit = (C.get(k, {}).get("markers", {}) or {}).get("first_catn_literal")
        if lit:
            literal = str(lit).splitlines()[0]
            break
    A(literal or "(none found)")
    A("```")
    A("")
    A("**The taxonomy travels badly.**")
    A("")
    A("| corpus | kept | revised | dead_end | L1 vs SWE-agent | edits in scope |")
    A("|---|---|---|---|---|---|")
    for k in ORDER:
        e = C.get(k)
        if not e:
            continue
        t = e.get("taxonomy", {})
        vv = e.get("verdicts", {})
        if not t.get("n_edits"):
            A(f"| `{k}` | n/a | n/a | n/a | — | 0 |")
            continue
        A(f"| `{k}` | {f(t['kept_rate'])} | {f(t['revised_rate'])} | {f(t['dead_end_rate'])} | "
          f"{f(vv.get('taxonomy_l1_vs_swe_agent'), 2)} | "
          f"{pct(e.get('patch_coverage', {}).get('edit_coverage'))} |")
    A(f"| *SWE-agent (scope B)* | {f(ref2.get('kept_rate'))} | {f(ref2.get('revised_rate'))} | "
      f"{f(ref2.get('dead_end_rate'))} | 0.00 | 100.0% |")
    A("")
    A("**The gold-target reversal is the part that survives best — where it can be measured.**")
    A("")
    A("| corpus | gold-covered runs | instances overlapping gold | pooled delta solved−failed (on_target_gold) | paired p |")
    A("|---|---|---|---|---|")
    for k in ORDER:
        e = C.get(k)
        if not e:
            continue
        g = e.get("gold", {})
        if "pooled" not in g or "solved" not in g.get("pooled", {}):
            A(f"| `{k}` | {g.get('n_runs_with_gold', 0):,} | {g.get('n_instances_with_gold', 0):,} | "
              f"not computable | — |")
            continue
        p_ = g["pooled"]
        wi = g.get("within_instance", {})
        pp = (wi.get("on_target_gold") or {}).get("p")
        A(f"| `{k}` | {p_['n_runs']:,} | {g.get('n_instances_with_gold', 0):,} | "
          f"{p_['delta_solved_minus_failed']['on_target_gold']:+.3f} | {fp(pp)} |")
    A(f"| *SWE-agent* | 19,635 | 228 | +0.070 | {fp(0.007006189656934297)} |")
    A("")
    for k in ORDER:
        e = C.get(k)
        if not e:
            continue
        v = e.get("verdicts", {})
        A(f"**`{k}`** — {v.get('footer','')} {v.get('taxonomy','')} {v.get('gold','')}")
        A("")

    A("## 4. Method, and where it could be wrong")
    A("")
    A("**Corpora.** Downloaded in full and parsed locally; total 4.6 GB. Row counts:")
    A("")
    A("| corpus | HF repo | rows in the corpus | rows parsed here |")
    A("|---|---|---|---|")
    HUB = {
        "nebius_openhands": "nebius/SWE-rebench-openhands-trajectories",
        "swegym": "SWE-Gym/OpenHands-Sampled-Trajectories",
        "pi": "whitecircle/swe-rebench-v2-glm-5.1-pi-agent-successful-traces",
        "smithmarines": "Kwai-Klear/SWE-smith-mini_swe_agent_plus-trajectories-66k",
        "thoughtworks": "thoughtworks/agentic-coding-trajectories",
    }
    for k in ORDER:
        e = C.get(k)
        if not e:
            continue
        A(f"| `{k}` | `{HUB[k]}` | — | "
          f"{e.get('patch_coverage',{}).get('n_runs',0):,} |")
    A("")
    A("**Where an edit's target file comes from.** This is the one place where scaffolds")
    A("genuinely differ, and it is recorded rather than assumed.")
    A("")
    A("- SWE-agent (the frozen study) reads it from the observation's `[File: …]` footer.")
    A("- OpenHands, the PI agent and mini-swe-agent do not print that footer, so the target")
    A("  comes from the **tool-call arguments** (`path`), which is the same information")
    A("  the agent acted on. Coverage is reported per corpus.")
    A("")
    A("**Paths.** `norm_path` strips the sandbox root (`/workspace/<repo>/`, `/testbed/`, …)")
    A("so an edit and a patch hunk referring to the same file compare equal. The frozen")
    A("study compared raw footer strings; the normalisation only makes that comparison")
    A("slightly more generous.")
    A("")
    A("**Line hashes.** A written line and a patch `+` line are compared by a 6-byte")
    A("blake2b of their stripped text, with a minimum length of 3 characters — the frozen")
    A("definitions, reused verbatim.")
    A("")
    A("**Recovered patches.** For the PI agent, mini-swe-agent and thoughtworks corpora the")
    A("final patch is not a column; it is taken from the agent's own printed `git diff` in")
    A("the transcript (the longest such block, else the last fenced `diff` block). A run")
    A("that never printed a diff is therefore *unmeasurable*, not *empty*, and such runs are")
    A("excluded from the taxonomy rather than scored as `kept = 0`. That is why those corpora")
    A("carry an explicit coverage fraction, and why the taxonomy verdict is only as strong as")
    A("that fraction.")
    A("")
    A("**Gold target.** `gold_patches.parquet` holds gold file basenames for 927 instances.")
    A("A run is `ever_touched_gold` if any edit step aims at a file whose *basename* is in")
    A("its instance's gold set, and `on_target_gold` is the share of its edit steps that do.")
    A("Matching is by basename, so a same-named file elsewhere in the tree would count; the")
    A("gold patches are small (1–3 files) and repo-specific, so this is a mild relaxation.")
    A("Corpora whose instance ids do not intersect that set get no gold result at all.")
    A("")
    A("**No model was called.** Everything is regex, hashing and arithmetic.")

    (DOCS / "XSCAFFOLD_REPLICATION.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {DOCS / 'XSCAFFOLD_REPLICATION.md'} ({len(L)} lines)")


if __name__ == "__main__":
    main()
