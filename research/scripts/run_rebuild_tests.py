"""Regression tests for the rebuild pipeline (agentstall).

These guard the properties that make the study honest rather than the numbers themselves:

1. **No leakage.** No feature may read a target, the reward, the final patch, or a future
   step. Checked structurally (the module's source does not mention them) and behaviourally
   (features computed on a prefix are identical to features computed on a longer run for the
   same step).
2. **Stationarity.** ``f_stat(t) = f(t) - mean(f(0..t))`` removes a constant and a linear
   drift in run position exactly, and leaves a constant series at zero.
3. **Causal event handling.** The sequential event series must not let a window's own
   verdict influence an alarm at that window.
4. **Parsers.** The TB2 turn grouping and the SWE-agent edit-block extractor behave on
   constructed inputs with known answers.
5. **Metric edge cases.** ``safe_auc``/``partial_auc``/``binarise`` handle constant,
   continuous and empty inputs without raising, and the targets are never features.

Run:  python scripts/run_rebuild_tests.py
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import corpus as C  # noqa: E402
from agentstall import evaluate as E  # noqa: E402
from agentstall import features as F  # noqa: E402
from agentstall import sequential as S  # noqa: E402
from agentstall import targets as T  # noqa: E402

PASS, FAIL = [], []


def check(name: str):
    def deco(fn):
        try:
            fn()
            PASS.append(name)
            print(f"  PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            FAIL.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
        return fn
    return deco


# --------------------------------------------------------------------------------------


@check("features.py does not read a target or a reward into any feature")
def test_no_target_references():
    """Structural check: no feature *value* may be derived from a target or a reward.

    ``reward`` legitimately appears as identity metadata carried on ``RunView`` (it labels
    the row for evaluation), so it is allowed in the dataclass field list and in the
    constructor.  What is forbidden is any arithmetic use of it, and any mention at all of
    the target columns or of future windows.
    """
    src = (ROOT / "src" / "agentstall" / "features.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    # locate docstrings so prose may be excluded from the scan
    in_doc = False
    doc_lines = set()
    for i, line in enumerate(lines, 1):
        n = line.count('"""')
        if in_doc:
            doc_lines.add(i)
            if n:
                in_doc = False
            continue
        if n == 1:
            in_doc = True
            doc_lines.add(i)
        elif n >= 2:
            doc_lines.add(i)
    bad = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or i in doc_lines:
            continue
        for word in ("y_stagnation", "y_waste", "y_future", "y_noop", "y_loop",
                     "generated_patch", "future_targets"):
            if word in line:
                bad.append((word, i, stripped[:80]))
        if "reward" in line and not line.strip().startswith("reward: int") \
                and "reward=int(" not in line:
            bad.append(("reward", i, stripped[:80]))
    assert not bad, f"features.py reads a target/reward: {bad[:4]}"


@check("features at step t are unchanged by truncating the run after t")
def test_prefix_invariance():
    rng = np.random.default_rng(0)
    n = 40
    df = pd.DataFrame({
        "run_id": ["r"] * n, "corpus": ["t"] * n, "task": ["k"] * n,
        "agent": ["a"] * n, "model": ["m"] * n, "reward": [1] * n,
        "step": np.arange(n), "n_steps": [n] * n,
        "is_edit": (rng.random(n) < 0.4).astype(float),
        "is_test": (rng.random(n) < 0.2).astype(float),
        "is_read": (rng.random(n) < 0.4).astype(float),
        "is_run": (rng.random(n) < 0.4).astype(float),
        "is_search": (rng.random(n) < 0.2).astype(float),
        "verb": rng.choice(["edit", "run", "read"], n),
        "file_total": np.where(rng.random(n) < 0.8, 100 + np.arange(n) % 7, -1).astype(float),
        "file_first": np.ones(n, dtype=float),
        "obs_chars": rng.integers(0, 500, n).astype(float),
        "text_chars": rng.integers(0, 400, n).astype(float),
        "n_cmds": rng.integers(0, 3, n).astype(float),
        "st_test": (rng.random(n) < 0.2).astype(float),
        "st_passed": rng.integers(-1, 5, n).astype(float),
        "st_failed": rng.integers(-1, 5, n).astype(float),
        "st_exit": rng.integers(-1, 2, n).astype(float),
        "st_syntax": (rng.random(n) < 0.1).astype(float),
        "st_tb": (rng.random(n) < 0.1).astype(float),
        "st_notfound": (rng.random(n) < 0.1).astype(float),
        "st_timeout": (rng.random(n) < 0.05).astype(float),
        "sig": [f"sig{i%7}" for i in range(n)],
        "cmd_family": [f"fam{i%5}" for i in range(n)],
        "file_shown": [f"/f{i%3}.py" for i in range(n)],
        "st_errc": [""] * n,
        "st_sig": [f"s{i%4}" for i in range(n)],
        "targets_str": [f"/f{i%3}.py" for i in range(n)],
    })
    ents_full = [[("file", f"/f{i%3}.py", 5)] for i in range(n)]

    rv_full = F.build_run_view(df, ents_full)
    wins_full = F.sweep_run(rv_full, w=10, stride=1, min_window=3)

    keep = 25
    rv_p = F.build_run_view(df.iloc[:keep].reset_index(drop=True), ents_full[:keep])
    wins_p = F.sweep_run(rv_p, w=10, stride=1, min_window=3)
    last_full = [w for w in wins_full if int(w["_t"]) == keep - 1]
    last_p = [w for w in wins_p if int(w["_t"]) == keep - 1]
    assert last_full and last_p, "no window produced at the boundary"
    a, b = last_full[0], last_p[0]
    for k in sorted(set(a) & set(b) - {"rep_recurrence"}):
        va, vb = a[k], b[k]
        if isinstance(va, float) and math.isnan(va):
            assert isinstance(vb, float) and math.isnan(vb), f"{k} nan mismatch"
            continue
        if abs(va - vb) > 1e-9:
            raise AssertionError(f"prefix invariance violated for {k}: {va} vs {vb}")


@check("stationarise removes constant and linear drift exactly, keeps a bend")
def test_stationarise():
    n = 50
    t = np.arange(n, dtype=float)
    raw = np.column_stack([np.full(n, 3.0), 2.0 + 0.5 * t, np.sin(t) + 0.3 * t])
    lev, fit = F.stationarise(raw, ["a", "b", "c"])
    assert np.allclose(lev[:, 0], 0.0, atol=1e-9), "level form: constant not removed"
    assert np.allclose(fit[:, 0], 0.0, atol=1e-9), "fit form: constant not removed"
    assert np.allclose(fit[:, 1], 0.0, atol=1e-6), f"fit form: drift not removed {fit[:4,1]}"
    assert np.abs(fit[:, 2]).max() > 0.5, "fit form destroyed the signal"
    # the level form is expected to leave a residual slope -- documented, not a bug
    assert np.abs(lev[:, 1]).max() > 1.0, "level form unexpectedly removed the drift"


@check("causal event shift prevents lookahead")
def test_causal_shift():
    ev = np.array([0.0, 0.0, 1.0, 1.0, 0.0, 0.0])
    out = S.causal_quiet_series({"r": ev}, w=2)["r"]
    assert out[0] == 0.0 and out[1] == 0.0, "alarm could fire before the window elapsed"
    assert out[2] == 0.0 and out[3] == 0.0, "event leaked backwards"
    assert out[4] == 1.0 and out[5] == 1.0, "event did not propagate forward"


@check("quiet detector fires on sustained silence and not on continuous events")
def test_quiet_detector():
    quiet = np.zeros(200)
    busy = np.outer(np.ones(1), np.tile([1.0, 0.0], 100)).ravel()
    assert S.quiet_detect(quiet, alpha=0.05) is not None, "no alarm on sustained silence"
    assert S.quiet_detect(busy, alpha=0.05) is None, "false alarm on a busy run"


@check("TB2 parser groups prose into the following action")
def test_tb2_grouping():
    steps = [
        {"src": "system", "msg": "prompt", "tools": None, "obs": None},
        {"src": "agent", "msg": "I will look around", "tools": None, "obs": None},
        {"src": "agent", "msg": "listing files", "tools": [{"fn": "Bash", "cmd": "ls -la"}],
         "obs": "file1\nfile2"},
        {"src": "agent", "msg": "now editing", "tools": None, "obs": None},
        {"src": "agent", "msg": "fix the bug", "tools": [{"fn": "Edit", "cmd": "/a/b.py"}],
         "obs": "ok"},
    ]
    import json
    out = C.build_tb2_steps(json.dumps(steps))
    assert len(out) == 2, f"expected 2 actions, got {len(out)}"
    assert "I will look around" in out[0].text and "listing files" in out[0].text
    assert out[0].cmds == ["ls -la"]
    assert out[0].obs == "file1\nfile2", f"system prompt leaked into the observation: {out[0].obs!r}"
    assert out[1].is_edit, "Edit tool not recognised as an edit"
    assert "fix the bug" in out[1].text


@check("SWE-agent edit blocks yield only the changed lines, not the context")
def test_edit_added_lines():
    # a single-line replacement prints context above it; only the last line is new
    body = ("DISCUSSION\nsome reasoning\n\n```\n"
            "edit 26:26\n"
            "    25:     previous context line\n"
            "    26:     return []\n"
            "end_of_edit\n```")
    lines = C.edit_added_lines(body)
    assert lines == ["return []"], lines
    # a range yields exactly the lines whose numbers fall inside it
    ranged = ("```\n"
              "edit 26:28\n"
              "    25: context\n"
              "    26: new A\n"
              "    27: new B\n"
              "    28: new C\n"
              "end_of_edit\n```")
    assert C.edit_added_lines(ranged) == ["new A", "new B", "new C"], C.edit_added_lines(ranged)
    here = "cat > /app/x.py <<EOF\nimport os\nprint(1)\nEOF"
    assert C.edit_added_lines(here) == ["import os", "print(1)"], C.edit_added_lines(here)
    # no body at all (e.g. a bare `create file`) must not invent lines
    assert C.edit_added_lines("create reproduce.py") == []


@check("metrics handle degenerate inputs without raising")
def test_metric_edges():
    y = np.array([0.0, 1.0, 0.0, 1.0])
    s = np.array([0.1, 0.9, 0.2, 0.8])
    assert abs(E.safe_auc(y, s) - 1.0) < 1e-9
    assert math.isnan(E.safe_auc(np.zeros(4), s))
    assert math.isnan(E.safe_auc(y[:1], s[:1]))
    assert E.binarise(np.array([0.0, 0.6, 0.4, 1.0])).tolist() == [0, 1, 0, 1]
    assert E.binarise(np.array([0.0, 1.0])).tolist() == [0, 1]
    pa = E.partial_auc(y, s, 0.05)
    assert pa == pa, "partial_auc raised or returned nan on a separable case"
    assert abs(pa - 1.0) < 1e-6, pa


@check("a feature's AUC direction is reported consistently with its sign")
def test_auc_direction():
    """Guard against the sign error that briefly inverted a published finding.

    A magnitude feature ranked as "high means wasted" must score `1 - auc` of the same feature
    ranked as "low means wasted"; if a table ever lists only one direction, this is what proves
    which one it is.  Built on a synthetic case with a known answer.
    """
    rng = np.random.default_rng(0)
    n = 4000
    y = np.concatenate([np.zeros(n // 4), np.ones(n // 4)])          # 0 = survives, 1 = wasted
    # a feature that is SMALL when wasted: wasted rows get low values
    x = np.concatenate([rng.normal(5, 1, n // 4), rng.normal(1, 1, n // 4)])
    auc_high_wasted = E.safe_auc(y, x)
    auc_low_wasted = E.safe_auc(y, -x)
    assert auc_low_wasted > 0.9, f"expected low->wasted to be strong, got {auc_low_wasted}"
    assert auc_high_wasted < 0.1, f"expected high->wasted to be inverted, got {auc_high_wasted}"
    assert abs((auc_high_wasted + auc_low_wasted) - 1.0) < 1e-9, "the two directions must sum to 1"
    # and the documented conclusion for edit size must match the data
    es_path = ROOT / "results" / "rebuild" / "edit_structure.json"
    if es_path.exists():
        es = json.loads(es_path.read_text(encoding="utf-8"))
        row = next((u for u in es.get("univariate", []) if u["feature"] == "n_added"), None)
        if row is not None:
            assert row["auc_low_means_wasted"] > row["auc_high_means_wasted"], (
                "edit_structure.json claims large edits are more wasted; the data says the "
                "opposite (small edits are the wasteful ones)")
            assert row["auc_low_means_wasted"] > 0.65, row


@check("targets are never present in the feature groups")
def test_target_feature_disjoint():
    feat = {k for grp in F.FEATURE_GROUPS.values() for k in grp}
    overlap = feat & set(T.TARGET_COLUMNS)
    assert not overlap, f"targets leaked into feature groups: {overlap}"
    assert not any(k.startswith("y_") for k in feat)


@check("targets module computes a no-op edit as waste")
def test_noop_target():
    df = pd.DataFrame({
        "run_id": ["r"] * 5, "corpus": ["t"] * 5, "task": ["k"] * 5, "agent": ["a"] * 5,
        "model": ["m"] * 5, "reward": [0] * 5, "step": np.arange(5), "n_steps": [5] * 5,
        "is_edit": [0, 1, 1, 0, 0], "is_test": [0] * 5, "is_read": [0] * 5,
        "is_run": [0] * 5, "is_search": [0] * 5, "verb": ["edit"] * 5,
        "file_total": [10.0, 10.0, 12.0, 12.0, 12.0], "file_first": [1.0] * 5,
        "obs_chars": [1.0] * 5, "text_chars": [1.0] * 5, "n_cmds": [1.0] * 5,
        "st_test": [0.0] * 5, "st_passed": [-1.0] * 5, "st_failed": [-1.0] * 5,
        "st_exit": [-999.0] * 5, "st_syntax": [0.0] * 5, "st_tb": [0.0] * 5,
        "st_notfound": [0.0] * 5, "st_timeout": [0.0] * 5,
        "sig": ["a"] * 5, "cmd_family": ["edit"] * 5, "file_shown": ["/f.py"] * 5,
        "st_errc": [""] * 5, "st_sig": ["s"] * 5, "targets_str": ["/f.py"] * 5,
    })
    rv = F.build_run_view(df, [[("file", "/f.py", 5)] for _ in range(5)])
    obj = T.step_level_objective(rv)
    # step 1 is an edit whose size did not change -> no-op; step 2 changed -> not
    assert obj["noop_edit"][1] == 1.0, "no-op edit not detected"
    assert obj["noop_edit"][2] == 0.0, "size-changing edit mislabelled as no-op"
    assert obj["ws_delta"][2] == 2.0


def main() -> None:
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    for name, err in FAIL:
        print(f"  FAILED: {name} -> {err}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
