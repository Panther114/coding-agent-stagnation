"""Verify that every number quoted in docs/ROUTE_MODES.md matches
results/rebuild/route_modes.json to the precision it is written to.

    python scripts/_verify_route_modes_doc.py

Any mismatch is printed as FAIL with both values; exit code 1 if anything fails. This exists
so the write-up cannot drift from the artifact.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "ROUTE_MODES.md"
JS = ROOT / "results" / "rebuild" / "route_modes.json"

doc_text = DOC.read_text(encoding="utf-8")
D = json.loads(JS.read_text(encoding="utf-8"))

fails: list[str] = []
checks = 0


def check(label: str, expected, actual):
    global checks
    checks += 1
    if isinstance(expected, float) and isinstance(actual, float):
        ok = abs(expected - actual) < 1e-9
    else:
        ok = expected == actual
    if not ok:
        fails.append(f"{label}: doc={expected!r} json={actual!r}")


def near(label: str, expected: float, actual: float, tol: float = 5e-4):
    global checks
    checks += 1
    if actual is None or abs(expected - actual) > tol:
        fails.append(f"{label}: doc={expected} json={actual}")


def in_doc(snippet: str, label: str):
    global checks
    checks += 1
    if snippet not in doc_text:
        fails.append(f"{label}: doc does not contain {snippet!r}")


# ---- coverage / labels -----------------------------------------------------------------
check("runs_in_corpus", 26679, D["coverage"]["runs_in_corpus"])
check("runs_with_gold", 20341, D["coverage"]["runs_with_gold"])
check("instances_with_gold", 927, D["coverage"]["instances_with_gold"])
check("instances_in_corpus", 1213, D["coverage"]["instances_in_corpus"])
check("edit_steps", 173417, D["coverage"]["edit_steps"])
check("edit_steps_unknown", 7109, D["coverage"]["edit_steps_with_unknown_file"])
near("coverage_pct", 76.2, round(100 * D["coverage"]["runs_with_gold"]
                                 / D["coverage"]["runs_in_corpus"], 1), 0.1)
near("unknown_frac_pct", 4.10, round(100 * D["coverage"]["edit_steps_with_unknown_file_frac"], 2),
     0.01)
lab = D["labels"]
near("y_fail_base", 0.8373, round(lab["y_fail_base_rate"], 4))
near("y_wrong_fix_failed", 0.6428, round(lab["y_wrong_fix_base_rate_over_failed"], 4))
near("y_wrong_fix_edited", 0.6705, round(lab["y_wrong_fix_base_rate_over_failed_with_edits"], 4))
near("success_ever_gold", 0.9813, round(lab["success_runs_ever_touched_gold"], 4))
near("on_target_failed", 0.4069, round(lab["on_target_gold_mean_failed"], 4))
near("on_target_success", 0.4771, round(lab["on_target_gold_mean_success"], 4))
check("never_edited", 704, lab["lost_runs_that_never_edited"])
check("n_failed", 17031, lab["n_failed"])
check("n_edited", 16327, lab["failed_runs_with_at_least_one_edit"])
nf = D["noise_floor"]
near("rpi_mean", 21.9, round(nf["runs_per_instance_mean"], 1), 0.05)
check("rpi_median", 14, int(nf["runs_per_instance_median"]))
near("rpi_p90", 50.4, round(nf["runs_per_instance_p90"], 1), 0.05)
check("rpi_max", 98, nf["runs_per_instance_max"])
check("mixed_instances", 228, nf["instances_with_both_outcomes"])
near("mixed_pct", 24.6, round(100 * nf["instances_with_both_outcomes_frac"], 1), 0.05)
wi = D["within_instance"]
near("within_auc", 0.584, round(wi["mean_auc"], 3))
near("within_above_half_pct", 66.2, round(100 * wi["frac_above_half"], 1), 0.05)

# ---- table AUCs ------------------------------------------------------------------------
TAB_Y_FAIL = {  # from the doc
    "position": [0.667, 0.664, 0.666, 0.666],
    "agentstop_shape": [0.554, 0.565, 0.594, 0.607],
    "tfnorm_novel": [0.543, 0.594, 0.627, 0.642],
    "ngram_loop": [0.506, 0.515, 0.544, 0.576],
    "exact_burst": [0.507, 0.520, 0.552, 0.578],
    "edit_rate_free": [0.465, 0.451, 0.452, 0.455],
    "own_rates": [0.693, 0.721, 0.721, 0.731],
    "own_all": [0.699, 0.725, 0.729, 0.743],
    "own_gbm_rates": [0.699, 0.725, 0.742, 0.763],
    "own_gbm_all": [0.702, 0.727, 0.744, 0.770],
    "own_rates_plus_position": [0.694, 0.720, 0.721, 0.732],
}
TAB_Y_MODE = {
    "position": [0.407, 0.411, 0.413, 0.413],
    "agentstop_shape": [0.493, 0.490, 0.475, 0.470],
    "tfnorm_novel": [0.449, 0.447, 0.467, 0.489],
    "ngram_loop": [0.485, 0.474, 0.459, 0.453],
    "exact_burst": [0.484, 0.473, 0.467, 0.466],
    "edit_rate_free": [0.418, 0.435, 0.486, 0.539],
    "own_rates": [0.676, 0.701, 0.724, 0.751],
    "own_all": [0.678, 0.715, 0.756, 0.777],
    "own_gbm_rates": [0.682, 0.724, 0.781, 0.806],
    "own_gbm_all": [0.685, 0.729, 0.785, 0.813],
    "own_rates_plus_position": [0.677, 0.702, 0.725, 0.751],
}
for task, tab in (("y_fail", TAB_Y_FAIL), ("y_mode", TAB_Y_MODE)):
    for f_i, f in enumerate(("0.1", "0.2", "0.4", "0.6")):
        m = D["tasks"][task]["fractions"][f]["methods"]
        for meth, vals in tab.items():
            near(f"{task} AUC {meth} f={f}", vals[f_i], round(m[meth]["auc"], 3))

# detail tables at f=0.40
det = {
    "y_fail": {"position": (0.666, 0.645, 0.687, 0.057, 0.114),
               "agentstop_shape": (0.594, 0.566, 0.624, 0.057, 0.111),
               "tfnorm_novel": (0.627, 0.602, 0.648, 0.056, 0.112),
               "exact_burst": (0.552, 0.545, 0.560, 0.057, 0.113),
               "ngram_loop": (0.544, 0.539, 0.550, 0.058, 0.112),
               "edit_rate_free": (0.452, 0.423, 0.483, 0.054, 0.105),
               "own_rates": (0.721, 0.694, 0.745, 0.058, 0.116),
               "own_all": (0.729, 0.704, 0.753, 0.059, 0.117),
               "own_gbm_all": (0.744, 0.720, 0.771, 0.059, 0.118)},
    "y_mode": {"position": (0.413, 0.392, 0.432, 0.016, 0.052),
               "agentstop_shape": (0.475, 0.436, 0.482, 0.043, 0.088),
               "tfnorm_novel": (0.467, 0.450, 0.485, 0.034, 0.087),
               "edit_rate_free": (0.486, 0.463, 0.507, 0.029, 0.071),
               "own_rates": (0.724, 0.707, 0.744, 0.065, 0.131),
               "own_gbm_all": (0.785, 0.768, 0.806, 0.070, 0.139)},
}
for task, tab in det.items():
    m = D["tasks"][task]["fractions"]["0.4"]["methods"]
    for meth, (a, lo, hi, r5, r10) in tab.items():
        near(f"{task} detail AUC {meth}", a, round(m[meth]["auc"], 3))
        near(f"{task} detail CI lo {meth}", lo, round(m[meth]["auc_ci95"][0], 3))
        near(f"{task} detail CI hi {meth}", hi, round(m[meth]["auc_ci95"][1], 3))
        near(f"{task} detail r5 {meth}", r5, round(m[meth]["recall_at_budget"]["0.05"], 3))
        near(f"{task} detail r10 {meth}", r10, round(m[meth]["recall_at_budget"]["0.1"], 3))

# ---- paired deltas ---------------------------------------------------------------------
DLT = {
    "y_fail": {"position": [0.026, 0.057, 0.054, 0.065],
               "agentstop_shape": [0.140, 0.156, 0.126, 0.124],
               "tfnorm_novel": [0.151, 0.127, 0.094, 0.089]},
    "y_mode": {"position": [0.270, 0.289, 0.311, 0.339],
               "agentstop_shape": [0.184, 0.211, 0.249, 0.282],
               "tfnorm_novel": [0.227, 0.254, 0.257, 0.263]},
}
CI_LO = {
    "y_fail": {"position": [0.011, 0.036, 0.035, 0.045]},
    "y_mode": {"position": [0.235, 0.258, 0.281, 0.308]},
}
for task, tab in DLT.items():
    for f_i, f in enumerate(("0.1", "0.2", "0.4", "0.6")):
        dd = D["tasks"][task]["fractions"][f]["deltas_primary_vs_baselines"]
        for meth, vals in tab.items():
            near(f"{task} delta {meth} f={f}", vals[f_i], round(dd[meth]["delta"], 3))
for task, tab in CI_LO.items():
    for f_i, f in enumerate(("0.1", "0.2", "0.4", "0.6")):
        dd = D["tasks"][task]["fractions"][f]["deltas_primary_vs_baselines"]["position"]
        near(f"{task} position CI lo f={f}", tab["position"][f_i], round(dd["ci95"][0], 3))

# ---- length matched --------------------------------------------------------------------
LM = {("y_fail", "0.1", "5"): (880, 0.733, 0.739, 0.358),
      ("y_fail", "0.2", "5"): (1446, 0.625, 0.634, 0.496),
      ("y_fail", "0.2", "10"): (458, 0.758, 0.774, 0.402),
      ("y_fail", "0.4", "10"): (858, 0.675, 0.710, 0.592),
      ("y_fail", "0.6", "5"): (1963, 0.695, 0.707, 0.581),
      ("y_fail", "0.6", "10"): (1190, 0.631, 0.636, 0.536),
      ("y_mode", "0.1", "5"): (842, 0.648, 0.653, 0.496),
      ("y_mode", "0.4", "10"): (775, 0.666, 0.718, 0.525),
      ("y_mode", "0.6", "5"): (1413, 0.739, 0.747, 0.439),
      ("y_mode", "0.6", "20"): (484, 0.703, 0.755, 0.522)}
for (task, f, L), (n, own, ownall, astop) in LM.items():
    cell = D["tasks"][task]["fractions"][f]["length_matched"][L]
    check(f"lm n {task} {f} L={L}", n, cell["n"])
    near(f"lm own_rates {task} {f} L={L}", own, round(cell["methods"]["own_rates"]["auc"], 3))
    near(f"lm own_all {task} {f} L={L}", ownall, round(cell["methods"]["own_all"]["auc"], 3))
    near(f"lm agentstop {task} {f} L={L}", astop,
         round(cell["methods"]["agentstop_shape"]["auc"], 3))

# ---- calibration -----------------------------------------------------------------------
CAL = {
    ("y_mode", "0.05"): (0.0459, 0.0605, 0.160),
    ("y_mode", "0.1"): (0.0777, 0.0931, 0.258),
    ("y_mode", "0.2"): (0.1232, 0.1329, 0.386),
    ("y_mode", "0.5"): (0.2475, 0.2552, 0.636),
    ("y_fail", "0.05"): (0.0339, 0.0513, 0.194),
    ("y_fail", "0.1"): (0.0603, 0.0842, 0.285),
    ("y_fail", "0.2"): (0.1088, 0.1409, 0.399),
    ("y_fail", "0.5"): (0.2255, 0.2684, 0.581),
}
for (task, a), (fa, famax, detrate) in CAL.items():
    s = D["calibration"][task]["by_alpha"][a]["seq_threshold"]
    near(f"cal FA {task} a={a}", fa, round(s["false_alarm_rate_mean"], 4), 1e-4)
    near(f"cal FA max {task} a={a}", famax, round(s["false_alarm_rate_max"], 4), 1e-4)
    near(f"cal det {task} a={a}", detrate, round(s["detection_rate_mean"], 3))
# checkpoint detail at alpha 0.2 (y_mode)
s2 = D["calibration"]["y_mode"]["by_alpha"]["0.2"]["seq_threshold"]
for f, d in (("0.1", 0.154), ("0.2", 0.250), ("0.4", 0.325), ("0.6", 0.386)):
    near(f"ckpt det y_mode a=0.2 f={f}", d, round(s2["detection_by_checkpoint_mean"][f], 3))
for f, fa in (("0.1", 0.0495), ("0.2", 0.0754), ("0.4", 0.0997), ("0.6", 0.1232)):
    near(f"ckpt FA y_mode a=0.2 f={f}", fa, round(s2["false_alarm_by_checkpoint_mean"][f], 4), 1e-4)
near("mean alarm fraction y_mode a=0.2", 0.261,
     round(s2["mean_alarm_fraction_among_detected"], 3))
near("n_null y_mode", 1561, round(D["calibration"]["y_mode"]["by_alpha"]["0.2"]["seq_threshold"]
                                   ["n_null_calibration_mean"]))
near("n_null y_fail", 903, round(D["calibration"]["y_fail"]["by_alpha"]["0.2"]["seq_threshold"]
                                 ["n_null_calibration_mean"]))
near("n_test y_fail", 4926, round(D["calibration"]["y_fail"]["by_alpha"]["0.2"]["seq_threshold"]
                                  ["n_test_runs_mean"]))
near("n_test y_mode", 4289, round(D["calibration"]["y_mode"]["by_alpha"]["0.2"]["seq_threshold"]
                                  ["n_test_runs_mean"]))
# e-value
EV = {("y_mode", "0.05"): (0.0, 0.0), ("y_mode", "0.2"): (0.0060, 0.012),
      ("y_mode", "0.5"): (0.0611, 0.228), ("y_fail", "0.05"): (0.0, 0.0),
      ("y_fail", "0.2"): (0.0078, 0.075), ("y_fail", "0.5"): (0.0692, 0.317)}
for (task, a), (fa, detrate) in EV.items():
    e = D["calibration"][task]["by_alpha"][a]["e_value_mean"]
    near(f"evalue FA {task} a={a}", fa, round(e["false_alarm_rate_mean"], 4), 1e-4)
    near(f"evalue det {task} a={a}", detrate, round(e["detection_rate_mean"], 3))
near("evalue null mean y_mode", 0.96,
     round(D["calibration"]["y_mode"]["by_alpha"]["0.05"]["e_value_mean"]["mean_e_value_on_nulls"], 2))
near("evalue null mean y_fail", 1.007,
     round(D["calibration"]["y_fail"]["by_alpha"]["0.05"]["e_value_mean"]["mean_e_value_on_nulls"], 3))

# ---- null checks -----------------------------------------------------------------------
nc = D["null_checks"]
near("raw flag never-failing", 0.984, round(nc["raw_0.5_threshold_flag_rate_on_never_failing_runs"], 3))
near("raw flag failing", 0.995, round(nc["raw_0.5_threshold_flag_rate_on_failing_runs"], 3))
near("calibrated FA 0.05", 0.0339,
     round(nc["calibrated_rule_false_alarm_on_never_failing_runs_alpha_0.05"], 4), 1e-4)
near("lost routed verify raw", 0.568, round(nc["lost_runs_routed_to_verify_raw_0.5"], 3))
near("lost mean mode score", 0.521, round(nc["lost_runs_mean_mode_score"], 3))
near("wrongfix mean mode score", 0.710, round(nc["wrong_fix_runs_mean_mode_score"], 3))

# ---- decision curve --------------------------------------------------------------------
DEC = {("0.1", "0.25"): (0.764, 0.518, 0.732, 0.656, 0.032, 0.024, 0.039),
       ("0.2", "0.25"): (0.776, 0.518, 0.732, 0.656, 0.044, 0.035, 0.053),
       ("0.4", "0.25"): (0.786, 0.518, 0.732, 0.656, 0.054, 0.045, 0.064),
       ("0.6", "0.25"): (0.800, 0.518, 0.732, 0.656, 0.068, 0.057, 0.077),
       ("0.1", "0.0"): (0.685, 0.357, 0.643, 0.541, 0.042, 0.032, 0.052),
       ("0.6", "0.0"): (0.733, 0.357, 0.643, 0.541, 0.090, 0.076, 0.103),
       ("0.1", "0.5"): (0.842, 0.679, 0.821, 0.770, 0.021, 0.016, 0.026),
       ("0.6", "0.5"): (0.866, 0.679, 0.821, 0.770, 0.045, 0.038, 0.052)}
for (f, lam), (d, s, v, r, delta, lo, hi) in DEC.items():
    b = D["decision_curve"]["conditional_on_failure"][f]["by_lambda"][lam]
    near(f"dec det f={f} l={lam}", d, round(b["detector"], 3))
    near(f"dec search f={f} l={lam}", s, round(b["always_search"], 3))
    near(f"dec verify f={f} l={lam}", v, round(b["always_verify"], 3))
    near(f"dec random f={f} l={lam}", r, round(b["random_routing"], 3))
    near(f"dec delta f={f} l={lam}", delta, round(b["delta_vs_best_baseline"], 3))
    near(f"dec lo f={f} l={lam}", lo, round(b["delta_ci95"][0], 3))
    near(f"dec hi f={f} l={lam}", hi, round(b["delta_ci95"][1], 3))
    check(f"dec beats_all f={f} l={lam}", True, b["beats_all_three"])
for f, acc, vr in (("0.1", 0.685, 0.877), ("0.2", 0.702, 0.822), ("0.4", 0.715, 0.807),
                   ("0.6", 0.733, 0.782)):
    cc = D["decision_curve"]["conditional_on_failure"][f]
    near(f"dec acc f={f}", acc, round(cc["routing_accuracy"], 3))
    near(f"dec verify_rate f={f}", vr, round(cc["verify_rate"], 3))
GATED = {"0.1": (0.639, 0.397), "0.2": (0.649, 0.397), "0.4": (0.657, 0.397),
         "0.6": (0.666, 0.397)}
for f, (d, s) in GATED.items():
    g = D["decision_curve"]["gated_all_runs"][f]
    near(f"gated det f={f}", d, round(g["detector_utility"], 3))
    near(f"gated search f={f}", s, round(g["always_search_utility"], 3))
    near(f"gated verify f={f}", 0.547, round(g["always_verify_utility"], 3))
    near(f"gated random f={f}", 0.523, round(g["random_utility"], 3))
    check(f"gated beats f={f}", True, g["beats_all_three"])

# ---- position == run length ------------------------------------------------------------
pe = D["integrity_checks"]["position_equals_run_length"]
for k, v in pe.items():
    near(f"position leak diagnostic {k}", 0.0, round(v["max_abs_difference"], 2), 0.01)

# ---- importance ------------------------------------------------------------------------
IMP_YFAIL = {"sig_entropy": (-2.03, 0.630), "max_consec_repeat_norm": (-1.98, 0.349),
             "noop_edit_frac": (0.88, 0.491), "any_file_edited_twice": (-0.79, 0.506),
             "repeat_file_edit_frac": (0.75, 0.526), "unique_cmdfam_frac": (-0.68, 0.345)}
IMP_YMODE = {"no_edit_yet": (-0.89, 0.515), "unique_cmdfam_frac": (0.88, 0.612),
             "noop_edit_frac": (-0.84, 0.409), "sig_entropy": (0.67, 0.548),
             "repeat_file_edit_frac": (-0.66, 0.456), "any_file_edited_twice": (0.49, 0.468)}
for task, f, tab in (("y_fail", "0.2", IMP_YFAIL), ("y_mode", "0.4", IMP_YMODE)):
    feats = {r["feature"]: r for r in
             D["tasks"][task]["fractions"][f]["feature_importance"]["top_features"]}
    for k, (coef, auc) in tab.items():
        near(f"imp coef {task} {k}", coef, round(feats[k]["mean_standardised_coef"], 2), 0.005)
        near(f"imp auc {task} {k}", auc, round(feats[k]["standalone_auc"], 3))

# ---- text-level claims ------------------------------------------------------------------
in_doc("**112 feature columns** at f = 0.10 and f = 0.40 come back identical", "selftest claim")
in_doc("All 8 combinations are controlled at their stated α", "calibration summary")
# the worst-split exceedance claim: exactly one level over its alpha, by <= 1.21x
_over = []
for _t in ("y_fail", "y_mode"):
    for _a, _v in D["calibration"][_t]["by_alpha"].items():
        _r = _v["seq_threshold"]["false_alarm_rate_max"] / float(_a)
        if _r > 1:
            _over.append((_t, _a, round(_r, 2)))
check("levels where the worst split exceeds alpha",
      [("y_fail", "0.05", 1.03), ("y_mode", "0.05", 1.21)], _over)
in_doc("1.03× (`y_fail`: 0.0513 measured) and 1.21× (`y_mode`: 0.0605 measured)",
       "worst-split exceedance")
for s in ("+0.026…+0.065", "+0.270…+0.339"):
    in_doc(s, "headline delta range")
check("verdict 8/8", "8/8", D["verdict"]["calibration_summary"]["levels_controlled_at_alpha"])
for t in ("y_fail", "y_mode"):
    check(f"verdict beats pos {t}", True, D["verdict"]["summary_by_task"][t]["beats_position"])
    check(f"verdict beats every {t}", True, D["verdict"]["summary_by_task"][t]["beats_every_baseline"])
in_doc("beats every baseline on identical rows and folds", "verdict prose")

print(f"checks: {checks}, failures: {len(fails)}")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
