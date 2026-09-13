"""Scratch: print the route_modes tables for the write-up (read-only)."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = json.load(open("results/rebuild/route_modes.json", encoding="utf-8"))
ORDER = ["position", "agentstop_shape", "ngram_loop", "exact_burst", "tfnorm_novel",
         "edit_rate_free", "own_rates", "own_all", "own_gbm_rates", "own_gbm_all",
         "own_rates_plus_position"]

for task in ("y_fail", "y_mode"):
    print("#" * 25, task)
    for f, ev in D["tasks"][task]["fractions"].items():
        m = ev["methods"]
        print(f"f={f} n={ev['n']} base={ev['base_rate']:.3f} mean_prefix={ev['mean_prefix_len']:.1f}")
        for k in ORDER:
            v = m[k]
            dd = ev["deltas_primary_vs_baselines"].get(k, {})
            star = "*" if dd.get("primary_beats") else " "
            ci = v["auc_ci95"]
            print(f"   {k:<24} {v['auc']:.3f} [{ci[0]:.3f},{ci[1]:.3f}] sd={v['auc_sd_over_fold_seeds']:.3f}"
                  f" r5={v['recall_at_budget']['0.05']:.3f} r10={v['recall_at_budget']['0.1']:.3f} {star}")
    print()
print("#" * 25, "y_mode_edited_only")
for f, ev in D["y_mode_edited_only"]["fractions"].items():
    m = ev["methods"]
    print(f"f={f} n={ev['n']} base={ev['base_rate']:.3f}: own_rates {m['own_rates']['auc']:.3f} "
          f"own_gbm_all {m['own_gbm_all']['auc']:.3f} position {m['position']['auc']:.3f} "
          f"agentstop {m['agentstop_shape']['auc']:.3f}")
print()
print("#" * 25, "calibration detail (seed 0)")
for task in ("y_fail", "y_mode"):
    det = D["calibration"][task]["detail_seed0"]
    print(task, "alpha", det["alpha"], "n_test", det["n_test_runs"])
    print("   detection by checkpoint:", {k: round(v, 3) for k, v in det["detection_by_checkpoint"].items()})
    print("   false alarm by checkpoint:", {k: round(v, 3) for k, v in det["false_alarm_by_checkpoint"].items()})
    print("   e-value rule:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in det["e_value_rule"].items()})
print()
print("#" * 25, "calibration by alpha")
for task in ("y_fail", "y_mode"):
    for a, v in D["calibration"][task]["by_alpha"].items():
        s, e = v["seq_threshold"], v["e_value_mean"]
        print(f"{task} a={a}: FA {s['false_alarm_rate_mean']:.4f} (max {s['false_alarm_rate_max']:.4f}) "
              f"det {s['detection_rate_mean']:.3f} | det_by_ckpt "
              f"{ {k: round(x,3) for k,x in s['detection_by_checkpoint_mean'].items()} } "
              f"| mean alarm at {s['mean_alarm_fraction_among_detected']:.2f} of the run "
              f"| e-value FA {e['false_alarm_rate_mean']:.4f} det {e['detection_rate_mean']:.3f}")
print()
print("#" * 25, "decision curve")
for f, v in D["decision_curve"]["conditional_on_failure"].items():
    row = " | ".join(f"lambda={lam}: {b['detector']:.3f} vs best {b['best_baseline']:.3f} "
                     f"(delta {b['delta_vs_best_baseline']:+.3f} "
                     f"[{b['delta_ci95'][0]:+.3f},{b['delta_ci95'][1]:+.3f}])"
                     for lam, b in v["by_lambda"].items())
    print(f"f={f} acc={v['routing_accuracy']:.3f} verify_rate={v['verify_rate']:.3f}")
    print("   ", row)
for f, v in D["decision_curve"]["gated_all_runs"].items():
    print(f"gated f={f}: detector {v['detector_utility']:.4f} search {v['always_search_utility']:.4f} "
          f"verify {v['always_verify_utility']:.4f} random {v['random_utility']:.4f} "
          f"intervention_rate {v['intervention_rate']:.3f} beats_all={v['beats_all_three']}")
print()
print("#" * 25, "length-matched")
for task in ("y_fail", "y_mode"):
    for f, ev in D["tasks"][task]["fractions"].items():
        lm = ev.get("length_matched", {})
        if lm:
            shown = {}
            for L, v in lm.items():
                shown[L] = {k: (None if v["methods"][k]["auc"] != v["methods"][k]["auc"]
                                else round(v["methods"][k]["auc"], 3))
                            for k in ("own_rates", "own_all", "agentstop_shape", "position")
                            if k in v["methods"]}
                shown[L]["n"] = v["n"]
            print(task, f, shown)
print()
print("features meta:", json.dumps(D["features"]["prefix_len_mean"], indent=1))
print("prefix quantiles:", json.dumps(D["features"]["prefix_len_quantiles"], indent=1))
print("tfnorm coverage:", D["features"]["tfnorm_targets_nonempty_frac"])
print("n rate features:", D["features"]["n_features_rates"],
      "n count features:", D["features"]["n_features_counts"])
print("integrity:", json.dumps(D["integrity_checks"], indent=1))
print("verdict headline:", D["verdict"]["headline"])
print("summary_by_task:", json.dumps(D["verdict"]["summary_by_task"], indent=1))
print("negative findings:", json.dumps(D["verdict"]["negative_findings"], indent=1))
print("importance y_mode 0.4:", json.dumps(D["tasks"]["y_mode"]["fractions"]["0.4"]
                                          ["feature_importance"]["top_features"], indent=1))
print("importance y_fail 0.2:", json.dumps(D["tasks"]["y_fail"]["fractions"]["0.2"]
                                          ["feature_importance"]["top_features"], indent=1))

