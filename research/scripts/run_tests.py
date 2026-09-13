"""Smoke tests for the monitor stack.

These check the invariants the paper depends on, rather than snapshotting outputs, so they
stay useful when the implementation changes.  Run with:

    python scripts/run_tests.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from typing import Callable, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

from build_dataset import build_views  # noqa: E402
from evidence import extract_entities, extract_state, relevance, task_terms  # noqa: E402
from features import ALL_FEATURES, FEATURE_CHANNEL, first_seen_index  # noqa: E402
from loaders import Action, Step, Trajectory, load_tb2, tb2_task_statements  # noqa: E402
from monitors import (WindowFeatureCache, alarmed_steps, budget_thresholds,  # noqa: E402
                      sustained_alarm)
from normalize import normalize_action  # noqa: E402

TESTS: List[Tuple[str, Callable[[], None]]] = []


def test(fn: Callable[[], None]) -> Callable[[], None]:
    TESTS.append((fn.__name__, fn))
    return fn


# --------------------------------------------------------------------------------------


@test
def test_loader_yields_well_formed_trajectories() -> None:
    trajs = load_tb2(limit=5)
    assert trajs, "loader returned nothing"
    for t in trajs:
        assert t.steps, f"{t.traj_id} has no steps"
        for s in t.steps:
            assert isinstance(s.observation, str)
            assert s.index == t.steps.index(s) or True  # indices are renumbered contiguously
        assert [s.index for s in t.steps] == list(range(len(t.steps)))


@test
def test_normalizer_is_total_and_idempotent() -> None:
    cases = [
        ("bash_command", "cd /app && python3 -m pytest tests/test_api.py -x"),
        ("bash_command", "cat > /app/x.R << 'EOF'\nf <- function(z) {}\nEOF"),
        ("Bash", "grep -rn 'def foo' /repo/pkg/mod.py | head -20"),
        ("str_replace_editor", 'str_replace(path="/repo/a.py", old_str="x", new_str="y")'),
        ("Read", '{"file_path": "/app/a.py", "offset": 10}'),
        ("", ""),
    ]
    for name, arg in cases:
        a = normalize_action(name, arg)
        assert a.kind, f"no intent for {name}"
        assert a.signature, f"no signature for {name}"
        b = normalize_action(name, arg)
        assert a.signature == b.signature, "normalization is not deterministic"
    # a compound command must be classified by its most informative part
    a = normalize_action("bash_command", "cd /app && pytest -q")
    assert a.kind == "verify", f"compound command classified as {a.kind}"


@test
def test_compound_verification_wins_over_navigation() -> None:
    a = normalize_action("bash_command", "cd /repo && make -j4 && ./run_tests.sh")
    assert a.kind == "verify", a.kind


@test
def test_state_extraction_reads_test_and_build_signals() -> None:
    s1 = extract_state("=== 2 failed, 8 passed, 1 warning in 1.20s ===")
    assert s1.n_passed == 8 and s1.n_failed == 2, s1.summary()
    s2 = extract_state("Traceback (most recent call last):\nValueError: bad shape\n<returncode>1</returncode>")
    assert s2.exit_code == 1 and s2.error_sig and s2.error_sig.startswith("ValueError"), s2.summary()
    s3 = extract_state("Build succeeded\nDone. 12 files")
    assert s3.build_ok is True
    s4 = extract_state("Segmentation fault (core dumped)")
    assert s4.crashed


@test
def test_entity_extraction_and_relevance() -> None:
    obs = ('[File: /lexicon/lexicon/providers/memset.py (145 lines total)]\n'
           'Traceback (most recent call last):\n'
           '  File "/lexicon/lexicon/providers/memset.py", line 144, in _request\n'
           'requests.exceptions.HTTPError: 403 Client Error')
    ents = {e.key for e in extract_entities(obs, "obs")}
    assert any("memset.py" in e for e in ents), ents
    assert any("HTTPError" in e for e in ents), ents
    terms = task_terms("Fix the memset provider so DNS records are created with the API token")
    assert relevance(["memset.py"], terms, {}) > 0.4, "task term overlap not detected"
    assert relevance(["zeta_market_ingest.py"], terms, {}) == 0.0


@test
def test_features_are_finite_and_channel_labelled() -> None:
    trajs = load_tb2(limit=4)
    stmts = tb2_task_statements()
    views = build_views(trajs, stmts)
    for v in views:
        v.idf = {}
    for v in views:
        cfg = {"_terms": task_terms(stmts.get(v.task, "")), "rel_threshold": 0.5}
        cache = WindowFeatureCache(v, 10, cfg)
        assert cache.X.shape[1] == len(ALL_FEATURES)
        for j, name in enumerate(ALL_FEATURES):
            col = cache.X[:, j]
            finite = col[~np.isnan(col)]
            assert np.all(np.isfinite(finite)), f"{name} produced non-finite values"
            assert name in FEATURE_CHANNEL, f"{name} has no channel"


@test
def test_online_restriction_features_do_not_use_future() -> None:
    """Truncating a trajectory must not change the features of the surviving windows."""
    trajs = load_tb2(limit=3)
    stmts = tb2_task_statements()
    views = build_views(trajs, stmts)
    for v in views:
        v.idf = {}
    v = max(views, key=lambda x: x.n_steps)
    if v.n_steps < 12:
        return
    cfg = {"_terms": task_terms(stmts.get(v.task, "")), "rel_threshold": 0.5}
    full = WindowFeatureCache(v, 10, cfg).X
    cut = type(v)(
        traj_id=v.traj_id, task=v.task, agent=v.agent, model=v.model, reward=v.reward,
        steps=v.steps[: v.n_steps // 2], idf={})
    part = WindowFeatureCache(cut, 10, {"_terms": cfg["_terms"], "rel_threshold": 0.5}).X
    n = part.shape[0]
    a = np.nan_to_num(full[:n], nan=-999.0)
    b = np.nan_to_num(part, nan=-999.0)
    # the last window of the truncated run may legitimately differ only for features that look
    # at "first seen anywhere earlier"; compare the prefix strictly before that point
    diff = np.abs(a[: max(0, n - 1)] - b[: max(0, n - 1)])
    assert float(np.max(diff)) < 1e-9, f"features depend on the future (max diff {float(np.max(diff))})"


@test
def test_alarm_rule_requires_persistence() -> None:
    s = np.array([0.0, 0.9, 0.1, 0.9, 0.9, 0.9])
    assert alarmed_steps(s, 0.8, k=2, min_step=0) == [4, 5]
    assert sustained_alarm(s, 0.8, k=2, min_step=0) == 4
    assert alarmed_steps(s, 0.95, k=2, min_step=0) == []
    # the minimum-step margin suppresses early alarms
    assert sustained_alarm(s, 0.8, k=2, min_step=5) is None


@test
def test_budget_thresholds_are_quantiles() -> None:
    rng = np.random.default_rng(0)
    series = [rng.normal(size=500)]
    thr = budget_thresholds(series, budgets=(0.05, 0.20))
    assert thr[0.05] > thr[0.20], "a smaller budget must need a higher threshold"
    frac = float((series[0] >= thr[0.05]).mean())
    assert abs(frac - 0.05) < 0.02, frac


@test
def test_frozen_artifacts_are_consistent() -> None:
    run = os.path.join(ROOT, "results", "final", "tb2_final")
    if not os.path.isdir(run):
        return
    cfg = json.load(open(os.path.join(run, "run_config.json"), encoding="utf-8"))
    wl = json.load(open(os.path.join(run, "window_metrics.json"), encoding="utf-8"))
    assert cfg["monitors"], "no monitors recorded"
    assert cfg["folds"] >= 1
    for mon, per in wl.items():
        for w, m in per.items():
            assert 0.0 <= m["prev"] <= 1.0
            if m["roc_auc"] == m["roc_auc"]:
                assert 0.3 <= m["roc_auc"] <= 1.0, (mon, w, m["roc_auc"])


@test
def test_annotation_gold_is_well_formed() -> None:
    import csv
    path = os.path.join(ROOT, "data", "annotations", "tb2", "adjudicated.csv")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert len(rows) > 400, len(rows)
    pos = sum(1 for r in rows if r["binary"] == "1")
    assert 0.1 < pos / len(rows) < 0.5, pos / len(rows)
    for r in rows:
        assert r["gold"] in {"PRODUCTIVE", "STAGNANT", "DONE_REDUNDANT", "REGRESSION",
                             "BLOCKED_EXTERNAL", "UNCERTAIN"}, r["gold"]
        if r["binary"] == "1":
            assert r["gold"] in {"STAGNANT", "DONE_REDUNDANT"}
        if r["binary"] == "0":
            assert r["gold"] in {"PRODUCTIVE", "REGRESSION"}


def main() -> int:
    failed = 0
    for name, fn in TESTS:
        t0 = time.time()
        try:
            fn()
            print(f"PASS  {name}  ({time.time()-t0:.2f}s)")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
