"""Main experiment runner: window-level and alarm-level evaluation of every monitor.

Design
------
* Feature caches are built once for every trajectory in the analysis sample, so all folds
  reuse identical features.
* Monitors are evaluated with **task-level k-fold cross-validation**: for each fold, models
  are trained and standardised on the training tasks only, and scored on the held-out tasks.
  Every annotated trajectory is therefore evaluated exactly once, by a model that never saw
  its task --- which is what a runtime would face on a new project.
* Window-level evaluation uses every annotated window; alarm-level evaluation runs each
  monitor sequentially and asks whether the first alarm lands in an annotated stagnant
  region at fixed false-stop budgets.  Savings are signed, so a false stop costs.
* All per-window features and per-step scores are exported, so every table and figure can be
  regenerated without recomputation.

Usage:
  python scripts/run_experiments.py --corpus tb2 --w 10 --out results/final/tb2
  python scripts/run_experiments.py --corpus nebius --processed data/processed/nebius \
      --annotations ../datasets/annotations/nebius --transfer-from results/final/tb2 \
      --out results/final/nebius_transfer
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

import paths  # noqa: E402
from build_dataset import build_views, compute_idf  # noqa: E402
from evaluation import (TrajGold, alarm_metrics, alarm_outcome, budget_frontier,  # noqa: E402
                        precision_recall_at, savings_curve, summarise_curve_at, window_metrics,
                        within_group_auc)
from alarm_eval import (evaluate_from_step_alarms, summarise_window_frontier,  # noqa: E402
                        bootstrap_ci as boot_ci)
from evidence import task_terms  # noqa: E402
from features import ALL_FEATURES  # noqa: E402
from loaders import Action, Step, Trajectory, nebius_task_statements, tb2_task_statements  # noqa: E402
from monitors import (ExactRepeat, FeatureMonitor, LogisticMonitor, StepBudget,  # noqa: E402
                      WindowFeatureCache, alarmed_steps, budget_thresholds, sustained_alarm)
from run_config import build_monitors, monitor_feature_groups  # noqa: E402

DEFAULT_SEED = 0
BUDGETS = [0.01, 0.02, 0.05, 0.10, 0.20]


# --------------------------------------------------------------------------------------
# data helpers
# --------------------------------------------------------------------------------------


def load_gold(d: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    adj = list(csv.DictReader(open(os.path.join(d, "adjudicated.csv"), newline="", encoding="utf-8")))
    regions = json.load(open(os.path.join(d, "gold_regions.json"), encoding="utf-8"))
    agree = json.load(open(os.path.join(d, "agreement.json"), encoding="utf-8"))
    return {a["card_id"]: a for a in adj}, {"regions": regions, "agreement": agree, "rows": adj}


def load_sample(proc: str) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in open(os.path.join(proc, "sample_trajectories.jsonl"), encoding="utf-8")]


def build_view_objects(sample: Sequence[Dict[str, Any]]) -> List[Trajectory]:
    out = []
    for b in sample:
        steps = [Step(index=i, text=s["text"],
                      actions=[Action(a["name"], a["arg"]) for a in s["actions"]],
                      observation=s["obs"]) for i, s in enumerate(b["steps"])]
        out.append(Trajectory(traj_id=b["traj_id"], task=b["task"], agent=b["agent"], model=b["model"],
                              reward=b["reward"], steps=steps, meta=b["meta"]))
    return out


def attach_embeddings(views, proc: str) -> bool:
    emb_path = os.path.join(proc, "step_embeddings.npz")
    if not os.path.exists(emb_path):
        return False
    emb = np.load(emb_path)
    tids = list(emb["traj_ids"])
    offs = list(emb["offsets"])
    E = emb["embeddings"]
    start = {tid: int(o) for tid, o in zip(tids, offs)}
    end = {tid: (int(offs[i + 1]) if i + 1 < len(tids) else E.shape[0]) for i, tid in enumerate(tids)}
    n = 0
    for v in views:
        if v.traj_id not in start:
            continue
        seg = E[start[v.traj_id]: end[v.traj_id]]
        for s in v.steps:
            if s.index < len(seg):
                s.sem_vec = seg[s.index]
        v.has_sem = True
        n += 1
    return n > 0


def make_folds(task_counts: Dict[str, int], k: int, seed: int = DEFAULT_SEED) -> List[List[str]]:
    """Task-level folds, balanced by how many annotated windows each task contributes.

    Greedy largest-first assignment: tasks with more annotations are placed first, into the
    fold that currently holds the fewest annotations.  This keeps the evaluation sets of the
    folds comparable even though the annotation budget is concentrated on a few tasks.
    """
    rng = np.random.default_rng(seed)
    items = sorted(task_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    # shuffle within equal sizes for reproducibility without bias
    order = sorted(items, key=lambda kv: (-kv[1], rng.random()))
    folds: List[List[str]] = [[] for _ in range(k)]
    load = [0] * k
    for task, cnt in order:
        j = int(np.argmin(load))
        folds[j].append(task)
        load[j] += max(1, cnt)
    return [sorted(f) for f in folds]


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------


def normalize_scores(s: np.ndarray, mode: str) -> np.ndarray:
    """Put a per-step score series on a comparable scale before thresholding.

    A single global threshold assumes that a score of 0.7 means the same thing in every
    trajectory.  It does not: monitors built from sparse features produce scores whose scale
    depends on the run.  Two reference normalisations are offered, because they trade realism
    against comparability:

    ``none``    raw scores (what the monitor outputs);
    ``traj``    z-score the whole trajectory (retrospective: uses the full run, so it is a
                reference bound rather than a deployable policy);
    ``online``  z-score against the running mean and standard deviation of the scores seen so
                far in this trajectory (deployable, fully online, no future information).
    """
    if mode == "none" or s.size == 0:
        return s
    if mode == "traj":
        mu, sd = float(np.nanmean(s)), float(np.nanstd(s)) + 1e-9
        z = (s - mu) / sd
    elif mode == "online":
        z = np.zeros_like(s)
        run_sum = 0.0
        run_sq = 0.0
        for i, v in enumerate(s):
            if v == v:
                run_sum += v
                run_sq += v * v
            n = i + 1
            mu = run_sum / n
            var = max(run_sq / n - mu * mu, 0.0)
            z[i] = (v - mu) / (var ** 0.5 + 1e-6)
    else:
        return s
    # map to (0,1) with a fixed slope so that the threshold sweep stays on a common scale
    return 0.5 + 0.5 * np.clip(z / 3.0, -1.0, 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tb2")
    ap.add_argument("--processed", default=None)
    ap.add_argument("--annotations", default=None)
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--w-extra", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--transfer-from", default=None)
    ap.add_argument("--min-step-margin", type=int, default=5)
    ap.add_argument("--tolerance", type=int, default=2,
                    help="steps of tolerance when crediting an alarm to an annotated window")
    ap.add_argument("--alarm-normalize", choices=["none", "traj", "online"], default="traj",
                    help="how per-step scores are put on a common scale before thresholding")
    ap.add_argument("--min-traj-windows", type=int, default=2,
                    help="annotated windows a trajectory needs before it enters alarm metrics")
    args = ap.parse_args()

    t0 = time.time()
    proc = args.processed or os.path.join(paths.PROCESSED, args.corpus)
    ann = args.annotations or os.path.join(paths.DATA, "annotations", args.corpus)
    os.makedirs(args.out, exist_ok=True)
    windows = [args.w] + ([args.w_extra] if args.w_extra else [])

    sample = load_sample(proc)
    trajs = build_view_objects(sample)
    statements = tb2_task_statements() if args.corpus == "tb2" else nebius_task_statements()
    by_card, gold = load_gold(ann)
    regions = gold["regions"]
    print(f"[{time.time()-t0:.0f}s] {len(trajs)} trajectories; gold {len(by_card)} windows over "
          f"{len(regions)} trajectories {gold['agreement']['labels']}")

    views = build_views(trajs, statements)
    idf = compute_idf(views, args.corpus)
    for v in views:
        v.idf = idf
    has_sem = attach_embeddings(views, proc)
    view_by_id = {v.traj_id: v for v in views}
    print(f"[{time.time()-t0:.0f}s] views built; semantic embeddings: {has_sem}")

    # ---------- caches (built once) ----------
    caches: Dict[str, Dict[int, WindowFeatureCache]] = {}
    for vi, v in enumerate(views):
        cfg_v = {"_terms": task_terms(statements.get(v.task, "")), "rel_threshold": 0.5}
        caches[v.traj_id] = {w: WindowFeatureCache(v, w, cfg_v) for w in windows}
        if vi % 400 == 0:
            print(f"[{time.time()-t0:.0f}s] caches {vi}/{len(views)}")
    print(f"[{time.time()-t0:.0f}s] caches built for {len(caches)} trajectories")

    # ---------- folds ----------
    task_counts: Dict[str, int] = Counter()
    for a in by_card.values():
        task_counts[a["task"]] += 1
    for v in views:
        task_counts.setdefault(v.task, 0)
    all_tasks = sorted(task_counts)
    folds = make_folds(task_counts, args.folds, args.seed)
    print(f"folds: {[len(f) for f in folds]} tasks; annotated windows per fold: "
          f"{[sum(task_counts[t] for t in f) for f in folds]}")

    thresholds = [round(x, 3) for x in np.arange(0.30, 1.0001, 0.02)]
    transfer_meta = None
    transfer_models: Dict[str, Dict[str, Any]] = {}
    if args.transfer_from:
        src = os.path.join(args.transfer_from, "logistic_models.json")
        if os.path.exists(src):
            transfer_models = json.load(open(src, encoding="utf-8"))
            transfer_meta = {"source": args.transfer_from, "n_models": len(transfer_models)}
            print(f"loaded {len(transfer_models)} transferred models from {src}")

    # accumulators across folds
    score_rows: List[Dict[str, Any]] = []
    window_rows: List[Dict[str, Any]] = []
    first_alarm: Dict[str, Dict[str, Dict[int, Dict[float, Optional[int]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict)))
    alarm_steps: Dict[str, Dict[str, Dict[int, Dict[float, List[int]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict)))
    budget_alarms: Dict[str, Dict[str, Dict[int, Dict[float, List[int]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict)))
    budget_first: Dict[str, Dict[str, Dict[int, Dict[float, Optional[int]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict)))
    budget_thr_used: Dict[str, Dict[str, Dict[float, float]]] = defaultdict(
        lambda: defaultdict(dict))
    fold_report: List[Dict[str, Any]] = []
    lr_coef_summary: Dict[str, List[Dict[str, float]]] = defaultdict(list)

    for fi, fold_tasks in enumerate(folds):
        fold_set = set(fold_tasks)
        train_ids = [v.traj_id for v in views if v.task not in fold_set]
        test_ids = [v.traj_id for v in views if v.task in fold_set]
        # training rows: annotated windows of the training tasks
        train_rows: List[Dict[str, Any]] = []
        for tid in train_ids:
            for w in windows:
                c = caches[tid][w]
                for t in range(c.n):
                    a = by_card.get(f"{args.corpus}_{tid}_{t}")
                    if a is None or a["binary"] == "":
                        continue
                    row = {"binary": int(a["binary"])}
                    for j, f in enumerate(ALL_FEATURES):
                        row[f] = float(c.X[t, j])
                    train_rows.append(row)
        y_train = np.array([r["binary"] for r in train_rows], dtype=int) if train_rows else np.zeros(0, dtype=int)

        lr_monitors: Dict[str, LogisticMonitor] = {}
        if y_train.size and len(np.unique(y_train)) > 1:
            for name, cols in monitor_feature_groups(has_sem).items():
                X = np.array([[r[f] for f in cols] for r in train_rows], dtype=np.float64)
                X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
                mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-9
                clf = LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced",
                                         random_state=args.seed)
                clf.fit((X - mu) / sd, y_train)
                lr_monitors[name] = LogisticMonitor(name, clf, cols, mu, sd)
                lr_coef_summary[name].append({
                    "fold": fi, "n": int(y_train.size), "pos": int(y_train.sum()),
                    "intercept": float(clf.intercept_[0]),
                    **{c: float(w) for c, w in zip(cols, clf.coef_[0])}})
        for name, s in transfer_models.items():
            clf = LogisticRegression()
            clf.coef_ = np.asarray([s["coef_values"]], dtype=float)
            clf.intercept_ = np.asarray([s["intercept"]], dtype=float)
            clf.classes_ = np.asarray([0, 1])
            lr_monitors["transfer_" + name] = LogisticMonitor(
                "transfer_" + name, clf, s["features"], np.asarray(s["mu"], dtype=float),
                np.asarray(s["sd"], dtype=float))

        monitors = build_monitors(lr_monitors, has_sem=has_sem)
        Xs = [caches[tid][w].X for tid in train_ids for w in windows]
        if Xs:
            Xtr = np.vstack(Xs)
            for m in monitors.values():
                if isinstance(m, FeatureMonitor):
                    m.fit(Xtr)

        # ---- calibrate alarm thresholds on the training trajectories ----
        budget_thr: Dict[str, Dict[int, Dict[float, float]]] = {}
        for w in windows:
            train_scores = {name: [] for name in monitors}
            for tid in train_ids[:400]:
                c = caches[tid][w]
                for name, mon in monitors.items():
                    train_scores[name].append(np.asarray(mon.score_series(c), dtype=float))
            for name in monitors:
                thr_map = budget_thresholds(train_scores[name], k=2, budgets=BUDGETS,
                                            min_step=args.min_step_margin)
                budget_thr.setdefault(name, {})[w] = thr_map
                budget_thr_used[name][w] = {float(b): float(t) for b, t in thr_map.items()}

        # ---- export per-window features and score every test trajectory ----
        n_lab = 0
        for tid in test_ids:
            v = view_by_id[tid]
            for w in windows:
                c = caches[tid][w]
                for t in range(c.n):
                    card_id = f"{args.corpus}_{tid}_{t}"
                    a = by_card.get(card_id)
                    dcard = by_card.get(f"d_{args.corpus}_{tid}_{t}")
                    ann_row = a or dcard
                    row = {"traj_id": tid, "task": v.task, "agent": v.agent, "model": v.model,
                           "reward": v.reward, "n_steps": v.n_steps, "t": t, "w": w,
                           "card_id": card_id, "fold": fi,
                           "gold": ann_row["gold"] if ann_row else "",
                           "kind": ann_row["kind"] if ann_row else "",
                           "detail": ann_row["detail"] if ann_row else "",
                           "binary": (int(ann_row["binary"]) if ann_row and ann_row["binary"] != "" else None),
                           "reason": (ann_row["reason"][:180] if ann_row else "")}
                    for j, f in enumerate(ALL_FEATURES):
                        row[f] = float(c.X[t, j])
                    window_rows.append(row)
                    if ann_row is not None and ann_row["binary"] != "":
                        n_lab += 1
                for name, mon in monitors.items():
                    s = np.asarray(mon.score_series(c), dtype=float)
                    s = normalize_scores(s, args.alarm_normalize)
                    for t in range(min(len(s), v.n_steps)):
                        score_rows.append({"traj_id": tid, "task": v.task, "agent": v.agent,
                                           "model": v.model, "reward": v.reward, "t": t, "w": w,
                                           "monitor": name, "fold": fi,
                                           "score": float(s[t]) if s[t] == s[t] else None})
                    for th in thresholds:
                        steps = alarmed_steps(s, th, k=2, min_step=args.min_step_margin)
                        first_alarm[name][w][tid][th] = (steps[0] if steps else None)
                        alarm_steps[name][w][tid][th] = steps
                    # budget-calibrated alarms: threshold = training quantile for each budget
                    for b, th in (budget_thr.get(name, {}).get(w) or {}).items():
                        if th != th:
                            continue
                        steps_b = alarmed_steps(s, th, k=2, min_step=args.min_step_margin)
                        budget_alarms[name][w][tid][b] = steps_b
                        budget_first[name][w][tid][b] = (steps_b[0] if steps_b else None)
        fold_report.append({"fold": fi, "n_test_traj": len(test_ids), "n_train_traj": len(train_ids),
                            "n_train_windows": len(train_rows), "n_test_labelled_windows": n_lab,
                            "tasks": fold_tasks})
        print(f"[{time.time()-t0:.0f}s] fold {fi}: test traj {len(test_ids)}, train labelled windows "
              f"{len(train_rows)} (pos {int(y_train.sum()) if y_train.size else 0}), test labelled "
              f"windows {n_lab}")

    print(f"[{time.time()-t0:.0f}s] exported {len(window_rows)} window rows, "
          f"{len(score_rows)} score rows")

    pq.write_table(pa.table({
        **{k: pa.array([r[k] for r in window_rows], type=pa.float64()) for k in ALL_FEATURES},
        "traj_id": pa.array([r["traj_id"] for r in window_rows], type=pa.string()),
        "task": pa.array([r["task"] for r in window_rows], type=pa.string()),
        "agent": pa.array([r["agent"] for r in window_rows], type=pa.string()),
        "model": pa.array([r["model"] for r in window_rows], type=pa.string()),
        "reward": pa.array([r["reward"] for r in window_rows], type=pa.int64()),
        "n_steps": pa.array([r["n_steps"] for r in window_rows], type=pa.int64()),
        "t": pa.array([r["t"] for r in window_rows], type=pa.int64()),
        "w": pa.array([r["w"] for r in window_rows], type=pa.int64()),
        "fold": pa.array([r["fold"] for r in window_rows], type=pa.int64()),
        "gold": pa.array([r["gold"] for r in window_rows], type=pa.string()),
        "kind": pa.array([r["kind"] for r in window_rows], type=pa.string()),
        "detail": pa.array([r["detail"] for r in window_rows], type=pa.string()),
        "binary": pa.array([r["binary"] for r in window_rows], type=pa.int64()),
        "card_id": pa.array([r["card_id"] for r in window_rows], type=pa.string()),
    }), os.path.join(args.out, "window_features.parquet"))
    pq.write_table(pa.Table.from_pylist(score_rows), os.path.join(args.out, "monitor_scores.parquet"))

    # ---------- window-level metrics ----------
    test_cards = [r for r in window_rows if r["binary"] is not None]
    lookup: Dict[Tuple[str, int, int, str], float] = {}
    for r in score_rows:
        if r["score"] is not None:
            lookup[(r["traj_id"], r["t"], r["w"], r["monitor"])] = r["score"]
    all_monitors = sorted({r["monitor"] for r in score_rows})
    wl: Dict[str, Any] = {}
    for name in all_monitors:
        wl[name] = {}
        for w in windows:
            sub = [r for r in test_cards if r["w"] == w]
            y, p, clusters = [], [], []
            for r in sub:
                sc = lookup.get((r["traj_id"], r["t"], w, name))
                if sc is None:
                    continue
                y.append(r["binary"]); p.append(sc); clusters.append(r["traj_id"])
            if not y:
                continue
            m = window_metrics(np.array(y), np.array(p))
            m["n_test_traj"] = float(len({r["traj_id"] for r in sub}))
            wauc, n_within = within_group_auc(np.array(y), np.array(p), clusters)
            m["within_traj_auc"] = wauc
            m["n_traj_with_both_classes"] = float(n_within)
            m["at_thresholds"] = {str(t): precision_recall_at(np.array(y), np.array(p), t)
                                  for t in (0.4, 0.5, 0.6, 0.7, 0.8)}
            m["per_agent"] = {}
            for ag in sorted({r["agent"] for r in sub}):
                rs = [r for r in sub if r["agent"] == ag]
                yy, pp = [], []
                for r in rs:
                    sc = lookup.get((r["traj_id"], r["t"], w, name))
                    if sc is not None:
                        yy.append(r["binary"]); pp.append(sc)
                if len(set(yy)) > 1 and len(yy) >= 8:
                    m["per_agent"][ag] = {"n": len(yy), **window_metrics(np.array(yy), np.array(pp))}
            # leave-one-scaffold-out: AUC on the scaffold held out entirely
            m["by_scaffold_auc"] = {ag: v["roc_auc"] for ag, v in m["per_agent"].items()}
            wl[name][w] = m

    # ---------- gold regions for alarm evaluation ----------
    gold_by_traj: Dict[str, TrajGold] = {}
    for tid, g in regions.items():
        if tid not in view_by_id or len(g["windows"]) < args.min_traj_windows:
            continue
        gold_by_traj[tid] = TrajGold(
            traj_id=tid, task=g["task"], agent=g["agent"], n_steps=g["n_steps"], reward=g["reward"],
            stagnant=[tuple(x) for x in g["stagnant_ranges"]],
            productive=[tuple(x) for x in g["productive_ranges"]], windows=g["windows"])
    print(f"alarm evaluation over {len(gold_by_traj)} annotated trajectories "
          f"({sum(1 for g in gold_by_traj.values() if g.stagnant)} with >=1 stagnant region)")

    # ---------- window-level alarm metrics (tolerant, all annotated windows) ----------
    # For each threshold: detection over annotated stagnant windows, false stops over
    # annotated productive windows, coverage over the unannotated windows.
    gold_windows: Dict[str, List[Dict[str, Any]]] = {}
    unlabelled_windows: Dict[str, List[Tuple[int, int]]] = {}
    for tid in {r["traj_id"] for r in window_rows}:
        wins = [r for r in window_rows if r["traj_id"] == tid and r["w"] == args.w]
        wins.sort(key=lambda r: r["t"])
        gl = [{"lo": max(0, r["t"] - r["w"] + 1), "hi": r["t"], "binary": r["binary"],
               "detail": r["detail"]} for r in wins if r["binary"] is not None]
        if gl:
            gold_windows[tid] = gl
        un = [(max(0, r["t"] - r["w"] + 1), r["t"]) for r in wins if r["binary"] is None]
        if un:
            unlabelled_windows[tid] = un
    win_alarm_curves: Dict[str, Any] = {}
    win_alarm_frontier: Dict[str, Any] = {}
    for name in all_monitors:
        per = alarm_steps[name][args.w]
        step_alarms = {th: {tid: per[tid].get(th, []) for tid in per} for th in thresholds}
        curve = evaluate_from_step_alarms(step_alarms, gold_windows, unlabelled_windows, tau=args.tolerance)
        win_alarm_curves[name] = curve
        win_alarm_frontier[name] = summarise_window_frontier(curve, BUDGETS)

    # ---------- budget-calibrated alarm metrics ----------
    # Here the operating point is fixed by the *budget* rather than by a score threshold: for
    # each budget we take the threshold whose training quantile matches that budget, so every
    # monitor is compared at the same firing rate rather than at the same raw score.
    budget_curves: Dict[str, Any] = {}
    budget_traj: Dict[str, Any] = {}
    for name in all_monitors:
        rows: List[Dict[str, Any]] = []
        traj_rows: Dict[str, List[Dict[str, Any]]] = {}
        for b in BUDGETS:
            per_b = budget_alarms[name][args.w]
            step_alarms_b = {b: {tid: per_b[tid].get(b, []) for tid in per_b}}
            m = evaluate_from_step_alarms(step_alarms_b, gold_windows, unlabelled_windows,
                                          tau=args.tolerance)[0]
            # trajectory-level view using the calibrated alarms
            per_th: List[Dict[str, Any]] = []
            for tid, g in gold_by_traj.items():
                al = budget_first[name][args.w].get(tid, {}).get(b)
                if al is None and tid not in budget_first[name][args.w]:
                    continue
                per_th.append(alarm_outcome(al, g, min_step=args.min_step_margin))
            tm = alarm_metrics(per_th) if per_th else {}
            rows.append({**m, "budget": b,
                         "threshold": budget_thr_used[name][args.w].get(b, float("nan")),
                         "traj_detection_rate": tm.get("detection_rate", float("nan")),
                         "traj_false_stop_rate": tm.get("false_stop_rate", float("nan")),
                         "traj_mean_saved": tm.get("mean_saved_steps", float("nan")),
                         "traj_median_latency": tm.get("median_latency", float("nan"))})
            traj_rows[str(b)] = per_th
        budget_curves[name] = rows
        budget_traj[name] = traj_rows
    print(f"window-alarm evaluation over {len(gold_windows)} trajectories, "
          f"{sum(1 for v in gold_windows.values() for w in v if w['binary'] == 1)} stagnant and "
          f"{sum(1 for v in gold_windows.values() for w in v if w['binary'] == 0)} productive windows")

    # ---------- alarm-level metrics ----------
    alarm_tables: Dict[str, Any] = {}
    frontier: Dict[str, Any] = {}
    outcome_counts: Dict[str, Any] = {}
    for name in all_monitors:
        alarm_tables[name] = {}
        frontier[name] = {}
        outcome_counts[name] = {}
        for w in windows:
            per_th: Dict[float, List[Dict[str, Any]]] = defaultdict(list)
            for tid, g in gold_by_traj.items():
                alarms = first_alarm[name][w].get(tid)
                if alarms is None:
                    continue
                for th, al in alarms.items():
                    per_th[th].append(alarm_outcome(al, g, min_step=args.min_step_margin))
            if not per_th:
                continue
            curve = savings_curve(per_th)
            alarm_tables[name][w] = curve
            frontier[name][w] = budget_frontier(curve, BUDGETS)
            outcome_counts[name][w] = dict(Counter(r["outcome"] for rs in per_th.values() for r in rs))

    # cross-validation of the frontier point estimates: resample trajectories with replacement
    rng = np.random.default_rng(args.seed)
    frontier_ci: Dict[str, Any] = {}
    for name in all_monitors:
        frontier_ci[name] = {}
        for w in windows:
            per_th: Dict[float, List[Dict[str, Any]]] = defaultdict(list)
            for tid, g in gold_by_traj.items():
                alarms = first_alarm[name][w].get(tid)
                if alarms is None:
                    continue
                for th, al in alarms.items():
                    per_th[th].append(alarm_outcome(al, g, min_step=args.min_step_margin))
            out = {}
            for b in BUDGETS:
                pt = summarise_curve_at(savings_curve(per_th), b) if per_th else {}
                if not pt:
                    continue
                thr = pt.get("threshold", float("nan"))
                if thr != thr:
                    continue
                rows = per_th.get(round(thr, 3), [])
                if not rows:
                    continue
                saved = np.array([r["saved_alarm"] for r in rows], dtype=float)
                det = np.array([r["detected"] for r in rows], dtype=float)
                n = len(rows)
                idx = rng.integers(0, n, size=(2000, n))
                boots = saved[idx].mean(axis=1)
                bootd = det[idx].mean(axis=1)
                out[str(b)] = {
                    "threshold": thr,
                    "saved_mean": float(saved.mean()),
                    "saved_lo": float(np.percentile(boots, 2.5)),
                    "saved_hi": float(np.percentile(boots, 97.5)),
                    "det_mean": float(det.mean()),
                    "det_lo": float(np.percentile(bootd, 2.5)),
                    "det_hi": float(np.percentile(bootd, 97.5)),
                    "n_traj": n,
                }
            frontier_ci[name][w] = out

    # ---------- free-running alarms on the whole sample (no gold needed) ----------
    descriptive: Dict[str, Any] = {}
    for name in all_monitors:
        for w in windows:
            fired, steps_saved, rewards_alarmed = [], [], []
            for tid in first_alarm[name][w]:
                a = first_alarm[name][w][tid].get(0.7)
                if a is None:
                    continue
                n = view_by_id[tid].n_steps
                fired.append(a)
                steps_saved.append(n - a)
                rewards_alarmed.append(view_by_id[tid].reward or 0)
            descriptive[f"{name}|w{w}"] = {
                "n_traj": len(first_alarm[name][w]),
                "alarm_rate": len(fired) / max(1, len(first_alarm[name][w])),
                "median_alarm_step": float(np.median(fired)) if fired else None,
                "median_steps_saved": float(np.median(steps_saved)) if fired else None,
                "total_steps_saved": float(np.sum(steps_saved)) if fired else 0.0,
                "pass_rate_among_alarmed": float(np.mean(rewards_alarmed)) if fired else None,
                "pass_rate_all": float(np.mean([view_by_id[t].reward or 0 for t in first_alarm[name][w]])),
            }

    # ---------- association between monitor scores and final outcome ----------
    outcome_assoc: Dict[str, Any] = {}
    for name in all_monitors:
        for w in windows:
            per_traj: Dict[str, List[float]] = defaultdict(list)
            rew: Dict[str, int] = {}
            for r in score_rows:
                if r["monitor"] != name or r["w"] != w or r["score"] is None:
                    continue
                per_traj[r["traj_id"]].append(r["score"])
                rew[r["traj_id"]] = r["reward"] or 0
            xs = np.array([np.mean(v) for v in per_traj.values()])
            ys = np.array([rew[k] for k in per_traj])
            if len(set(ys.tolist())) > 1 and len(xs) > 10:
                outcome_assoc[f"{name}|w{w}"] = {
                    "auc_mean_score_vs_success": float(window_metrics(ys, -xs)["roc_auc"]),
                    "n": int(len(xs)),
                    "pass_rate": float(ys.mean()),
                }

    # ---------- write ----------
    def dump(name: str, obj: Any) -> None:
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)

    dump("window_metrics.json", wl)
    dump("window_alarm_curves.json", win_alarm_curves)
    dump("window_alarm_frontier.json", win_alarm_frontier)
    dump("budget_calibrated.json", budget_curves)
    dump("budget_thresholds.json", {k: {kk: {str(b): v for b, v in vv.items()} for kk, vv in kv.items()}
                                    for k, kv in budget_thr_used.items()})
    dump("alarm_curves.json", alarm_tables)
    dump("alarm_frontier.json", frontier)
    dump("alarm_frontier_ci.json", frontier_ci)
    dump("alarm_outcomes.json", outcome_counts)
    dump("descriptive.json", descriptive)
    dump("outcome_association.json", outcome_assoc)
    dump("logistic_report.json", {k: v for k, v in lr_coef_summary.items()})
    dump("logistic_models.json", {
        name: {"features": rows[0] and [c for c in rows[0] if c not in ("fold", "n", "pos", "intercept")],
               "coef_values": [rows[0][c] for c in rows[0] if c not in ("fold", "n", "pos", "intercept")],
               "intercept": rows[0]["intercept"],
               "mu": [0.0] * len([c for c in rows[0] if c not in ("fold", "n", "pos", "intercept")]),
               "sd": [1.0] * len([c for c in rows[0] if c not in ("fold", "n", "pos", "intercept")])}
        for name, rows in lr_coef_summary.items() if rows})
    dump("fold_report.json", fold_report)
    dump("gold_summary.json", {"agreement": gold["agreement"], "regions": regions})
    dump("run_config.json", {
        "args": vars(args), "seed": args.seed, "windows": windows, "folds": len(folds),
        "tasks_per_fold": [len(f) for f in folds],
        "annotated_windows_per_fold": [sum(task_counts[t] for t in f) for f in folds],
        "n_traj": len(views), "n_window_rows": len(window_rows),
        "n_annotated_windows": len(test_cards), "n_alarm_eval_traj": len(gold_by_traj),
        "n_alarm_eval_traj_with_region": sum(1 for g in gold_by_traj.values() if g.stagnant),
        "thresholds": thresholds, "min_step_margin": args.min_step_margin,
        "monitors": all_monitors, "has_semantic": bool(has_sem),
        "transfer": transfer_meta, "corpus": args.corpus,
        "seconds": time.time() - t0, "built_at": time.strftime("%Y-%m-%d %H:%M:%S")})

    # ---------- console summary ----------
    print("\n=== window level (ROC-AUC / PR-AUC / best F1 / F1@best) ===")
    for name in sorted(wl):
        for w, m in sorted(wl[name].items()):
            print(f"{name:26} w={w:<3} n={int(m['n']):5d} pos={m['prev']:.3f} roc={m['roc_auc']:.3f} "
                  f"pr={m['pr_auc']:.3f} f1={m['f1_best']:.3f} thr={m['thr_best']:.2f}")
    print("\n=== alarm frontier (annotated trajectories) ===")
    for name in sorted(frontier):
        for w, fr in sorted(frontier[name].items()):
            parts = []
            for f in fr:
                if not f.get("available"):
                    parts.append(f"b={f['budget']:.2f}[--]")
                else:
                    parts.append(f"b={f['budget']:.2f}[fs={f['false_stop_rate']:.2f} "
                                 f"det={f['detection_rate']:.2f} saved={f['mean_saved_steps']:.1f}]")
            print(f"{name:26} w={w:<3} " + " ".join(parts))
    print(f"\nwrote {args.out} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
