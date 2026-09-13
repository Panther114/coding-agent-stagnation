"""Score the blinded 12-window pilot (stdlib only, no pandas/sklearn).

Reads the judge-filled blind packet + the sealed key (opens the key = unblinding,
so run ONLY after all 12 verdicts + confidences + reasons are committed):

    python3 research/scripts/score_human_sample_ci.py \
        --judge research/docs/human_check_blind/judge.csv \
        --key research/docs/human_check_blind/key/sealed_key.csv \
        --out research/results/rebuild/human_check_blind_scored.json

Verdict mapping (pre-registered):
  positive (1) = stalled | stagnant | done-redundant | done
  negative (0) = progress | productive | progress-regression-note
  excluded     = blocked-external | blocked | uncertain | empty
Confidence/reason are required for completeness but do not affect the mapping.

Reports, on the scored (non-excluded) set:
  raw agreements (human-stored, human-mechanical, stored-mechanical) + Wilson 95% CIs,
  Cohen's kappa vs each ref + bootstrap 95% CIs,
  paired difference (human-mech minus human-stored) + bootstrap CI + McNemar exact p,
  confusion counts, stagnant rates, exclusion counts.

Self-tests (no human data needed):
    python3 research/scripts/score_human_sample_ci.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

POS = {"stalled", "stagnant", "s", "done-redundant", "done", "d", "1", "true", "t", "yes", "y"}
NEG = {"progress", "productive", "productive-regression", "p", "0", "false", "f", "no", "n"}
EXC = {"blocked-external", "blocked", "b", "blocked_external",
       "uncertain", "u", "unsure", "", "none", "nan"}
CONF_OK = {"high", "medium", "low"}


def norm_verdict(v) -> str:
    s = ("" if v is None else str(v)).strip().lower().replace("_", "-")
    s = " ".join(s.split())
    if s in ("done redundant", "done redundant-verification"):
        return "done-redundant"
    if s in ("blocked external",):
        return "blocked-external"
    return s


def to_binary(v):
    s = norm_verdict(v)
    if s in POS:
        return 1
    if s in NEG:
        return 0
    return None  # excluded (blocked / uncertain / empty / unknown)


def wilson_ci(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


def kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1 = sum(a) / n
    pb1 = sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if abs(1 - pe) < 1e-12:
        return float("nan")
    return (po - pe) / (1 - pe)


def boot_ci(stat, rows: list, seed: int = 7, reps: int = 5000):
    rng = random.Random(seed)
    n = len(rows)
    vals = []
    for _ in range(reps):
        s = [rows[rng.randrange(n)] for _ in range(n)]
        v = stat(s)
        if v == v:  # skip nan
            vals.append(v)
    if not vals:
        return (float("nan"), float("nan"))
    vals.sort()
    lo = vals[int(0.025 * len(vals))]
    hi = vals[int(0.975 * len(vals)) - 1] if len(vals) > 1 else vals[0]
    return (lo, hi)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact p for discordant pair (b, c)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2 * p if b != c else 1.0)


def load_rows(judge_path: Path, key_path: Path):
    with open(judge_path, newline="", encoding="utf-8") as f:
        judge = {r["blind_id"]: r for r in csv.DictReader(f)}
    with open(key_path, newline="", encoding="utf-8") as f:
        keys = {r["blind_id"]: r for r in csv.DictReader(f)}
    if set(judge) != set(keys):
        missing = set(keys) - set(judge)
        extra = set(judge) - set(keys)
        raise SystemExit(f"blind_id mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    return judge, keys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", type=str, default="research/docs/human_check_blind/judge.csv")
    ap.add_argument("--key", type=str, default="research/docs/human_check_blind/key/sealed_key.csv")
    ap.add_argument("--out", type=str,
                    default="research/results/rebuild/human_check_blind_scored.json")
    ap.add_argument("--allow-partial", action="store_true",
                    help="score filled rows even if some are empty/excluded")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        run_selftests()
        return

    judge, keys = load_rows(Path(args.judge), Path(args.key))
    ids = sorted(keys)
    incomplete = [i for i in ids if norm_verdict(judge[i].get("your_verdict", "")) in ("", "none", "nan")]
    if incomplete and not args.allow_partial:
        print(f"REFUSAL: {len(incomplete)}/{len(ids)} rows unfilled ({', '.join(incomplete)}). "
              f"A person must commit all 12 verdicts first — this script will not guess. "
              f"Re-run with --allow-partial to score only filled rows.")
        sys.exit(2)
    noreason = [i for i in ids if not (judge[i].get("reason_step_cites") or "").strip()
                and norm_verdict(judge[i].get("your_verdict", "")) not in ("", "none", "nan")]
    noconf = [i for i in ids if (judge[i].get("confidence") or "").strip().lower() not in CONF_OK
              and norm_verdict(judge[i].get("your_verdict", "")) not in ("", "none", "nan")]
    if noreason:
        print(f"WARNING: {len(noreason)} filled rows lack a step-cited reason: {', '.join(noreason)}")
    if noconf:
        print(f"WARNING: {len(noconf)} filled rows lack confidence high/medium/low: {', '.join(noconf)}")

    scored = []
    excluded = []
    for i in ids:
        h = to_binary(judge[i].get("your_verdict", ""))
        if h is None:
            excluded.append({"blind_id": i, "verdict": judge[i].get("your_verdict", "")})
            continue
        s = int(float(keys[i]["stored_binary"]))
        m = int(float(keys[i]["mech_stagnant"]))
        scored.append({"blind_id": i, "human": h, "stored": s, "mech": m})

    n = len(scored)
    if n == 0:
        print("No scored rows (all blocked/uncertain/empty). Nothing to report.")
        sys.exit(2)

    h = [r["human"] for r in scored]
    s = [r["stored"] for r in scored]
    m = [r["mech"] for r in scored]
    a_hs = sum(1 for a, b in zip(h, s) if a == b)
    a_hm = sum(1 for a, b in zip(h, m) if a == b)
    a_sm = sum(1 for a, b in zip(s, m) if a == b)

    k_hs = kappa(h, s)
    k_hm = kappa(h, m)
    ci_hs = wilson_ci(a_hs, n)
    ci_hm = wilson_ci(a_hm, n)
    ci_sm = wilson_ci(a_sm, n)
    kci_hs = boot_ci(lambda rs: kappa([r["human"] for r in rs], [r["stored"] for r in rs]),
                     scored, args.seed, args.reps)
    kci_hm = boot_ci(lambda rs: kappa([r["human"] for r in rs], [r["mech"] for r in rs]),
                     scored, args.seed + 1, args.reps)
    diff = a_hm / n - a_hs / n
    dci = boot_ci(lambda rs: (sum(1 for r in rs if r["human"] == r["mech"]) / len(rs)
                              - sum(1 for r in rs if r["human"] == r["stored"]) / len(rs)),
                  scored, args.seed + 2, args.reps)
    # McNemar on (agree-with-stored?, agree-with-mech?): b = mech-only, c = stored-only.
    b = sum(1 for r in scored if r["human"] == r["mech"] and r["human"] != r["stored"])
    c = sum(1 for r in scored if r["human"] == r["stored"] and r["human"] != r["mech"])
    p_mc = mcnemar_exact(b, c)

    res = {
        "n_sample": len(ids),
        "n_scored": n,
        "n_excluded": len(excluded),
        "excluded": excluded,
        "human_vs_stored": a_hs / n,
        "human_vs_stored_wilson95": list(ci_hs),
        "human_vs_mechanical": a_hm / n,
        "human_vs_mechanical_wilson95": list(ci_hm),
        "stored_vs_mechanical_on_scored": a_sm / n,
        "stored_vs_mechanical_wilson95": list(ci_sm),
        "kappa_human_vs_stored": k_hs,
        "kappa_human_vs_stored_boot95": list(kci_hs),
        "kappa_human_vs_mechanical": k_hm,
        "kappa_human_vs_mechanical_boot95": list(kci_hm),
        "diff_mech_minus_stored": diff,
        "diff_boot95": list(dci),
        "mcnemar_mech_only": b,
        "mcnemar_stored_only": c,
        "mcnemar_exact_p": p_mc,
        "human_stagnant_rate": sum(h) / n,
        "stored_stagnant_rate": sum(s) / n,
        "mechanical_stagnant_rate": sum(m) / n,
        "bootstrap_reps": args.reps,
        "bootstrap_seed": args.seed,
        "warning": ("n<=12: CIs are wide by design; report intervals, never points. "
                    "A 1-window swing is noise."),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"scored {n}/{len(ids)} rows (excluded {len(excluded)}: "
          + (", ".join(e['blind_id'] + "=" + str(e['verdict']) for e in excluded) or "none") + ")")
    print(f"  human vs stored     : {res['human_vs_stored']:.1%}  95% Wilson [{ci_hs[0]:.1%}, {ci_hs[1]:.1%}]"
          f"  (kappa {k_hs:+.3f} [{kci_hs[0]:+.3f}, {kci_hs[1]:+.3f}])")
    print(f"  human vs mechanical : {res['human_vs_mechanical']:.1%}  95% Wilson [{ci_hm[0]:.1%}, {ci_hm[1]:.1%}]"
          f"  (kappa {k_hm:+.3f} [{kci_hm[0]:+.3f}, {kci_hm[1]:+.3f}])")
    print(f"  stored vs mechanical: {res['stored_vs_mechanical_on_scored']:.1%}")
    print(f"  diff (mech-stored)  : {diff:+.3f}  boot95 [{dci[0]:+.3f}, {dci[1]:+.3f}]"
          f"  McNemar b={b} c={c} p={p_mc:.3f}")
    print(f"wrote {out}")


def run_selftests() -> None:
    # 1. Wilson sanity: 9/12.
    lo, hi = wilson_ci(9, 12)
    assert 0.40 < lo < 0.55 and 0.85 < hi < 0.96, (lo, hi)
    # 2. Kappa perfect / chance.
    assert abs(kappa([0, 0, 1, 1], [0, 0, 1, 1]) - 1.0) < 1e-9
    assert abs(kappa([0, 0, 1, 1], [0, 1, 0, 1]) - 0.0) < 1e-9
    # 3. Mapping incl. codebook labels.
    assert to_binary("stalled") == 1 and to_binary("STAGNANT") == 1
    assert to_binary("done-redundant") == 1
    assert to_binary("progress") == 0 and to_binary("PRODUCTIVE") == 0
    assert to_binary("blocked-external") is None and to_binary("uncertain") is None
    assert to_binary("") is None
    # 4. McNemar edges.
    assert mcnemar_exact(0, 0) == 1.0
    assert 0.0 <= mcnemar_exact(5, 0) <= 0.1
    # 5. Bootstrap CI contains point on separable data.
    rows = [{"human": 1, "stored": 1, "mech": 0}] * 6 + \
           [{"human": 0, "stored": 0, "mech": 0}] * 6
    lo, hi = boot_ci(lambda rs: sum(r["human"] == r["stored"] for r in rs) / len(rs),
                     rows, seed=1, reps=500)
    assert lo <= 1.0 <= hi, (lo, hi)
    print("selftest: 5/5 groups passed (wilson, kappa, mapping, mcnemar, bootstrap)")


if __name__ == "__main__":
    main()
