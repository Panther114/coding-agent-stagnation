"""Cost of low-yield turns: does an agent burn tokens on round-trips that produce almost nothing?

The claim under test (from a collaborator measuring a runtime plugin): agents spend turns on
wait/poll calls and on unbatched tool calls, and each such turn re-sends the whole accumulated
context, so the cost is in the INPUT, not the few characters of output.

That reframing matters, because the naive measurement says the opposite.  In Terminal-Bench the
2,036 BashOutput/TaskOutput poll turns have a mean observation of 247 chars and a mean output of
19 chars -- trivially cheap in isolation, 0.19% of steps.  If the hypothesis is right, the real
cost is that each of those turns pays for the entire conversation so far.

So this script prices turns by the context they re-send:

    context(t)  ~= accumulated (observation + agent text) characters of steps 0..t-1
    total cost  ~= sum over turns of context(t)          [the input side dominates]
    low-yield   ~= turns where the turn's own output + observation is a small fraction of context

and reports, per corpus and per scaffold:
  * the share of total input-priced cost spent on poll turns specifically,
  * the share spent on ALL turns whose own contribution is under a few percent of context,
  * the same for turns that repeat the previous turn's command signature.

Everything is reported as a share of that corpus's own total, so corpora of different sizes are
comparable, and the numbers are explicitly estimates from character counts, not billed tokens.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rebuild"

TABLES = [
    ("tb2_all_scaffolds", ROOT / "data" / "processed" / "steps_tb2_dedup" / "tb2" / "steps.parquet"),
    ("swe_agent_shards0_3", ROOT / "data" / "processed" / "steps" / "nebius" / "steps.parquet"),
    ("swe_agent_shards4_7", ROOT / "data" / "processed" / "steps_repl" / "nebius" / "steps.parquet"),
    ("swe_agent_shards8_11", ROOT / "data" / "processed" / "steps_repl2" / "nebius" / "steps.parquet"),
]

POLL_TOOLS = {"bashoutput", "bash_output", "taskoutput", "task_output", "wait", "sleep",
              "wait_shell_command"}


def analyse(label: str, path: Path, low_yield_frac: float = 0.05) -> Dict[str, object]:
    if not path.exists():
        return {"table": label, "error": "missing"}
    import pyarrow.parquet as pq
    cols = pq.ParquetFile(str(path)).schema_arrow.names
    want = [c for c in ("run_id", "task", "model", "agent", "step", "n_steps", "tool",
                        "obs_chars", "text_chars", "sig", "reward") if c in cols]
    df = pd.read_parquet(path, columns=want)
    n = len(df)
    res: Dict[str, object] = {"table": label, "n_steps": int(n),
                              "n_runs": int(df["run_id"].nunique())}
    if not n:
        return res

    obs = pd.to_numeric(df["obs_chars"], errors="coerce").fillna(0).to_numpy(dtype=float)
    txt = pd.to_numeric(df["text_chars"], errors="coerce").fillna(0).to_numpy(dtype=float)
    own = obs + txt

    # per-run cumulative context, in step order
    run = df["run_id"].astype(str).to_numpy()
    order = np.lexsort((df["step"].to_numpy(), run))
    obs_s, txt_s, own_s, run_s = obs[order], txt[order], own[order], run[order]
    cum = np.cumsum(own_s)
    ctx = np.zeros(len(cum))
    ctx[1:] = cum[:-1]
    # reset context at run boundaries
    new_run = np.ones(len(run_s), dtype=bool)
    new_run[1:] = run_s[1:] != run_s[:-1]
    starts = np.flatnonzero(new_run)
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(run_s)
        ctx[s:e] -= (cum[s - 1] if s > 0 else 0.0)

    total_ctx = float(ctx.sum())
    res["total_context_chars"] = total_ctx
    res["mean_context_chars"] = float(ctx.mean())

    tool = df["tool"].astype(str).str.lower().to_numpy()
    is_poll_s = np.isin(tool[order], list(POLL_TOOLS))
    res["poll_turns"] = int(is_poll_s.sum())
    res["poll_cost_share"] = (float(ctx[is_poll_s].sum() / total_ctx)
                              if total_ctx > 0 else None)

    # low-yield turns: own contribution is a small fraction of the context that carried it
    with np.errstate(divide="ignore", invalid="ignore"):
        yield_ratio = np.where(ctx > 0, own_s / np.maximum(ctx, 1.0), np.nan)
    low = np.isfinite(yield_ratio) & (yield_ratio < low_yield_frac)
    res[f"low_yield_turns_lt_{low_yield_frac}"] = int(low.sum())
    res[f"low_yield_cost_share_lt_{low_yield_frac}"] = (
        float(ctx[low].sum() / total_ctx) if total_ctx > 0 else None)

    # repeated-signature turns
    if "sig" in df:
        sig = df["sig"].astype(str).to_numpy()[order]
        rep = np.zeros(len(sig), dtype=bool)
        rep[1:] = (sig[1:] == sig[:-1]) & (sig[1:] != "")
        rep &= ~new_run
        res["repeat_turns"] = int(rep.sum())
        res["repeat_cost_share"] = (float(ctx[rep].sum() / total_ctx)
                                    if total_ctx > 0 else None)

    res["mean_own_chars"] = float(own_s.mean())
    res["median_context_chars"] = float(np.median(ctx))

    # by scaffold-ish grouping (model or agent, whichever exists)
    gcol = "agent" if "agent" in df and df["agent"].nunique() > 1 else (
        "model" if "model" in df and df["model"].nunique() > 1 else None)
    if gcol:
        grp = df[gcol].astype(str).to_numpy()[order]
        rows = []
        for k in pd.unique(grp):
            m = grp == k
            if m.sum() < 500:
                continue
            tt = ctx[m].sum()
            rows.append({
                "group": str(k), "turns": int(m.sum()),
                "cost_share_of_corpus": round(float(tt / total_ctx), 5) if total_ctx else None,
                "poll_share_within": round(float(ctx[m & is_poll_s].sum() / tt), 6) if tt else None,
                "low_yield_share_within": (round(float(ctx[m & low].sum() / tt), 5)
                                           if tt else None),
            })
        rows.sort(key=lambda r: -(r["cost_share_of_corpus"] or 0))
        res["by_group"] = rows[:15]
        res["group_column"] = gcol
    return res


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out: Dict[str, object] = {
        "purpose": ("price agent turns by the context they re-send, to test the claim that "
                    "wait/poll and unbatched turns burn tokens whose cost is in the INPUT"),
        "caveat": ("character-count estimates, not billed tokens; the absolute numbers are "
                   "proxies and only the shares should be compared"),
        "tables": {},
    }
    for label, path in TABLES:
        print(f"\n=== {label} ===", flush=True)
        r = analyse(label, path)
        out["tables"][label] = r
        if "error" in r:
            print(f"  {r['error']}")
            continue
        print(f"  steps={r['n_steps']:,} runs={r['n_runs']:,} "
              f"mean_context={r['mean_context_chars']:,.0f} chars")
        print(f"  poll turns={r['poll_turns']:,}  cost share={r['poll_cost_share']:.4%}"
              if r.get("poll_cost_share") is not None else "  poll: n/a")
        lo = r.get("low_yield_cost_share_lt_0.05")
        print(f"  turns contributing <5% of their context: {r.get('low_yield_turns_lt_0.05'):,}"
              f"  cost share={lo:.2%}" if lo is not None else "")
        rs = r.get("repeat_cost_share")
        if rs is not None:
            print(f"  repeated-signature turns: {r.get('repeat_turns'):,}  cost share={rs:.2%}")
        for g in (r.get("by_group") or [])[:6]:
            print(f"    {g['group'][:34]:34s} turns={g['turns']:>7,} "
                  f"corpus_cost={g['cost_share_of_corpus']:.2%} "
                  f"low_yield={g['low_yield_share_within']:.2%}")

    (OUT / "roundtrip_cost.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"\nwrote {OUT / 'roundtrip_cost.json'}")


if __name__ == "__main__":
    main()
