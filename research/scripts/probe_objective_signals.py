"""Highest-information first experiment on the 26,680-run Nebius corpus.

It answers three questions that decide the whole study design, using only the data
already on disk:

Q1  Is run length confounded with task difficulty?
    Prior work ("Beyond Resolution Rates", 2604.02547) reports that failures are longer
    pooled (+14% to +112%) but that within contested tasks the resolved runs are
    LONGER (44.0 vs 39.6 steps, p=1.9e-9). If that reverses here too, then any monitor
    that learns "long run => failure" is learning difficulty, not stagnation, and the
    study must be evaluated within-instance.

Q2  Does the "wasted work" share differ between resolved and unresolved runs once the
    instance is held fixed? This is the base-rate question: if stagnation is present
    in most windows (SWE-PRM flags 7.21 of 7.24), an AUC is not evidence of skill.

Q3  Is there a dense per-step objective progress signal at all?
    A public check said no corpus ships per-step test outcomes. But the *agent's own
    edits* are recorded at every step, and an edit that survives to the end of the
    trajectory is objectively productive whereas an edit that is later undone is
    objectively wasted. This computes the survival rate of edit steps and tests
    whether it separates resolved from unresolved runs within instance.

Writes results/rebuild/objective_signals.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"
FENCE = re.compile(r"```(?:bash|sh)?\s*\n(.*?)```", re.S)
FILE_HDR = re.compile(r"\[File:\s*([^\]\s]+)")
# lines the editor added: everything between the === marker of an OLD/NEW block and END
BLOCK = re.compile(r"^>>>>>>> OLD\s*$", re.M)
ENDM = re.compile(r"^<<<<<<< END\s*$", re.M)
NORM = re.compile(r"\s+")


def blocks(ai_text: str):
    """Extract (head_line, new_lines) for every action block in an ai turn."""
    out = []
    for body in FENCE.findall(ai_text):
        head = body.strip().splitlines()[0] if body.strip() else ""
        m1 = BLOCK.search(body)
        m2 = ENDM.search(body)
        new_lines = []
        if m1 and m2 and m2.start() > m1.end():
            seg = body[m1.end():m2.start()]
            # the NEW half follows a line of '=' characters
            parts = re.split(r"^=+\s*$", seg, maxsplit=1, flags=re.M)
            if len(parts) == 2:
                new_lines = [NORM.sub(" ", ln).strip() for ln in parts[1].splitlines()]
                new_lines = [ln for ln in new_lines if len(ln) >= 4]
        out.append((head, new_lines))
    return out


def analyse_run(traj, patch: str):
    """Per-run objective edit-survival statistics."""
    ai = [m.get("text") or "" for m in traj if m.get("role") == "ai"]
    added_by_step = []
    for text in ai:
        lines = []
        for _head, nl in blocks(text):
            lines.extend(nl)
        added_by_step.append(lines)
    # final surviving set: the agent's own final patch plus anything still present
    final_txt = NORM.sub(" ", patch or "")
    n_add = sum(len(x) for x in added_by_step)
    n_surv = sum(1 for lines in added_by_step for ln in lines if ln and ln in final_txt)
    # an edit that is followed by a later edit to the same file is a candidate revert
    edits = [i for i, lines in enumerate(added_by_step) if lines]
    dup_edit = 0
    seen_sig = Counter()
    for i in edits:
        key = " ".join(added_by_step[i][:6])
        if seen_sig[key]:
            dup_edit += 1
        seen_sig[key] += 1
    return {
        "n_ai": len(ai),
        "n_added_lines": n_add,
        "n_surviving_lines": n_surv,
        "survival_rate": (n_surv / n_add) if n_add else np.nan,
        "n_edit_steps": len(edits),
        "dup_edit_frac": (dup_edit / len(edits)) if edits else np.nan,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted((ROOT / "data" / "raw" / "nebius").glob("train-*.parquet"))
    rows = []
    for f in files:
        d = pd.read_parquet(f, columns=["instance_id", "model_name", "target", "trajectory",
                                        "generated_patch", "exit_status"])
        print(f"{f.name}: {len(d)} rows", flush=True)
        for i in range(len(d)):
            traj = d["trajectory"][i]
            if traj is None:
                continue
            st = analyse_run(list(traj), d["generated_patch"][i] or "")
            st.update({
                "instance_id": d["instance_id"][i],
                "model": d["model_name"][i],
                "target": int(bool(d["target"][i])),
                "exit_status": d["exit_status"][i],
                "patch_lines": len((d["generated_patch"][i] or "").splitlines()),
            })
            rows.append(st)
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / "objective_signals.parquet", index=False)
    print(f"\n{len(df)} runs, {df['instance_id'].nunique()} instances")

    res = {}
    # ---- Q1: length vs outcome, pooled and within instance ----
    res["pooled"] = {
        "steps_solved_mean": float(df.loc[df.target == 1, "n_ai"].mean()),
        "steps_failed_mean": float(df.loc[df.target == 0, "n_ai"].mean()),
        "success_rate": float(df.target.mean()),
    }
    print(f"\nQ1 pooled: solved {res['pooled']['steps_solved_mean']:.1f} steps, "
          f"failed {res['pooled']['steps_failed_mean']:.1f} steps, "
          f"success {res['pooled']['success_rate']:.3f}")

    # within-instance: instances with both outcomes
    g = df.groupby("instance_id")["target"]
    contested = g.nunique() == 2
    inst = g.size()
    sel = inst[(inst >= 3) & contested]
    sub = df[df.instance_id.isin(sel.index)]
    per_inst = []
    for iid, grp in sub.groupby("instance_id"):
        a = grp.loc[grp.target == 1, "n_ai"]
        b = grp.loc[grp.target == 0, "n_ai"]
        per_inst.append({
            "instance_id": iid,
            "n": len(grp),
            "steps_solved": float(a.mean()),
            "steps_failed": float(b.mean()),
            "delta": float(a.mean() - b.mean()),
            "surv_solved": float(grp.loc[grp.target == 1, "survival_rate"].mean()),
            "surv_failed": float(grp.loc[grp.target == 0, "survival_rate"].mean()),
        })
    pi = pd.DataFrame(per_inst)
    res["within_instance"] = {
        "n_instances": int(len(pi)),
        "n_runs": int(len(sub)),
        "mean_steps_solved": float(pi.steps_solved.mean()),
        "mean_steps_failed": float(pi.steps_failed.mean()),
        "mean_delta": float(pi.delta.mean()),
        "median_delta": float(pi.delta.median()),
        "frac_instances_solved_longer": float((pi.delta > 0).mean()),
    }
    from scipy import stats
    if len(pi) > 5:
        t, p = stats.wilcoxon(pi.steps_solved, pi.steps_failed)
        res["within_instance"]["wilcoxon_p"] = float(p)
    print(f"Q1 within-instance ({len(pi)} instances, {len(sub)} runs): "
          f"solved {pi.steps_solved.mean():.1f} vs failed {pi.steps_failed.mean():.1f} steps "
          f"(delta {pi.delta.mean():+.2f}, solved longer in {(pi.delta > 0).mean():.1%}) "
          f"p={res['within_instance'].get('wilcoxon_p', float('nan')):.2e}")

    # ---- Q2/Q3: edit survival, pooled and within instance ----
    both = df.dropna(subset=["survival_rate"])
    res["survival_pooled"] = {
        "n_runs_with_edits": int(len(both)),
        "solved_mean": float(both.loc[both.target == 1, "survival_rate"].mean()),
        "failed_mean": float(both.loc[both.target == 0, "survival_rate"].mean()),
        "frac_instances_solved_higher": (
            float((pi.surv_solved > pi.surv_failed).mean()) if len(pi) else float("nan")),
        "instances_solved_higher": int((pi.surv_solved > pi.surv_failed).sum()),
    }
    if len(pi) > 9 and pi.surv_solved.notna().any():
        t, p = stats.wilcoxon(pi.surv_solved.dropna(), pi.surv_failed.dropna())
        res["survival_pooled"]["wilcoxon_p"] = float(p)
    print(f"Q3 edit-line survival: solved {res['survival_pooled']['solved_mean']:.3f} vs "
          f"failed {res['survival_pooled']['failed_mean']:.3f}; "
          f"solved higher in {res['survival_pooled']['instances_solved_higher']}/{len(pi)} instances "
          f"p={res['survival_pooled'].get('wilcoxon_p', float('nan')):.2e}")

    # ---- Q2: wasted-work base rate ----
    res["base_rates"] = {
        "mean_survival": float(both.survival_rate.mean()) if len(both) else None,
        "median_survival": float(both.survival_rate.median()) if len(both) else None,
        "frac_runs_below_half": float((both.survival_rate < 0.5).mean()) if len(both) else None,
        "mean_dup_edit_frac": float(df.dup_edit_frac.mean()),
    }
    print(f"Q2 base rate: mean edit-line survival {res['base_rates']['mean_survival']:.3f}, "
          f"{res['base_rates']['frac_runs_below_half']:.1%} of runs below 0.5")

    with open(OUT / "objective_signals.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    pi.to_parquet(OUT / "within_instance.parquet", index=False)
    print(f"\nwrote {OUT / 'objective_signals.json'}")


if __name__ == "__main__":
    main()
