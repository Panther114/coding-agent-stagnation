"""Probe: can the Nebius SWE-agent corpus carry OBJECTIVE per-step progress labels?

The rebuild note said the study's worst limitation is that its stagnation labels are
AI judgements, and that "this release contains no dense objective progress signal to
predict" (ReBUILD_FINDINGS section 3). That was measured on Terminal-Bench, which
stores only a final reward.

This probe asks whether the *other* corpus on disk can supply one. It measures how
much of the following is recoverable, on 1,500 trajectories:

  1. Which files the agent CREATED / EDITED (from patch observations).
  2. Which commands it ran and whether the observation shows an error.
  3. Whether the edit survived into the agent's own final `generated_patch`.
  4. How many steps contributed nothing that survives ("wasted work").
  5. Test-run observations inside the trajectory.

If (1) and (3) hold, a dense objective label exists and the study can be rebuilt on
it. If they do not, the honest answer is that they do not, and that is recorded.

No artifacts are written; this prints a report.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nebius"

# SWE-agent v1 patches look like:
#   [File: /lexicon/lexicon/providers/memset.py]
#   [1 lines above the scrolling window are hidden]
#   >>>>>>>>> OLD
#   ...
#   =========
#   NEW content
#   <<<<<<< END
FILE_HDR = re.compile(r"\[File:\s*([^\]\s]+)", re.M)
PATCH_HDR = re.compile(r"\[File:\s*([^\]]+?)\]\s*\n", re.M)
OLD_NEW = re.compile(r"^>>>>>>> OLD\s*$", re.M)
END_EDIT = re.compile(r"^<<<<<<< END\s*$", re.M)
CMD_FENCE = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.S)
EDIT_CMDS = (
    "create", "str_replace", "insert", "edit", "apply_patch", "write", "cat >", "tee ",
    "sed -i", "python -c", ">>",
)


def ai_messages(tr):
    """[(text, context_of_next_user_message)] for ai turns."""
    out = []
    for m in tr:
        role = m.get("role")
        text = m.get("text") or ""
        if role == "ai":
            out.append(text)
    return out


def observations(tr):
    return [m.get("text") or "" for m in tr if m.get("role") == "user"]


def commands_of(ai_text: str):
    cmds = []
    for block in CMD_FENCE.findall(ai_text):
        for line in block.strip().splitlines():
            line = line.strip()
            if line:
                cmds.append(line)
    return cmds


def is_edit_command(cmd: str) -> bool:
    low = cmd.lower()
    head = low.split()[0] if low.split() else ""
    if head in ("create", "str_replace", "insert", "edit", "apply_patch"):
        return True
    if head.startswith("str_replace") or head.startswith("create"):
        return True
    if low.startswith("cat >") or low.startswith("cat <<") or " tee " in low or low.startswith("tee "):
        return True
    if "sed -i" in low or low.startswith("apply_patch"):
        return True
    return False


def edited_files_in_obs(obs: str):
    """Files whose content this observation shows (open/read/edit results)."""
    return FILE_HDR.findall(obs)


def diff_files(patch: str):
    return re.findall(r"^diff --git a/(\S+)", patch or "", re.M)


def patched_lines(patch: str):
    """Set of added-line bodies in the final patch (normalised)."""
    out = set()
    for line in (patch or "").splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            body = line[1:].strip()
            if len(body) >= 8:
                out.add(body[:120])
    return out


def main() -> None:
    df = pd.read_parquet(RAW / "train-00000-of-00012.parquet")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    sample = df.head(n)
    print(f"probing {len(sample)} trajectories")

    stat = collections.Counter()
    waste_fracs = []
    n_steps_all = []
    err_fracs = []
    surv_rates = []
    files_edited_per_step = []
    test_runs_per_run = 0
    cmd_family = collections.Counter()
    final_files_hit = []

    for tr, patch, target in zip(sample["trajectory"], sample["generated_patch"], sample["target"]):
        if tr is None:
            stat["no_traj"] += 1
            continue
        obs_list = observations(tr)
        ai_list = ai_messages(tr)
        plines = patched_lines(patch)
        pfiles = set(diff_files(patch))
        n_steps = len(ai_list)
        n_steps_all.append(n_steps)
        if not plines:
            stat["empty_patch"] += 1

        # walk pairs (ai_i, obs_i)
        useful = 0
        ran_edit = 0
        err = 0
        n_obs = 0
        hit_final = 0
        for i, ai in enumerate(ai_list):
            obs = obs_list[i] if i < len(obs_list) else ""
            n_obs += 1
            cmds = commands_of(ai)
            for c in cmds:
                head = (c.split()[0] if c.split() else "?")[:14]
                cmd_family[head] += 1
            edited = is_edit_command(" ".join(cmds))
            if edited:
                ran_edit += 1
            low = obs.lower()
            if ("traceback" in low or "error:" in low or "error]" in low
                    or "no such file" in low or "not found" in low or "failed" in low):
                err += 1
            if "test session starts" in low:
                test_runs_per_run += 1
            # contribution test: does any line of the observation show up as an
            # added line of the final patch, or does it name a file the agent
            # finally patched?
            contrib = False
            if plines:
                for line in obs.splitlines():
                    s = line.strip()
                    if len(s) >= 12 and s[:120] in plines:
                        contrib = True
                        break
            if not contrib and pfiles:
                for f in edited_files_in_obs(obs):
                    base = f.rstrip("/").split("/")[-1]
                    if any(pf.endswith(base) or base.endswith(pf.split("/")[-1]) for pf in pfiles):
                        contrib = True
                        break
            if contrib:
                useful += 1
                hit_final += 1
        if n_obs:
            waste_fracs.append(1.0 - useful / n_obs)
            err_fracs.append(err / n_obs)
            files_edited_per_step.append(ran_edit / n_obs)
            if plines:
                surv_rates.append(hit_final / max(1, n_obs))
                final_files_hit.append(len(pfiles))

    print(f"\nstepping stats: mean steps {np.mean(n_steps_all):.1f} median {np.median(n_steps_all):.0f}")
    print(f"runs with empty final patch: {stat['empty_patch']}")
    w = np.array(waste_fracs)
    print(f"\nWASTED-STEP FRACTION per trajectory: mean {w.mean():.3f} median {np.median(w):.3f}")
    print(f"  quartiles {np.percentile(w, [25, 50, 75]).round(3)}")
    e = np.array(err_fracs)
    print(f"error-bearing observation fraction: mean {e.mean():.3f}")
    ed = np.array(files_edited_per_step)
    print(f"edit-command fraction of steps: mean {ed.mean():.3f} median {np.median(ed):.3f}")
    print(f"runs with >=1 in-trajectory test run: {test_runs_per_run} test runs total")
    print(f"final patch touches mean {np.mean(final_files_hit) if final_files_hit else 0:.1f} files")
    print("\nmost common command heads:", cmd_family.most_common(20))

    # does waste correlate with failure?
    ok = sample["target"].to_numpy()
    ww = np.array(waste_fracs)
    if len(ww) == len(ok):
        print(f"\nsuccess rate {ok.mean():.3f}")
        print(f"waste|success {ww[ok].mean():.3f}  waste|failure {ww[~ok].mean():.3f}")
        from scipy import stats
        print("  mannwhitney p =", stats.mannwhitneyu(ww[ok], ww[~ok]).pvalue)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
