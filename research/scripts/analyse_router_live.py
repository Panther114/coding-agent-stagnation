"""Does the router work outside the corpus it was trained on?  Apply it, unchanged, to live runs.

The offline transfer result (``route_modes_transfer.json``) shows the router generalises across
three disjoint shard sets.  Those sets all come from the *same* scaffold: SWE-agent on
SWE-bench-style instances, with the same prompt, the same tool set and the same observation
footer.  A fair objection is that this measures shard-level generalisation, not distribution-level
generalisation.

This script closes that gap with data that already exists: the in-house live experiment
(``results/live/episodes*.jsonl``) -- a different scaffold, a different model
(``deepseek-v4.1-flash``), and eight real PyPI packages instead of SWE-bench instances.  The
router is the frozen model fitted on shards 0-3 (``demo/_cache/router.pkl``); nothing is refitted.

The bridge, and why it is not free
----------------------------------
Live episodes record *turns* (tool name, model text, observation), not the parsed step rows the
corpus pipeline produces, so a step table has to be reconstructed.  Every mapping is listed here
so the reader can judge it:

===========================  =====================================================
column                       live mapping
===========================  =====================================================
``verb``                     ``read``->read, ``write``->edit, ``test``->run, ``done``->finish
``is_edit`` / ``is_read``    tool-name test
``is_test`` / ``is_run``     tool name is ``test`` (running the suite is the only exec tool)
``is_search``                always 0 -- the live harness exposes no search tool
``is_finish``                tool name is ``done``
``sig``                      tool name, plus the written path for ``write`` turns
``added_lines_n``            lines in that turn's written content (0 when the turn is not a write)
``st_*``                     ``agentstall.corpus.parse_obs_state`` -- the *same* parser the
                             corpus build uses, so status semantics are identical
``obs_chars`` / ``text_chars``  lengths of the recorded observation / model text
``targets_str``              empty: the live transcript does not record command text, so the
                             TF-normalised redundancy baseline cannot be evaluated here
===========================  =====================================================

Two consequences are reported rather than hidden: (1) the live runs are capped at 14 turns, so
prefixes are short; (2) ``ever_touched_gold`` is 1.0 in every live episode, so the *mode* task
(LOST vs WRONG-FIX) has no negatives in this data set and **cannot** be evaluated here -- only
the failure head can.

Writes ``results/live/live_router_deployment.json``.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall.corpus import parse_obs_state  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "route_modes", ROOT / "scripts" / "analyse_route_modes.py")
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)

LIVE = ROOT / "results" / "live"
OUT = LIVE / "live_router_deployment.json"
MODEL = ROOT.parent / "demo" / "_cache" / "router.pkl"
FRACTIONS = (0.20, 0.40, 0.60)
VERB = {"read": "read", "write": "edit", "test": "run", "done": "finish"}

#: baseline columns present in the live table.  ``position`` is the prefix length itself, the
#: strongest baseline in the offline study (and a leak diagnostic, not a deployable feature);
#: ``agentstop_shape`` is the published output-length/overlap family.
BASELINES = {"position": "_prefix_len", "agentstop_shape": "_agentstop_outlen",
             "agentstop_overlap": "_agentstop_overlap"}


def episodes() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for name in ("episodes48.jsonl", "episodes_masked.jsonl"):
        p = LIVE / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["_src"] = name
                out.append(r)
    return out


def build_steps(recs: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for r in recs:
        tr = r.get("transcript") or []
        if not tr:
            continue
        rid = f"live::{r['task_id']}::{r['arm']}::{r['seed']}"
        path_by_turn = {w["turn"]: w.get("path") or "" for w in (r.get("writes") or [])}
        lines_by_turn = {w["turn"]: (w.get("content") or "").count("\n") + 1
                         for w in (r.get("writes") or [])}
        for t in tr:
            cmd = (t.get("cmd") or "").strip().lower()
            obs = t.get("obs") or ""
            st = parse_obs_state(obs)
            path = path_by_turn.get(t.get("turn"), "")
            n_written = lines_by_turn.get(t.get("turn"), 0) if cmd == "write" else 0
            rows.append({
                "run_id": rid, "task": r["task_id"], "model": "deepseek-v4.1-flash",
                "reward": int(bool(r.get("success"))), "step": int(t["turn"]),
                "n_steps": len(tr), "verb": VERB.get(cmd, "run"),
                "cmd_family": cmd or "none",
                "is_edit": int(cmd == "write"), "is_read": int(cmd == "read"),
                "is_search": 0, "is_run": int(cmd == "test"),
                "is_test": int(cmd == "test"), "is_finish": int(cmd == "done"),
                "obs_chars": len(obs), "text_chars": len(t.get("reply") or ""),
                "sig": f"{cmd}|{path}" if cmd == "write" else (cmd or "none"),
                "targets_str": "", "file_shown": path, "added_lines_n": n_written,
                "st_passed": st.n_passed if st.n_passed is not None else -1,
                "st_failed": st.n_failed if st.n_failed is not None else -1,
                "st_error": st.n_error if st.n_error is not None else -1,
                "st_tb": int(st.traceback), "st_syntax": int(st.syntax_error),
                "st_notfound": int(st.not_found), "st_sig": st.signature()[:120],
                # run-level labels straight off the episode record
                "arm": r["arm"], "fail_before": bool(r.get("fail_before")),
                "success": bool(r.get("success")), "reached_gold": bool(r.get("reached_gold")),
            })
    return pd.DataFrame(rows)[list(arm.STEP_COLS) + ["arm", "fail_before", "success",
                                                     "reached_gold"]]


def labels_from_steps(steps: pd.DataFrame) -> pd.DataFrame:
    g = steps.groupby("run_id", sort=False).agg(
        task=("task", "first"), arm=("arm", "first"), fail_before=("fail_before", "first"),
        success=("success", "first"), reached_gold=("reached_gold", "first"),
        reward=("reward", "first"), n_steps=("n_steps", "first")).reset_index()
    g["y_fail"] = (g["reward"] == 0).astype(int)
    # mode target: only defined for failed runs, and only meaningful if some failed run is LOST
    g["y_wrong_fix"] = np.where(g["y_fail"] == 1, g["reached_gold"].astype(int), np.nan)
    return g


def cluster_auc_ci(y: np.ndarray, s: np.ndarray, task: np.ndarray, n: int = 2000,
                   seed: int = 0) -> Optional[List[float]]:
    """AUC CI by resampling *tasks*, not runs: episodes of one task share a defect and a package."""
    tasks = np.unique(task)
    if len(tasks) < 3 or len(np.unique(y)) < 2:
        return None
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        pick = rng.choice(tasks, size=len(tasks), replace=True)
        idx = np.concatenate([np.flatnonzero(task == t) for t in pick])
        yy, ss = y[idx], s[idx]
        if len(np.unique(yy)) < 2:
            continue
        out.append(arm._auc(yy, ss))
    if not out:
        return None
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def refit_subset(tables: Dict[float, pd.DataFrame], valid: pd.DataFrame) -> Dict[str, Any]:
    """Re-fit the failure head on the training corpus using only bridgeable features.

    The frozen model is trained on the full rate family, including features the live bridge
    cannot reproduce (``verify_frac``, ``search_frac`` are constant zero here) and features whose
    scale differs by construction (observations are truncated in the live harness).  A low live
    AUC could therefore be a bridge artefact.  This block separates the two: it re-fits on
    shards 0-3 with a strict feature set, reports the *in-corpus* AUC for the that same feature
    set (so a weaker model is visible), and only then scores live.
    """
    from sklearn.linear_model import LogisticRegression

    cache = ROOT / "_cache" / "route_modes" / "prefix_features.parquet"
    lab = ROOT / "_cache" / "route_modes" / "labels.parquet"
    if not (cache.exists() and lab.exists()):
        return {"skipped": f"no cached training table at {cache}"}

    tr = pd.read_parquet(cache)
    fr = sorted(tr["_fraction"].unique())
    tr = tr[np.isclose(tr["_fraction"], fractions_close(fr))].copy()
    y = pd.read_parquet(lab)[["run_id", "y_fail", "n_steps"]]
    tr = tr.merge(y, on="run_id", how="inner")
    live_cols = set(tables[FRACTIONS[0]].columns)
    base = [c for c in arm.RATE_FEATURES
            if c in tr.columns and c in live_cols and c not in UNBRIDGEABLE]
    sets = {
        "bridgeable": base,
        "bridgeable_no_sig": [c for c in base if c not in SIG_FEATURES],
        "bridgeable_no_sig_no_scale": [c for c in base
                                        if c not in SIG_FEATURES + SCALE_SENSITIVE],
    }
    out: Dict[str, Any] = {
        "train_table": str(cache.relative_to(ROOT)).replace("\\", "/"),
        "n_train_rows": int(len(tr)), "dropped_features": UNBRIDGEABLE,
        "sig_features": SIG_FEATURES, "scale_sensitive": SCALE_SENSITIVE, "variants": {},
    }
    for name, cols in sets.items():
        if not cols:
            continue
        X = arm._clean(tr[cols].to_numpy())
        yy = tr["y_fail"].to_numpy(dtype=float)
        mu = X.mean(axis=0)
        sd = np.where(X.std(axis=0) < 1e-9, 1.0, X.std(axis=0))
        m = LogisticRegression(max_iter=3000, C=1.0, solver="lbfgs", random_state=0)
        m.fit((X - mu) / sd, yy)
        blob = {"models": {"y_fail": {"coef": m.coef_.ravel(), "intercept": float(m.intercept_[0]),
                                      "mu": mu, "sd": sd}}}
        in_corpus = float(arm._auc(yy, predict(blob, X, "y_fail")))
        row: Dict[str, Any] = {"n_features": len(cols), "features": cols,
                               "auc_in_corpus_shards0_3": in_corpus, "live": {}}
        for f in FRACTIONS:
            t = tables[f].merge(valid[["run_id", "y_fail"]], on="run_id", how="inner")
            Xl = arm._clean(t[cols].to_numpy())
            yl = t["y_fail"].to_numpy(dtype=float)
            row["live"][str(f)] = {"n": int(len(t)), "auc": float(arm._auc(yl, predict(
                blob, Xl, "y_fail")))}
        out["variants"][name] = row
        print(f"  [refit {name:28s}] {len(cols):2d} features  in-corpus AUC="
              f"{in_corpus:.3f}  live=" +
              "  ".join(f"{f:.2f}:{row['live'][str(f)]['auc']:.3f}" for f in FRACTIONS))
    return out


def fractions_close(unique_fractions) -> float:
    """The cached table is keyed by float fractions; pick the one nearest the deployed 0.20."""
    return float(min(unique_fractions, key=lambda x: abs(float(x) - FRACTIONS[0])))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--valid-only", action="store_true", default=True)
    args = ap.parse_args()

    recs = episodes()
    steps = build_steps(recs)
    labs = labels_from_steps(steps)
    print(f"episodes with a transcript: {len(labs)}  (from {len(recs)} records)")

    valid = labs[labs["fail_before"]] if args.valid_only else labs
    dropped = len(labs) - len(valid)
    steps = steps[steps["run_id"].isin(set(valid["run_id"]))].copy()
    print(f"valid episodes: {len(valid)}  (dropped {dropped} where the task was not broken)")

    if not MODEL.exists():
        raise SystemExit(f"no frozen model at {MODEL}; run  python demo/route.py --fit  first")
    blob = arm_pickle(MODEL)
    cols = list(blob["cols"])
    print(f"frozen model: {len(cols)} rate features, fitted on shards 0-3, fraction "
          f"{blob['fraction']:.0%} -- nothing is refitted here")

    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        tables, _meta = arm.prefix_features(steps, FRACTIONS)

    res: Dict[str, Any] = {
        "question": "does the frozen router (trained on public SWE-agent runs) predict failure "
                    "on in-house live episodes: different scaffold, different model, real packages?",
        "model_artifact": str(MODEL.relative_to(ROOT.parent)).replace("\\", "/"),
        "n_episodes_raw": int(len(labs)), "n_dropped_fail_before_false": int(dropped),
        "n_valid": int(len(valid)),
        "arms": {a: int((valid["arm"] == a).sum()) for a in sorted(valid["arm"].unique())},
        "mapping_caveats": [
            "live runs are capped at 14 turns, so prefixes are short",
            "the mode target has no negatives here (reached_gold is 1.0), so LOST/WRONG-FIX "
            "cannot be evaluated on this data set",
            "targets_str is empty, so the TF-normalised redundancy baseline is not evaluable",
            "sig for write turns is tool name + path; the corpus uses a command digest",
        ],
        "fractions": {},
    }

    for f in FRACTIONS:
        t = tables[f].merge(valid[["run_id", "y_fail", "y_wrong_fix", "arm", "task"]].rename(
            columns={"task": "task_id"}), on="run_id", how="inner")
        if t["run_id"].duplicated().any():
            raise SystemExit("run_id collision after merge: live arms share a task id")
        y = t["y_fail"].to_numpy(dtype=float)
        X = arm._clean(t[cols].to_numpy())
        p_fail = predict(blob, X, "y_fail")
        block: Dict[str, Any] = {
            "n": int(len(t)), "n_failed": int(y.sum()),
            "auc_router": float(arm._auc(y, p_fail)),
            "auc_router_ci95_task_clustered": cluster_auc_ci(
                y, p_fail, t["task_id"].to_numpy()),
            "baselines": {},
        }
        for name, col in BASELINES.items():
            if col in t.columns:
                block["baselines"][name] = float(arm._auc(y, t[col].to_numpy(dtype=float)))
        block["gain_over_best_baseline"] = (
            block["auc_router"] - max(block["baselines"].values())
            if block["baselines"] else None)
        # drift: is the live feature vector even inside the training distribution?
        mu, sd = blob["models"]["y_fail"]["mu"], blob["models"]["y_fail"]["sd"]
        Z = (X - mu) / np.where(sd < 1e-9, 1.0, sd)
        block["feature_drift"] = {
            "n_features": len(cols),
            "n_features_abs_z_gt_3": int((np.abs(Z).mean(axis=0) > 3).sum()),
            "worst": sorted(
                [{"feature": c, "live_minus_train_sd": float(z)}
                 for c, z in zip(cols, np.abs(Z).mean(axis=0))],
                key=lambda d: -d["live_minus_train_sd"])[:8],
        }
        res["fractions"][str(f)] = block
        print(f"  f={f:.2f}  n={block['n']:3d}  router AUC={block['auc_router']:.3f}  "
              f"baselines={ {k: round(v,3) for k,v in block['baselines'].items()} }  "
              f"gain={block['gain_over_best_baseline']:+.3f}")

    # per-arm view: does it hold in the arm where the answer is hidden?
    res["by_arm"] = {}
    for a in sorted(valid["arm"].unique()):
        row = {}
        for f in FRACTIONS:
            t = tables[f].merge(valid[valid["arm"] == a][["run_id", "y_fail"]], on="run_id")
            if len(t) < 8 or t["y_fail"].nunique() < 2:
                row[str(f)] = None
                continue
            row[str(f)] = float(arm._auc(t["y_fail"].to_numpy(dtype=float),
                                         predict(blob, arm._clean(t[cols].to_numpy()),
                                                 "y_fail")))
        res["by_arm"][a] = row
    print("\nby arm:", json.dumps({k: {kk: (round(vv, 3) if vv is not None else None)
                                        for kk, vv in v.items()}
                                   for k, v in res["by_arm"].items()}))

    res["verdict"] = verdict(res)
    print("\nrefitting on the training corpus with bridgeable features only:")
    res["refit_bridgeable"] = refit_subset(tables, valid)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + res["verdict"]["headline"])
    print(f"wrote {OUT}")


def verdict(res: Dict[str, Any]) -> Dict[str, Any]:
    b = res["fractions"][str(FRACTIONS[0])]
    ok = b["auc_router"] > 0.5 and (b["gain_over_best_baseline"] or 0) > 0
    return {
        "headline": (
            f"frozen router on live runs: AUC {b['auc_router']:.3f} at {FRACTIONS[0]:.0%} "
            f"(n={b['n']}), best baseline {max(b['baselines'].values()):.3f}, "
            f"gain {b['gain_over_best_baseline']:+.3f}"
            if b["baselines"] else f"frozen router on live runs: AUC {b['auc_router']:.3f}"),
        "transfers_better_than_baselines": bool(ok),
        "mode_head_evaluable": False,
        "mode_head_reason": "no LOST episodes exist in the live data (reached_gold = 1.0 everywhere)",
    }


def arm_pickle(path: Path) -> Dict[str, Any]:
    import pickle
    return pickle.loads(path.read_bytes())


def predict(blob: Dict[str, Any], X: np.ndarray, ycol: str, cols: Optional[List[str]] = None
            ) -> np.ndarray:
    """Sigmoid of the frozen linear head.  The exponent is clipped: on live features that sit
    far outside the training range the unclipped exponential overflows, which numpy reports as a
    RuntimeWarning and which silently saturates the score."""
    m = blob["models"][ycol]
    z = ((X - m["mu"]) / m["sd"]) @ m["coef"] + m["intercept"]
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


#: features whose *definition* cannot be reproduced from a live transcript, so a model using
#: them would be scored against a column that is constant (0) here and not in the corpus.
UNBRIDGEABLE = ["verify_frac", "search_frac"]

#: features built on ``sig``, which the live bridge approximates as ``tool|path`` rather than
#: the corpus's command digest.  Reported as a separate, sig-free variant so a negative result
#: can be attributed to the bridge rather than to distribution shift.
SIG_FEATURES = ["unique_sig_frac", "sig_entropy", "repeat_sig_frac", "max_consec_repeat_norm",
                "has_repeat_3plus"]

#: features whose *scale* differs by construction: live observations are truncated to 1_500
#: characters and model text to 600, the corpus keeps them whole.
SCALE_SENSITIVE = ["obs_mean", "obs_last_over_mean", "text_chars_mean", "text_to_obs",
                   "obs_mean_over_text", "obs_slope_norm", "obs_half_ratio"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
