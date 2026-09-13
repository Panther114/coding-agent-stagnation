"""Monitor zoo: hand-designed channel monitors plus learned variants.

Each hand-designed monitor is a signed, standardised sum of features squashed through a
logistic.  ``direction`` is +1 when a larger feature value indicates *stagnation* and -1
when a larger value indicates *productive* activity.

The monitor set implements the ablation the paper reports:

  B1  step budget                        - trivial lower baseline
  B2  exact/normalized action repetition - string-level guard
  B3  command-family / target repetition - coarser repetition guard
  B4  semantic redundancy                - embedding-diversity style baseline (SEM)
  B5  relevance-blind novelty            - how far raw novelty alone gets (NOV)
  B6  verification only                  - objective verification deltas (VER)
  B7  workspace only                     - edit/churn dynamics (WORK)
  C1  task-grounded evidence             - novel *and relevant* entities (EVID)
  C2  evidence + verification            - the proposed combination
  C3  evidence + semantic novelty        - does task grounding add to diversity?
  C4  all hand-designed channels
  L*  logistic regression per channel and per combination (task-disjoint trained)
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from features import ALL_FEATURES, FEATURE_CHANNEL
from monitors import ExactRepeat, FeatureMonitor, StepBudget


def _cols(channel: str) -> List[str]:
    return [f for f in ALL_FEATURES if FEATURE_CHANNEL.get(f) == channel]


def _signed(features: Sequence[str], positive_is_stagnant: Sequence[str]) -> Tuple[List[str], List[int]]:
    pos = set(positive_is_stagnant)
    return list(features), [1 if f in pos else -1 for f in features]


SEM_FEATURES = ["sem_diversity", "sem_novelty_rate", "sem_nearest_sim", "sem_centroid_dist"]

SEM_STAGNANT = ["sem_nearest_sim", "sem_centroid_dist"]      # high similarity => stagnant
SEM_PRODUCTIVE = ["sem_diversity", "sem_novelty_rate"]       # high diversity => productive

REP_FEATURES = _cols("REP")
REP_STAGNANT = ["rep_exact_frac", "rep_norm_frac", "rep_target_frac", "rep_cmdfam_frac",
                "rep_searchterm_frac", "rep_exact_maxrepeat", "rep_cycle", "rep_global_recurrence"]

NOV_FEATURES = _cols("NOV")
NOV_PRODUCTIVE = ["nov_new_entity_rate", "nov_new_path_rate", "nov_new_symbol_rate",
                  "nov_new_exc_rate", "nov_new_testid_rate", "nov_distinct_sig_frac"]
NOV_STAGNANT = ["nov_obs_chars"]

EVID_FEATURES = _cols("EVID")
EVID_PRODUCTIVE = ["ev_new_relevant_rate", "ev_new_relevant_frac", "ev_new_highrel_rate",
                   "ev_persist_rate", "ev_rel_weighted_novelty", "ev_relevance_max"]

VER_FEATURES = _cols("VER")
VER_PRODUCTIVE = ["ver_progress", "ver_has_improvement", "ver_passed_delta", "ver_n_improve",
                  "ver_novel_errorsig_rate", "ver_exit_success_frac"]
VER_STAGNANT = ["ver_stall_len", "ver_same_errorsig_frac", "ver_n_regress", "ver_failed_delta"]

WORK_FEATURES = _cols("WORK")
WORK_PRODUCTIVE = ["wk_net_new_edited_targets", "wk_new_edit_target_frac"]
WORK_STAGNANT = ["wk_churn_rate", "wk_reedit_rate", "wk_edit_after_complete", "wk_n_edit"]


def _mix(features: Sequence[str], stagnant: Sequence[str]) -> Tuple[List[str], List[int]]:
    f = list(features)
    return f, [1 if x in set(stagnant) else -1 for x in f]


def build_monitors(lr_monitors: Dict[str, Any], has_sem: bool = True) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    out["B1_step30"] = StepBudget(30)
    out["B1_step60"] = StepBudget(60)
    out["B2_exact_rep3"] = ExactRepeat(3)
    out["B2_exact_rep5"] = ExactRepeat(5)

    out["B3_rep_channel"] = FeatureMonitor("B3_rep_channel", * _signed(REP_FEATURES, REP_STAGNANT))
    out["B3_rep_target"] = FeatureMonitor(
        "B3_rep_target", ["rep_target_frac", "rep_cmdfam_frac", "rep_searchterm_frac",
                          "rep_cycle", "rep_global_recurrence"],
        [1, 1, 1, 1, 1])
    if SEM_FEATURES and has_sem:
        out["B4_semantic"] = FeatureMonitor("B4_semantic", SEM_FEATURES,
                                            [1 if f in SEM_STAGNANT else -1 for f in SEM_FEATURES])
        out["B4_sem_diversity"] = FeatureMonitor("B4_sem_diversity", ["sem_diversity"], [-1])
    out["B5_novelty"] = FeatureMonitor("B5_novelty", *_mix(NOV_FEATURES, NOV_STAGNANT))
    out["B5_novelty_sig"] = FeatureMonitor("B5_novelty_sig", ["nov_distinct_sig_frac"], [-1])
    out["B6_verification"] = FeatureMonitor("B6_verification", *_mix(VER_FEATURES, VER_STAGNANT))
    out["B6_ver_stall"] = FeatureMonitor("B6_ver_stall", ["ver_stall_len"], [1])
    out["B7_workspace"] = FeatureMonitor("B7_workspace", *_mix(WORK_FEATURES, WORK_STAGNANT))
    out["C1_evidence"] = FeatureMonitor("C1_evidence", *_mix(EVID_FEATURES, []))
    out["C1_evidence_rel"] = FeatureMonitor(
        "C1_evidence_rel", ["ev_new_relevant_rate", "ev_new_highrel_rate", "ev_persist_rate"], [-1, -1, -1])
    out["C2_evid_ver"] = FeatureMonitor(
        "C2_evid_ver", EVID_FEATURES + VER_FEATURES, *_mix(EVID_FEATURES + VER_FEATURES, VER_STAGNANT)[1:])
    out["C2_evid_ver_work"] = FeatureMonitor(
        "C2_evid_ver_work", EVID_FEATURES + VER_FEATURES + WORK_FEATURES,
        *_mix(EVID_FEATURES + VER_FEATURES + WORK_FEATURES, VER_STAGNANT + WORK_STAGNANT)[1:])
    if SEM_FEATURES and has_sem:
        out["C3_evid_sem"] = FeatureMonitor(
            "C3_evid_sem", EVID_FEATURES + SEM_FEATURES,
            *_mix(EVID_FEATURES + SEM_FEATURES, SEM_STAGNANT)[1:])
    allf = REP_FEATURES + NOV_FEATURES + EVID_FEATURES + VER_FEATURES + WORK_FEATURES
    out["C4_all_hand"] = FeatureMonitor(
        "C4_all_hand", allf, *_mix(allf, REP_STAGNANT + VER_STAGNANT + WORK_STAGNANT + NOV_STAGNANT)[1:])

    for name, mon in lr_monitors.items():
        out["L_" + name] = mon
    return out


def monitor_feature_groups(has_sem: bool = True) -> Dict[str, List[str]]:
    """Feature subsets used by the learned logistic monitors (the ablation)."""
    groups: Dict[str, List[str]] = {
        "rep": REP_FEATURES,
        "nov": NOV_FEATURES,
        "evid": EVID_FEATURES,
        "ver": VER_FEATURES,
        "work": WORK_FEATURES,
        "evid_ver": EVID_FEATURES + VER_FEATURES,
        "evid_nov": EVID_FEATURES + NOV_FEATURES,
        "all_hand": REP_FEATURES + NOV_FEATURES + EVID_FEATURES + VER_FEATURES + WORK_FEATURES,
    }
    if has_sem:
        groups["sem"] = SEM_FEATURES
        groups["evid_sem"] = EVID_FEATURES + SEM_FEATURES
        groups["all_sem"] = (REP_FEATURES + NOV_FEATURES + EVID_FEATURES + VER_FEATURES
                             + WORK_FEATURES + SEM_FEATURES)
    return groups
