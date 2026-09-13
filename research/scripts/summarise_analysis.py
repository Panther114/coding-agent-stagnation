"""Read a frozen analysis and print the decision-relevant numbers in one page.

    python scripts/summarise_analysis.py --run results/rebuild/tb2_w10
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    run = Path(args.run)
    if not run.is_absolute():
        run = ROOT / run
    d = json.loads((run / "analysis.json").read_text(encoding="utf-8"))
    print(f"=== {run.name}  target={d.get('primary_target')}  "
          f"{d['n_windows']} windows / {d['n_runs']} runs / {d['n_tasks']} tasks")
    print("\n[A] target base rates")
    for k, v in d["A_base_rates"].items():
        if isinstance(v, dict) and "mean" in v and "n" in v:
            print(f"   {k:<22} mean {v['mean']:.3f}  zero-frac {v.get('frac_zero', float('nan')):.2f}"
                  f"  one-frac {v.get('frac_one', float('nan')):.2f}  n {v['n']}")
    print(f"   uniform runs (whole run one class): {d['A_base_rates']['frac_uniform_runs']:.1%}")

    print("\n[B] position confound of the feature set")
    pc = d["B_confound"]["position_confound"]
    print(f"   mean |spearman| with position: raw {pc['mean_abs_spearman_raw']:.3f} -> "
          f"stationary {pc['mean_abs_spearman_stat']:.3f}  "
          f"(reduced for {pc['frac_reduced']:.0%} of {pc['n_features']} features)")
    sf = sorted([f for f in d["B_confound"]["single_features"] if f["auc"] == f["auc"]
                 and f["auc"] > 0.5], key=lambda x: -x["auc"])[:8]
    print("   strongest single features (AUC vs primary target):")
    for f in sf:
        print(f"      {f['feature']:<24} auc {f['auc']:.3f}  spearman {f['spearman']:+.3f}  "
              f"|rho pos| raw {abs(f['r_position']):.3f} stat {abs(f['r_position_s']):.3f}")

    print("\n[C/D] monitors, pooled vs within-run vs task-split")
    print(f"   {'monitor':<20} {'pooled':>7} {'withinRun':>10} {'medRun':>7} {'above':>10} "
          f"{'btwTask':>8} {'withinT':>8} {'burst':>6} {'pAUC5':>7} {'det5':>6}")
    for name, v in d["D_within_run"].items():
        wr = v["within_run"]
        gc = v["between_within_task"]
        bm = v["burst"]
        pa = v["partial_auc"]
        db = v["budget"]
        pooled = next((m["oof_auc"] for m in d["C_monitors"]["monitors"] if m["name"] == name), float("nan"))
        print(f"   {name:<20} {pooled:>7.3f} {wr.get('mean_auc', float('nan')):>10.3f} "
              f"{wr.get('median_auc', float('nan')):>7.3f} "
              f"{str(wr.get('n_above_half', 0)) + '/' + str(wr.get('n_runs', 0)):>10} "
              f"{gc.get('between_auc', float('nan')):>8.3f} "
              f"{gc.get('within_spearman', float('nan')):>+8.3f} "
              f"{bm.get('lift', float('nan')):>6.2f} "
              f"{pa.get('pauc_5', float('nan')):>7.3f} "
              f"{db.get('det_at_5', {}).get('det', float('nan')):>6.3f}")
    print("\n[E] paired comparisons")
    for k, v in d.get("E_comparisons", {}).items():
        print(f"   {k}: delta {v['delta']:+.3f} [{v['lo']:+.3f}, {v['hi']:+.3f}] p={v['p']:.3f}")


if __name__ == "__main__":
    main()
