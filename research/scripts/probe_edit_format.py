"""Exactly how does a SWE-agent edit turn and its observation look?

Needed to turn "was this edit reverted?" into a mechanical test rather than a
guess. Prints raw turns; no artifacts.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "raw" / "nebius" / "train-00000-of-00012.parquet"
FENCE = re.compile(r"```(?:bash|sh)?\s*\n(.*?)```", re.S)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    d = pd.read_parquet(P, columns=["instance_id", "trajectory", "generated_patch"])
    shown_edit = 0
    shown_create = 0
    shown_shell_edit = 0
    for i in range(len(d)):
        traj = list(d["trajectory"][i])
        for j, m in enumerate(traj):
            if m.get("role") != "ai":
                continue
            text = m.get("text") or ""
            for body in FENCE.findall(text):
                head = body.strip().splitlines()[0] if body.strip() else ""
                obs = ""
                if j + 1 < len(traj) and traj[j + 1].get("role") == "user":
                    obs = traj[j + 1].get("text") or ""
                if head.startswith("str_replace") and shown_edit < 2:
                    shown_edit += 1
                    print("=" * 90)
                    print("ACTION (str_replace):")
                    print(body[:1200])
                    print("--- OBSERVATION:")
                    print(obs[:1200])
                elif head.startswith("create") and shown_create < 1:
                    shown_create += 1
                    print("=" * 90)
                    print("ACTION (create):")
                    print(body[:700])
                    print("--- OBSERVATION:")
                    print(obs[:700])
                elif re.match(r"^(sed|cat|python|tee|patch)", head) and ">" in body and shown_shell_edit < 2:
                    shown_shell_edit += 1
                    print("=" * 90)
                    print("ACTION (shell edit candidate):", head[:80])
                    print(body[:600])
                    print("--- OBSERVATION:")
                    print(obs[:600])
        if shown_edit >= 2 and shown_create >= 1 and shown_shell_edit >= 2:
            break
    # also: does the agent's own final patch appear in the trajectory as an observation?
    print("\n" + "=" * 90)
    n_patch_in_obs = 0
    for i in range(min(200, len(d))):
        traj = list(d["trajectory"][i])
        patch = d["generated_patch"][i] or ""
        if len(patch) < 50:
            continue
        sig = patch.strip().splitlines()[0][:40]
        for m in traj:
            if m.get("role") == "user" and (m.get("text") or "").find("diff --git") >= 0:
                n_patch_in_obs += 1
                break
    print(f"runs (of 200) whose trajectory contains a 'diff --git' observation: {n_patch_in_obs}")


if __name__ == "__main__":
    main()
