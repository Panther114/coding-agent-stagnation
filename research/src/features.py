"""Online, reference-free window features for stagnation monitoring.

For every trajectory and every window of ``w`` steps we compute features that a
runtime could compute at that moment: only the task statement, the actions and the
observations seen so far.  No gold patch, no future steps, no hidden tests and no
final reward enters this module; final reward and corpus statistics are attached by
the evaluation code, for analysis only.

Channels
--------
REP   action repetition (exact / normalized / target-level / command-family)
NOV   raw informational novelty (entities never seen before; relevance-blind)
EVID  task-grounded evidence gain (novel *and* task-relevant entities)
VER   verification deltas (test/build/error state changes)
WORK  workspace dynamics (edit targets, churn, re-edits)
SEM   semantic novelty of action+observation text (injected embeddings)
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from evidence import ObsState, extract_entities, extract_state, relevance
from normalize import NormAction

CHANNELS = ["REP", "NOV", "EVID", "VER", "WORK", "SEM"]
FEATURE_CHANNEL: Dict[str, str] = {}


def _reg(channel: str, names: Sequence[str]) -> None:
    for n in names:
        FEATURE_CHANNEL[n] = channel


_reg("REP", [
    "rep_exact_frac", "rep_norm_frac", "rep_target_frac", "rep_cmdfam_frac", "rep_searchterm_frac",
    "rep_exact_maxrepeat", "rep_cycle", "rep_global_recurrence",
])
_reg("NOV", [
    "nov_new_entity_frac", "nov_new_entity_rate", "nov_new_path_rate", "nov_new_symbol_rate",
    "nov_new_exc_rate", "nov_new_testid_rate", "nov_obs_chars", "nov_distinct_sig_frac",
])
_reg("EVID", [
    "ev_new_relevant_rate", "ev_new_relevant_frac", "ev_relevance_mean", "ev_relevance_max",
    "ev_new_highrel_rate", "ev_persist_rate", "ev_rel_weighted_novelty",
])
_reg("VER", [
    "ver_n_verify", "ver_n_improve", "ver_n_regress", "ver_progress", "ver_stall_len",
    "ver_same_errorsig_frac", "ver_passed_delta", "ver_failed_delta", "ver_novel_errorsig_rate",
    "ver_exit_success_frac", "ver_has_improvement",
])
_reg("WORK", [
    "wk_n_edit", "wk_new_edit_target_frac", "wk_churn_rate", "wk_reedit_rate",
    "wk_net_new_edited_targets", "wk_edit_after_complete",
])
_reg("SEM", ["sem_diversity", "sem_nearest_sim", "sem_centroid_dist", "sem_novelty_rate"])

ALL_FEATURES: List[str] = [f for f in FEATURE_CHANNEL]
META_FEATURES = ["_n_actions", "_step", "_window"]


@dataclass
class StepView:
    """Per-step observable record."""

    index: int
    actions: List[NormAction]
    obs_state: ObsState
    entities: List[Tuple[str, str]]              # (kind, value)
    obs_chars: int
    text_chars: int
    sig_keys: List[str]
    cmd_keys: List[str]
    target_keys: List[str]
    search_keys: List[str]
    kind_counts: Dict[str, int]
    edit_targets: List[str]
    n_actions: int
    step_terms: Set[str] = field(default_factory=set)
    # kept as a numpy row (not a list) to avoid materialising ~10^8 Python floats
    sem_vec: Optional["np.ndarray"] = None

    @property
    def entity_keys(self) -> List[str]:
        return [f"{k}|{v}" for k, v in self.entities]


@dataclass
class TrajView:
    traj_id: str
    task: str
    agent: str
    model: str
    reward: Optional[int]
    steps: List[StepView]
    idf: Dict[str, float] = field(default_factory=dict)
    finish_step: Optional[int] = None
    has_sem: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def n_steps(self) -> int:
        return len(self.steps)


# --------------------------------------------------------------------------------------
# View construction
# --------------------------------------------------------------------------------------


def _h(s: str) -> str:
    return hashlib.blake2b(s.encode("utf-8", "ignore"), digest_size=8).hexdigest()


def build_step_view(index: int, text: str, actions: Sequence[NormAction], obs: str,
                    terms: Set[str], idf: Dict[str, float]) -> StepView:
    st = extract_state(obs)
    ents: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for src in ("obs", "action", "agent"):
        if src == "obs":
            payload = obs
        elif src == "action":
            payload = " ".join(a.signature for a in actions)
        else:
            payload = text
        for e in extract_entities(payload, src):
            if e.key not in seen:
                seen.add(e.key)
                ents.append((e.kind, e.value))

    sig_keys = [_h(a.signature) for a in actions]
    cmd_keys: List[str] = []
    target_keys: List[str] = []
    search_keys: List[str] = []
    edit_targets: List[str] = []
    kind_counts: Dict[str, int] = {}
    for a in actions:
        kind_counts[a.kind] = kind_counts.get(a.kind, 0) + 1
        for c in a.commands:
            cmd_keys.append(_h(c[:200]))
        for t in a.targets:
            target_keys.append(_h(t))
        for t in a.search_terms:
            search_keys.append(_h(t))
        if a.kind == "edit":
            edit_targets.extend(a.targets or [f"verb::{a.verb}"])

    # task-vocabulary terms this step exposes, computed once per step so that window
    # features never have to rescan the trajectory prefix
    step_terms: Set[str] = set()
    for t in _TERM_RE.findall(obs.lower()):
        if len(t) >= 4:
            step_terms.add(t)
    for a in actions:
        for t in _TERM_RE.findall(a.signature.lower()):
            if len(t) >= 4:
                step_terms.add(t)

    return StepView(
        index=index,
        actions=list(actions),
        obs_state=st,
        entities=ents,
        obs_chars=len(obs or ""),
        text_chars=len(text or ""),
        sig_keys=sig_keys,
        cmd_keys=cmd_keys,
        target_keys=target_keys,
        search_keys=search_keys,
        kind_counts=kind_counts,
        edit_targets=edit_targets,
        n_actions=len(actions),
        step_terms=step_terms,
    )


_TERM_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")


def _state_is_verification(s: ObsState) -> bool:
    return (s.exit_code is not None or s.n_failed is not None or s.n_passed is not None
            or s.build_ok is not None or s.error_sig is not None or s.crashed or s.timed_out)


def _state_score(s: ObsState) -> float:
    """Monotone scalar summary of an observed verification state (higher = better)."""
    score = 0.0
    if s.exit_code is not None:
        score += 1.0 if s.exit_code == 0 else -1.0
    if s.n_passed is not None:
        score += min(s.n_passed, 200) / 10.0
    if s.n_failed is not None:
        score -= min(s.n_failed, 200) / 10.0
    if s.build_ok is True:
        score += 2.0
    elif s.build_ok is False:
        score -= 2.0
    if s.crashed:
        score -= 1.0
    if s.timed_out:
        score -= 0.3
    return score


def _cos(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return num / (na * nb)


# --------------------------------------------------------------------------------------
# Window features
# --------------------------------------------------------------------------------------


def _dup_frac(seq: Sequence[str]) -> Tuple[float, int]:
    if not seq:
        return 0.0, 0
    c = Counter(seq)
    return sum(v - 1 for v in c.values()) / len(seq), max(c.values())


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def compute_window_features(view: TrajView, t: int, w: int,
                            first_seen_global: Dict[str, int],
                            cfg: Dict[str, Any]) -> Dict[str, float]:
    """Features for the window of ``w`` steps ending at step ``t`` (inclusive).

    Only ``steps[:t+1]`` is read, so the computation is genuinely online.
    """
    lo = max(0, t - w + 1)
    win = view.steps[lo: t + 1]
    f: Dict[str, float] = {}

    # ---------------- REP ----------------
    sigs = [k for s in win for k in s.sig_keys]
    cmds = [k for s in win for k in s.cmd_keys]
    tgts = [k for s in win for k in s.target_keys]
    sterms = [k for s in win for k in s.search_keys]
    fams = [max(s.kind_counts, key=s.kind_counts.get) if s.kind_counts else "none" for s in win]

    f["rep_exact_frac"], f["rep_exact_maxrepeat"] = _dup_frac(sigs)
    f["rep_norm_frac"], _ = _dup_frac(cmds)
    f["rep_target_frac"], _ = _dup_frac(tgts)
    f["rep_cmdfam_frac"], _ = _dup_frac(fams)
    f["rep_searchterm_frac"], _ = _dup_frac(sterms)

    cyc = 0.0
    if len(sigs) >= 6:
        for p in (2, 3, 4):
            if len(sigs) >= 2 * p:
                hits = sum(1 for i in range(p, len(sigs)) if sigs[i] == sigs[i - p])
                cyc = max(cyc, hits / (len(sigs) - p))
    f["rep_cycle"] = cyc

    if sigs:
        rec = sum(1 for i, k in enumerate(sigs) if first_seen_global.get(k, 10**9) < lo)
        f["rep_global_recurrence"] = rec / len(sigs)
    else:
        f["rep_global_recurrence"] = 0.0

    # ---------------- NOV / EVID ----------------
    # first-seen index of every entity, computed once per trajectory
    win_keys: List[str] = []
    n_ent_slots = 0
    for s in win:
        ks = s.entity_keys
        win_keys.extend(ks)
        n_ent_slots += len(ks)

    new_mask = [k for k in win_keys if first_seen_global.get(k, 10**9) >= lo]
    n_new = len(set(new_mask))
    f["nov_new_entity_rate"] = n_new / len(win)
    f["nov_new_entity_frac"] = n_new / max(1, len(set(win_keys)))

    def new_rate(kind: str) -> float:
        ks = {k for k in win_keys if k.startswith(kind + "|")}
        nk = {k for k in ks if first_seen_global.get(k, 10**9) >= lo}
        return len(nk) / len(win)

    f["nov_new_path_rate"] = new_rate("path")
    f["nov_new_symbol_rate"] = new_rate("symbol")
    f["nov_new_exc_rate"] = new_rate("exception")
    f["nov_new_testid_rate"] = new_rate("testid")
    f["nov_obs_chars"] = _mean([s.obs_chars for s in win])
    f["nov_distinct_sig_frac"] = len(set(sigs)) / max(1, len(sigs))

    thr = float(cfg.get("rel_threshold", 0.5))
    idf = view.idf
    terms = cfg["_terms"]
    rel_of = {k: relevance([k.split("|", 1)[1]], terms, idf) for k in set(win_keys)}
    rel_vals = list(rel_of.values())
    f["ev_relevance_mean"] = _mean(rel_vals)
    f["ev_relevance_max"] = max(rel_vals) if rel_vals else 0.0
    new_rel = [(k, rel_of[k]) for k in new_mask]
    f["ev_new_relevant_rate"] = sum(1 for _, r in new_rel if r >= thr) / len(win)
    f["ev_new_relevant_frac"] = sum(1 for _, r in new_rel if r >= thr) / max(1, len(new_rel))
    f["ev_new_highrel_rate"] = sum(1 for _, r in new_rel if r >= 0.8) / len(win)
    f["ev_rel_weighted_novelty"] = sum(r for _, r in new_rel) / len(win)

    in_win_count = Counter(win_keys)
    persist = sum(1 for k, _ in new_rel if in_win_count[k] >= 2)
    f["ev_persist_rate"] = persist / len(win)

    # novel task-vocabulary terms appearing in observations (term level, not entity level).
    # ``_terms_prefix`` is a per-trajectory memo of the cumulative term set, so building the
    # prefix vocabulary stays linear instead of rescanning the trajectory for every window.
    memo: Dict[int, Set[str]] = cfg.setdefault("_terms_prefix", {})
    if lo == 0:
        seen_terms: Set[str] = set()
        memo[0] = set()
    else:
        seen_terms = memo.get(lo)
        if seen_terms is None:
            prev = memo.get(lo - 1)
            if prev is None:
                prev = set()
                for s in view.steps[:lo - 1]:
                    prev |= s.step_terms
            seen_terms = prev | view.steps[lo - 1].step_terms
            memo[lo] = seen_terms
    new_terms: Set[str] = set()
    for s in win:
        new_terms |= (s.step_terms - seen_terms)
    new_terms &= terms
    f["ev_new_term_rate"] = len(new_terms) / len(win)

    # ---------------- VER ----------------
    n_ver = sum(1 for s in win if _state_is_verification(s.obs_state))
    f["ver_n_verify"] = float(n_ver)
    prev: Optional[ObsState] = None
    improve = regress = novel_sig = 0
    passed_delta = failed_delta = 0.0
    for s in win:
        cur = s.obs_state
        if not _state_is_verification(cur):
            continue
        if prev is not None:
            a, b = _state_score(cur), _state_score(prev)
            if a > b:
                improve += 1
            elif a < b:
                regress += 1
            if cur.n_passed is not None and prev.n_passed is not None:
                passed_delta += cur.n_passed - prev.n_passed
            if cur.n_failed is not None and prev.n_failed is not None:
                failed_delta += cur.n_failed - prev.n_failed
            if cur.error_sig and cur.error_sig != prev.error_sig:
                novel_sig += 1
        prev = cur
    f["ver_n_improve"] = float(improve)
    f["ver_n_regress"] = float(regress)
    f["ver_progress"] = float(improve - regress)
    f["ver_has_improvement"] = 1.0 if improve > 0 else 0.0
    f["ver_passed_delta"] = passed_delta
    f["ver_failed_delta"] = failed_delta
    f["ver_novel_errorsig_rate"] = novel_sig / max(1, n_ver - 1)
    sigs_all = [s.obs_state.error_sig for s in win if s.obs_state.error_sig]
    f["ver_same_errorsig_frac"] = (max(Counter(sigs_all).values()) / max(1, len(sigs_all))) if sigs_all else 0.0
    f["ver_exit_success_frac"] = sum(1 for s in win if s.obs_state.exit_code == 0) / max(1, n_ver)

    last_improve: Optional[int] = None
    first_ver: Optional[int] = None
    prev2: Optional[ObsState] = None
    for si in range(0, t + 1):
        cur = view.steps[si].obs_state
        if not _state_is_verification(cur):
            continue
        if first_ver is None:
            first_ver = si
        if prev2 is not None and _state_score(cur) > _state_score(prev2):
            last_improve = si
        prev2 = cur
    f["ver_stall_len"] = 0.0 if first_ver is None else float(t - (last_improve if last_improve is not None else first_ver))

    # ---------------- WORK ----------------
    edits = [s for s in win if s.kind_counts.get("edit")]
    f["wk_n_edit"] = float(len(edits))
    edit_targets_all = [tt for s in win for tt in s.edit_targets]
    if edits:
        new_t = sum(1 for tt in edit_targets_all if first_seen_global.get(f"target|{tt}", 10**9) >= lo)
        f["wk_new_edit_target_frac"] = new_t / max(1, len(edit_targets_all))
    else:
        f["wk_new_edit_target_frac"] = 0.0
    tc = Counter(edit_targets_all)
    f["wk_churn_rate"] = sum(v - 1 for v in tc.values()) / max(1, len(edit_targets_all))
    f["wk_reedit_rate"] = sum(1 for v in tc.values() if v > 1) / max(1, len(tc))
    f["wk_net_new_edited_targets"] = float(sum(1 for v in tc.values() if v == 1))
    if view.finish_step is None:
        f["wk_edit_after_complete"] = 0.0
    else:
        f["wk_edit_after_complete"] = float(
            sum(1 for s in win if s.index > view.finish_step and s.kind_counts.get("edit")))

    # ---------------- SEM ----------------
    if view.has_sem:
        vecs = [s.sem_vec for s in win if s.sem_vec is not None]
        if len(vecs) >= 2:
            M = np.asarray(vecs, dtype=np.float64)
            if M.shape[0] >= 2:
                sims = np.abs(M @ M.T)
                iu = np.triu_indices(M.shape[0], k=1)
                f["sem_diversity"] = 1.0 - float(np.mean(sims[iu]))
                last = M[-1]
                prev = M[:-1]
                denom = (np.linalg.norm(prev, axis=1) * (np.linalg.norm(last) + 1e-12)) + 1e-12
                f["sem_nearest_sim"] = float(np.max(np.abs(prev @ last) / denom))
                cent = M.mean(axis=0)
                nc = float(np.linalg.norm(cent))
                f["sem_centroid_dist"] = 1.0 - (abs(float(last @ cent)) / (nc + 1e-12)
                                                if nc > 1e-12 else 0.0)
            else:
                for k in ("sem_diversity", "sem_nearest_sim", "sem_centroid_dist"):
                    f[k] = float("nan")
            hist = [s.sem_vec for s in view.steps[:lo] if s.sem_vec is not None]
            if hist:
                H = np.asarray(hist, dtype=np.float64)
                last = np.asarray(vecs[-1], dtype=np.float64)
                denom = (np.linalg.norm(H, axis=1) * (np.linalg.norm(last) + 1e-12)) + 1e-12
                f["sem_novelty_rate"] = 1.0 - float(np.max(np.abs(H @ last) / denom))
            else:
                f["sem_novelty_rate"] = 1.0
        else:
            for k in ("sem_diversity", "sem_nearest_sim", "sem_centroid_dist", "sem_novelty_rate"):
                f[k] = float("nan")
    else:
        for k in ("sem_diversity", "sem_nearest_sim", "sem_centroid_dist", "sem_novelty_rate"):
            f[k] = float("nan")

    f["_n_actions"] = float(sum(s.n_actions for s in win))
    f["_step"] = float(t)
    f["_window"] = float(w)
    return f


def first_seen_index(view: TrajView) -> Dict[str, int]:
    """Step index at which each entity/target key was first observed."""
    out: Dict[str, int] = {}
    for s in view.steps:
        for k in s.entity_keys:
            out.setdefault(k, s.index)
        for a in s.actions:
            for t in a.targets:
                out.setdefault(f"target|{t}", s.index)
        for k in s.sig_keys:
            out.setdefault(k, s.index)
    return out
