"""Smoke test for the monitor stack end to end."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

from build_dataset import build_views, compute_idf  # noqa: E402
from evidence import task_terms  # noqa: E402
from features import ALL_FEATURES, FEATURE_CHANNEL, first_seen_index  # noqa: E402
from loaders import load_tb2, tb2_task_statements  # noqa: E402
from monitors import (ExactRepeat, FeatureMonitor, StepBudget, WindowFeatureCache,  # noqa: E402
                      LogisticMonitor, sustained_alarm)

MON_BASE = {
    "B2": (["rep_exact_frac", "rep_norm_frac"], [+1, +1]),
    "B4_sem": (["nov_distinct_sig_frac"], [-1]),
    "C_evid": (["ev_new_relevant_rate", "ev_persist_rate"], [-1, -1]),
    "C_ver": (["ver_progress", "ver_has_improvement"], [-1, -1]),
}


def main():
    trajs = load_tb2(limit=6)
    stmts = tb2_task_statements()
    views = build_views(trajs, stmts)
    idf = compute_idf(views, "tb2")
    for v in views:
        v.idf = idf
    Xtr = []
    for v in views:
        cfg = {"_terms": task_terms(stmts.get(v.task, "")), "rel_threshold": 0.5}
        cache = WindowFeatureCache(v, 10, cfg)
        print(f"{v.traj_id[:40]:42} steps={v.n_steps:4d} cache={cache.X.shape}")
        Xtr.append(cache.X)
        for name, (feats, dirs) in MON_BASE.items():
            m = FeatureMonitor(name, feats, dirs).fit(Xtr[0])
            s = m.score_series(cache)
            alarm = sustained_alarm(s, 0.7, k=2, min_step=5)
            print(f"    {name:10} score mean={np.nanmean(s):.3f} max={np.nanmax(s):.3f} alarm={alarm}")
        sb = StepBudget(60)
        er = ExactRepeat(3)
        print(f"    B1 alarm={sustained_alarm(sb.score_series(cache), 0.5)} "
              f"B2 alarm={sustained_alarm(er.score_series(cache), 1.0)}")


if __name__ == "__main__":
    main()
