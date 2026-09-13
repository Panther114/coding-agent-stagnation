"""Print compact structural peeks of specific columns for the critical candidates."""
from __future__ import annotations

import json
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "_cache" / "recon" / "raw"


def load(name: str):
    f = next(RAW.glob(f"{name}*.json"))
    return json.loads(f.read_text(encoding="utf-8"))


def show(title: str, s: str, n: int = 1400):
    print(f"\n---- {title} ----")
    print(s[:n].replace("\x00", ""))


# 1) nebius SWE-rebench-openhands: the `trajectory` column
d = load("nebius__SWE-rebench-openhands")
row = d["rows"][0]["row"]
print("=" * 100)
print("nebius/SWE-rebench-openhands-trajectories")
print("=" * 100)
for k, v in row.items():
    if k == "trajectory":
        print(f"{k}: type={type(v).__name__} len={len(v) if hasattr(v,'__len__') else '?'}")
        if isinstance(v, list):
            print(f"  n_items={len(v)}  item0_type={type(v[0]).__name__}")
            for i, it in enumerate(v[:3]):
                print(f"  [{i}] {json.dumps(it, ensure_ascii=False)[:700]}")
        else:
            show("trajectory (raw)", str(v), 2500)
    else:
        print(f"{k}: {json.dumps(v, ensure_ascii=False)[:300]}")

# 2) SWE-Gym OpenHands sampled: test_result column + observation format
d = load("SWE-Gym__OpenHands-Sampled")
row = d["rows"][0]["row"]
print("\n" + "=" * 100)
print("SWE-Gym/OpenHands-Sampled-Trajectories")
print("=" * 100)
print("test_result column ->", json.dumps(row.get("test_result"), ensure_ascii=False)[:900])
msgs = row.get("messages")
if isinstance(msgs, str):
    msgs = json.loads(msgs)
print(f"n_messages={len(msgs)}")
for i, m in enumerate(msgs[:6]):
    c = m.get("content")
    if isinstance(c, list):
        c = " ".join(json.dumps(x, ensure_ascii=False) for x in c)
    print(f"  [{i}] role={m.get('role')!r:12} keys={sorted(m.keys())} content[:400]={str(c)[:400]!r}")
# print a tool observation
for i, m in enumerate(msgs):
    if m.get("role") == "tool":
        c = m.get("content")
        print(f"\n  TOOL OBS [{i}]: {str(c)[:1500]}")
        break
