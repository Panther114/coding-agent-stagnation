"""Stage timing probe for the experiment pipeline."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")

from build_dataset import build_views, compute_idf  # noqa: E402
from evidence import task_terms  # noqa: E402
from loaders import Action, Step, Trajectory, tb2_task_statements  # noqa: E402
from monitors import WindowFeatureCache  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
t0 = time.time()
sample = [json.loads(l) for l in open("data/processed/tb2/sample_trajectories.jsonl", encoding="utf-8")][:N]
trajs = []
for b in sample:
    steps = [Step(index=i, text=s["text"], actions=[Action(a["name"], a["arg"]) for a in s["actions"]],
                  observation=s["obs"]) for i, s in enumerate(b["steps"])]
    trajs.append(Trajectory(traj_id=b["traj_id"], task=b["task"], agent=b["agent"], model=b["model"],
                            reward=b["reward"], steps=steps, meta=b["meta"]))
print(f"load   {time.time()-t0:6.1f}s  n={len(trajs)} steps={sum(len(t.steps) for t in trajs)}")
st = tb2_task_statements()
views = build_views(trajs, st)
print(f"views  {time.time()-t0:6.1f}s")
idf = compute_idf(views, "tb2")
print(f"idf    {time.time()-t0:6.1f}s terms={len(idf)}")
for v in views:
    v.idf = idf
rows = 0
tc = time.time()
for v in views:
    cfg = {"_terms": task_terms(st.get(v.task, "")), "rel_threshold": 0.5}
    c = WindowFeatureCache(v, 10, cfg)
    rows += c.n
print(f"cache  {time.time()-tc:6.1f}s rows={rows}")
tc = time.time()
for v in views:
    cfg = {"_terms": task_terms(st.get(v.task, "")), "rel_threshold": 0.5}
    WindowFeatureCache(v, 20, cfg)
print(f"cache20 {time.time()-tc:6.1f}s")
print(f"total  {time.time()-t0:6.1f}s")
