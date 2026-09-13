"""Cross-scaffold failure prediction: does the router's signal survive a different scaffold?

The offline transfer result (``route_modes_transfer.json``) holds the scaffold fixed (SWE-agent)
and varies the shards.  A reviewer's first objection is that this is shard-level, not
distribution-level, generalisation.  The cross-scaffold corpora already on disk answer it:

======================  =========  =================  =========================================
corpus                  runs       pass / fail        scaffold
======================  =========  =================  =========================================
SWE-agent (shards 0-3)  20,341     --                 SWE-agent, the training scaffold
OpenHands / SWE-Gym     67,074     32,161 / 34,913    OpenHands, agentless-style tool calls
thoughtworks            15,000     4,624 / 10,376     four frameworks in one corpus
SWE-Gym sampled         6,055      491 / 5,564        OpenHands trajectories, mostly failing
PI agent                7,777      7,777 / 0          all-success corpus: label is degenerate
mini-swe-agent-plus     65,994     --                 no ``resolved`` field at all
======================  =========  =================  =========================================

Only the first three can be scored, and they are scored here with the *same code path* that
builds the training table, so nothing about the comparison is corpus-specific.

The bridge, stated exactly
--------------------------
The five files do not share a schema, so a common per-step frame is derived.  Both sides go
through this builder; no feature is computed one way for training and another way for a test
corpus:

===========================  ===============================  ==============================
field                        SWE-agent (training)             cross-scaffold corpora
===========================  ===============================  ==============================
``verb``                     as parsed by ``corpus.py``       same classifier, fed (tool, cmd)
``is_edit``                  as parsed by ``corpus.py``       the extractor's own ``is_edit``
``is_test``                  test counts visible in the obs   ``n_pass``/``n_fail``/``n_err``
``sig``                      hash of the command body         hash of tool + first 120 chars
``cmd_family``               first token of the command       same
``observed file``            the editor's shown file          the extractor's ``file``
``added_lines_n``            lines added by an edit           ``n_added``
``obs_chars``                observation length               observation length
``st_passed/failed/error``   ``parse_obs_state``              the extractor's test summary
``st_tb/syntax/notfound``    ``parse_obs_state``              not extracted -> excluded
===========================  ===============================  ==============================

Excluded for lack of a shared definition: ``text_chars`` and its three derived features (no
model text outside SWE-agent), and the error-flag features (no traceback/syntax flags outside).
That leaves 29 of the 34 rate features, which is what is fitted and scored below.

Writes ``results/rebuild/router_xscaffold.json`` and caches feature tables in
``_cache/xscaffold_features/``.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentstall import corpus as C  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "route_modes", ROOT / "scripts" / "analyse_route_modes.py")
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)

OUT = ROOT / "results" / "rebuild" / "router_xscaffold.json"
CACHE = ROOT / "_cache" / "xscaffold_features"
FRACTIONS = (0.20, 0.40, 0.60)
CHUNK_RUNS = 6000      # runs per feature-building chunk: bounds peak memory on the 4.3 M-step corpus

XSCAFFOLD = ROOT / "data" / "processed" / "xscaffold"
TRAIN_STEPS = ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet"
TRAIN_GOLD = ROOT / "results" / "rebuild" / "gold_patches.parquet"

CORPORA = {
    "openhands": ("nebius_openhands", "OpenHands (SWE-Gym sampled)"),
    "thoughtworks": ("thoughtworks", "four frameworks (thoughtworks)"),
    "swegym": ("swegym", "OpenHands / SWE-Gym"),
}

#: features computable identically on both sides of the bridge
BRIDGE_FEATURES = [
    "no_edit_yet", "first_edit_frac", "edit_rate", "noop_edit_frac", "distinct_files_per_edit",
    "repeat_file_edit_frac", "any_file_edited_twice", "testish_per_step", "verify_frac",
    "run_frac", "read_frac", "search_frac", "finish_seen", "unique_sig_frac",
    "unique_cmdfam_frac", "sig_entropy", "cmdfam_entropy", "repeat_sig_frac",
    "max_consec_repeat_norm", "has_repeat_3plus", "obs_mean", "obs_last_over_mean",
    "obs_slope_norm", "obs_half_ratio", "err_rate", "pass_seen_per_step", "fail_seen_per_step",
    "err_seen_per_step", "fail_minus_pass_norm", "any_test_fail_seen", "any_test_pass_seen",
]

STEP_COLS = ["run_id", "task", "model", "reward", "step", "n_steps", "verb", "cmd_family",
             "is_edit", "is_read", "is_search", "is_run", "is_test", "is_finish", "obs_chars",
             "text_chars", "sig", "targets_str", "file_shown", "added_lines_n", "st_passed",
             "st_failed", "st_error", "st_tb", "st_syntax", "st_notfound", "st_sig"]


def verb_and_flags(tool: str, cmd: str) -> Tuple[str, str]:
    """The corpus's own verb classifier, applied to a (tool, command) pair."""
    first = (cmd or "").splitlines()[0] if (cmd or "").strip() else ""
    head = first.strip().split()[0].lower() if first.strip() else ""
    verb = C.VERB_OTHER
    if first:
        verb, _targets = C._classify_shell(first)
        if head in C._TOOL_VERB:
            verb = C._TOOL_VERB[head]
        if head in ("create", "str_replace", "insert", "undo_edit", "edit", "apply_patch"):
            verb = C.VERB_EDIT
        elif head in ("open", "goto", "scroll_down", "scroll_up"):
            verb = C.VERB_READ
    if verb == C.VERB_OTHER and tool:
        verb = C._TOOL_VERB.get((tool or "").lower(), C.VERB_OTHER)
    fam = head or (tool or "").lower()[:20] or "none"
    return verb, fam


def sig_of(tool: str, cmd: str) -> str:
    return C.h64(((tool or "") + "\u0000" + (cmd or "")[:120])[:800])


def _status(v, default: int = -1) -> np.ndarray:
    return np.where(pd.isna(v), default, v).astype(np.int64)


def _chunked(df: pd.DataFrame, n: int) -> Iterator[pd.DataFrame]:
    for i in range(0, len(df), n):
        yield df.iloc[i:i + n]


# --------------------------------------------------------------------------------------
# builders: one frame of STEP_COLS rows either way
# --------------------------------------------------------------------------------------


def build_training_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    d = chunk
    is_test = ((d["st_passed"] >= 0) | (d["st_failed"] >= 0) | (d["st_error"] >= 0))
    return pd.DataFrame({
        "run_id": d["run_id"], "task": d["task"], "model": d["model"],
        "reward": d["reward"], "step": d["step"], "n_steps": d["n_steps"],
        "verb": d["verb"], "cmd_family": d["cmd_family"].astype(str).str.slice(0, 20),
        "is_edit": d["is_edit"].astype(np.int8), "is_read": d["is_read"].astype(np.int8),
        "is_search": d["is_search"].astype(np.int8), "is_run": d["is_run"].astype(np.int8),
        "is_test": is_test.astype(np.int8), "is_finish": d["is_finish"].astype(np.int8),
        "obs_chars": d["obs_chars"].astype(np.float32),
        "text_chars": d["text_chars"].astype(np.float32),
        "sig": d["sig"].astype(str),
        # targets_str only feeds the TF-normalised redundancy *baseline*, which this study does
        # not use; blanking it keeps the 400-character strings out of memory for 1 M steps
        "targets_str": "",
        "file_shown": d["file_shown"].fillna("").astype(str),
        "added_lines_n": d["added_lines_n"].astype(np.int32),
        "st_passed": d["st_passed"].astype(np.int64), "st_failed": d["st_failed"].astype(np.int64),
        "st_error": d["st_error"].astype(np.int64), "st_tb": 0, "st_syntax": 0, "st_notfound": 0,
        "st_sig": "",
    })


def build_external(chunk: pd.DataFrame) -> pd.DataFrame:
    """Map one batch of an extractor table (``{tool, cmd, is_edit, file, n_added, ...}``)."""
    verbs, fams, sigs, basenames = [], [], [], []
    for tool, cmd, is_edit, file in zip(chunk["tool"].fillna(""), chunk["cmd"].fillna(""),
                                        chunk["is_edit"].fillna(0), chunk["file"].fillna("")):
        verb, fam = verb_and_flags(str(tool), str(cmd))
        if int(is_edit) == 1:
            verb = C.VERB_EDIT
        verbs.append(verb)
        fams.append(fam)
        sigs.append(sig_of(str(tool), str(cmd)))
        b = str(file).replace("\\", "/")
        basenames.append(C.h64(b.rsplit("/", 1)[-1]) if b else "")
    verb = np.array(verbs, dtype=object)
    is_test = ((chunk["n_pass"].notna()) | (chunk["n_fail"].notna())
               | (chunk["n_err"].notna())).to_numpy()
    return pd.DataFrame({
        "run_id": chunk["run_id"].astype(str), "task": chunk["instance_id"].astype(str),
        "model": chunk["model"].fillna("").astype(str), "reward": 0,
        "step": chunk["step"].astype(np.int64), "n_steps": chunk["n_steps"].astype(np.int64),
        "verb": verb, "cmd_family": np.array(fams, dtype=object),
        "is_edit": chunk["is_edit"].fillna(0).to_numpy().astype(np.int8),
        "is_read": (verb == C.VERB_READ).astype(np.int8),
        "is_search": (verb == C.VERB_SEARCH).astype(np.int8),
        "is_run": (verb == C.VERB_RUN).astype(np.int8),
        "is_test": is_test.astype(np.int8),
        "is_finish": (verb == C.VERB_FINISH).astype(np.int8),
        "obs_chars": chunk["obs_chars"].fillna(0).to_numpy().astype(np.float32),
        "text_chars": np.zeros(len(chunk), dtype=np.float32),
        "sig": np.array(sigs, dtype=object), "targets_str": "",
        "file_shown": np.array(basenames, dtype=object),
        "added_lines_n": chunk["n_added"].fillna(0).to_numpy().astype(np.int32),
        "st_passed": _status(chunk["n_pass"]), "st_failed": _status(chunk["n_fail"]),
        "st_error": _status(chunk["n_err"]), "st_tb": 0, "st_syntax": 0, "st_notfound": 0,
        "st_sig": "",
    })


# --------------------------------------------------------------------------------------
# feature tables
# --------------------------------------------------------------------------------------


def features_for(name: str, steps: pd.DataFrame) -> pd.DataFrame:
    """Prefix features for one corpus, built chunk by chunk so memory stays bounded."""
    rows: List[pd.DataFrame] = []
    ids = steps["run_id"].drop_duplicates()
    for i, chunk_ids in enumerate(_chunked(ids.to_frame(), CHUNK_RUNS)):
        sub = steps[steps["run_id"].isin(set(chunk_ids["run_id"]))]
        with contextlib.redirect_stdout(io.StringIO()):
            tabs, _meta = arm.prefix_features(sub, FRACTIONS)
        rows.append(pd.concat([tabs[f] for f in FRACTIONS], ignore_index=True))
        print(f"    {name}: chunk {i + 1} ({len(sub):,} steps, {sub['run_id'].nunique():,} runs)",
              flush=True)
    return pd.concat(rows, ignore_index=True)


def load_training(cache: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Feature table + run labels for the SWE-agent training shards."""
    if cache.exists():
        t = pd.read_parquet(cache)
        lab = pd.read_parquet(cache.with_name(cache.stem + "_labels.parquet"))
        return t, lab
    cols = ["run_id", "task", "model", "reward", "step", "n_steps", "verb", "cmd_family",
            "is_edit", "is_read", "is_search", "is_run", "is_finish", "obs_chars", "text_chars",
            "sig", "targets_str", "file_shown", "added_lines_n", "st_passed", "st_failed",
            "st_error"]
    raw = pd.read_parquet(TRAIN_STEPS, columns=cols)
    raw["st_tb"] = raw["st_syntax"] = raw["st_notfound"] = 0
    raw["st_sig"] = ""
    print(f"  training steps: {len(raw):,} rows, {raw['run_id'].nunique():,} runs")
    t = features_for("train", build_training_chunk(raw))
    lab = (raw.groupby("run_id", sort=False)
           .agg(task=("task", "first"), model=("model", "first"), reward=("reward", "first"),
                n_steps=("n_steps", "first")).reset_index())
    lab["y_fail"] = (lab["reward"] == 0).astype(int)
    t.to_parquet(cache, index=False)
    lab.to_parquet(cache.with_name(cache.stem + "_labels.parquet"), index=False)
    return t, lab


def load_external(key: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    stem, _label = CORPORA[key]
    cache = CACHE / f"{key}_features.parquet"
    if cache.exists():
        t = pd.read_parquet(cache)
        lab = pd.read_parquet(cache.with_name(cache.stem + "_labels.parquet"))
        return t, lab
    runs = pd.read_parquet(XSCAFFOLD / f"{stem}_runs.parquet",
                           columns=["run_id", "instance_id", "model", "resolved", "n_steps"])
    runs = runs[runs["resolved"].notna()].copy()
    runs["y_fail"] = 1 - runs["resolved"].astype(int)
    print(f"  {key}: {len(runs):,} runs with a resolved label "
          f"({int(runs['y_fail'].sum()):,} failing)")
    need = ["run_id", "instance_id", "model", "step", "is_edit", "file", "n_added", "tool",
            "cmd", "obs_chars", "n_pass", "n_fail", "n_err"]
    step_pf = pd.read_parquet(XSCAFFOLD / f"{stem}_steps.parquet", columns=need)
    step_pf = step_pf.merge(runs[["run_id", "n_steps"]], on="run_id", how="inner")
    print(f"  {key}: {len(step_pf):,} steps over {step_pf['run_id'].nunique():,} runs")
    pieces: List[pd.DataFrame] = []
    ids = step_pf["run_id"].drop_duplicates().to_frame()
    for i, chunk_ids in enumerate(_chunked(ids, CHUNK_RUNS)):
        sub = step_pf[step_pf["run_id"].isin(set(chunk_ids["run_id"]))]
        frame = build_external(sub)
        with contextlib.redirect_stdout(io.StringIO()):
            tabs, _meta = arm.prefix_features(frame, FRACTIONS)
        pieces.append(pd.concat([tabs[f] for f in FRACTIONS], ignore_index=True))
        del sub, frame
        print(f"    {key}: chunk {i + 1}/{len(ids) // CHUNK_RUNS + 1} done", flush=True)
    t = pd.concat(pieces, ignore_index=True)
    lab = runs[["run_id", "instance_id", "model", "n_steps", "y_fail"]].rename(
        columns={"instance_id": "task"})
    t.to_parquet(cache, index=False)
    lab.to_parquet(cache.with_name(cache.stem + "_labels.parquet"), index=False)
    return t, lab


def _columns(p: Path) -> List[str]:
    import pyarrow.parquet as pq
    return pq.ParquetFile(p).schema_arrow.names


# --------------------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------------------


def _fit(tr: pd.DataFrame, cols: List[str]) -> Dict[str, object]:
    from sklearn.linear_model import LogisticRegression
    d = tr.dropna(subset=["y_fail"])
    X = arm._clean(d[cols].to_numpy())
    y = d["y_fail"].to_numpy(dtype=float)
    mu, sd = X.mean(axis=0), np.where(X.std(axis=0) < 1e-9, 1.0, X.std(axis=0))
    m = LogisticRegression(max_iter=3000, C=1.0, solver="lbfgs", random_state=0)
    m.fit((X - mu) / sd, y)
    return {"coef": m.coef_.ravel(), "intercept": float(m.intercept_[0]), "mu": mu, "sd": sd}


def _score(blob: Dict[str, object], X: np.ndarray) -> np.ndarray:
    z = ((X - blob["mu"]) / blob["sd"]) @ blob["coef"] + blob["intercept"]
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


def evaluate() -> Dict[str, object]:
    CACHE.mkdir(parents=True, exist_ok=True)
    cols = list(BRIDGE_FEATURES)
    res: Dict[str, object] = {
        "question": "trained on SWE-agent (shards 0-3), does failure prediction survive a "
                    "different scaffold?",
        "features": cols, "n_features": len(cols),
        "excluded": ["text_chars_mean", "text_to_obs", "obs_mean_over_text (no model text "
                     "outside SWE-agent)", "err_rate uses only st_error (no traceback/syntax "
                     "flags outside SWE-agent)"],
        "fractions": {}, "corpora": {},
    }
    print("building the training feature table (SWE-agent shards 0-3) ...")
    tr, tr_lab = load_training(CACHE / "train_features.parquet")
    tr = tr.merge(tr_lab[["run_id", "y_fail", "n_steps"]], on="run_id", how="inner")
    print(f"  training rows (run x fraction): {len(tr):,}")

    for key in CORPORA:
        print(f"\nbuilding {key} ...")
        t, lab = load_external(key)
        t = t.merge(lab[["run_id", "y_fail"]], on="run_id", how="inner")
        block: Dict[str, object] = {"label": CORPORA[key][1], "n_runs": int(t["run_id"].nunique())}
        for f in FRACTIONS:
            trf = tr[np.isclose(tr["_fraction"], f)]
            tef = t[np.isclose(t["_fraction"], f)]
            blob = _fit(trf, cols)
            y = tef["y_fail"].to_numpy(dtype=float)
            s = _score(blob, arm._clean(tef[cols].to_numpy()))
            oof = arm.oof_scores(trf.reset_index(drop=True), cols, "y_fail", n_folds=5, seed=0)
            ok = np.isfinite(oof)
            row = {"n": int(len(tef)), "n_failed": int(y.sum()),
                   "auc_router": float(arm._auc(y, s)),
                   "in_corpus_auc_train": float(arm._auc(
                       trf["y_fail"].to_numpy(dtype=float),
                       _score(blob, arm._clean(trf[cols].to_numpy())))),
                   "in_corpus_oof_auc": float(arm._auc(trf["y_fail"].to_numpy(dtype=float)[ok],
                                                       oof[ok])) if ok.any() else None,
                   "baselines": {
                       "position": float(arm._auc(y, tef["_prefix_len"].to_numpy(dtype=float))),
                       "agentstop_outlen": float(arm._auc(y, tef["obs_mean"].to_numpy())),
                       "agentstop_overlap": float(arm._auc(
                           y, tef["repeat_sig_frac"].to_numpy())),
                   }}
            row["gain_over_best_baseline"] = (
                row["auc_router"] - max(row["baselines"].values()))
            row["gap_vs_in_corpus_oof"] = (
                row["auc_router"] - row["in_corpus_oof_auc"]
                if row["in_corpus_oof_auc"] is not None else None)
            block[f"{f:.2f}"] = row
            print(f"  {key:14s} f={f:.2f}  n={row['n']:6,d}  router AUC={row['auc_router']:.3f} "
                  f"(in-corpus OOF {row['in_corpus_oof_auc']:.3f}, gap "
                  f"{row['gap_vs_in_corpus_oof']:+.3f})  "
                  f"best baseline {max(row['baselines'].values()):.3f}  "
                  f"gain {row['gain_over_best_baseline']:+.3f}")
        res["corpora"][key] = block

    prim = {k: v[f"{FRACTIONS[0]:.2f}"]["auc_router"] for k, v in res["corpora"].items()}
    res["verdict"] = {
        "headline": "; ".join(f"{CORPORA[k][1]}: AUC {v:.3f}" for k, v in prim.items()),
        "transfers_above_chance_everywhere": bool(all(v > 0.5 for v in prim.values())),
        "mean_auc_at_20pct": float(np.mean(list(prim.values()))),
    }
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + res["verdict"]["headline"])
    print(f"wrote {OUT}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None, help="build one corpus only")
    ap.add_argument("--train-only", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    CACHE.mkdir(parents=True, exist_ok=True)
    if args.corpus:
        load_external(args.corpus)
    elif args.train_only:
        load_training(CACHE / "train_features.parquet")
    else:
        evaluate()


if __name__ == "__main__":
    main()
