"""Build a blinded 12-window human pilot packet (stdlib only).

Reads:
  windows_to_judge.csv          (authoritative 12-row judge list, card paths)
  research/results/rebuild/human_check_sample.csv  (stored judgement + mechanical,
      used ONLY for the sealed key, never for the judge view)

Writes under research/docs/human_check_blind/:
  judge.csv                     (blind_id, task, t, w, card_blind, your_verdict, ...)
  packet.md                     (judge-facing table, no labels)
  cards/Bxx.md                  (redacted card copies: outcome line removed)
  key/sealed_key.csv + sealed_key.json  (blind_id -> orig mapping + labels; DO NOT OPEN until judged)
  key/SHA256SUMS                (integrity)
  README.md                     (blinding rules)

Deterministic: blind order is a seeded shuffle (default 20260914), documented in packet.md.
No model verdicts are filled in. Requires only the standard library.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
JUDGE_CSV = REPO / "tasks" / "windows_to_judge.csv"
SAMPLE_CSV = ROOT / "results" / "rebuild" / "human_check_sample.csv"
OUT = ROOT / "docs" / "human_check_blind"


def redact_card(text: str, blind_id: str) -> tuple[str, int]:
    """Remove outcome-leaking and identity-leaking lines from a card copy."""
    import re
    out_lines = []
    n = 0
    for line in text.splitlines():
        low = line.strip().lower()
        if line.strip().startswith("# Annotation card"):
            out_lines.append(f"# Annotation card `{blind_id}` (blinded copy)")
            n += 1
            continue
        # Redact the header line carrying final task reward / trajectory length is kept
        # for context but reward token is masked; scaffold/model kept (not a label).
        if "final task reward" in low:
            # Mask the reward digit(s) but keep the line shape so the judge knows it was hidden.
            import re
            masked = re.sub(r"final task reward:\s*\S+", "final task reward: [HIDDEN]", line)
            out_lines.append(masked)
            out_lines.append("> NOTE (blinding): outcome hidden. Ignore any solved/reward claim elsewhere.")
            n += 1
            continue
        if "run solved the task" in low:
            import re
            masked = re.sub(r"run solved the task:\s*\S+", "run solved the task: [HIDDEN]", line)
            out_lines.append(masked)
            n += 1
            continue
        out_lines.append(line)
    return "\n".join(out_lines) + "\n", n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--out", type=str, default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    cards_out = out / "cards"
    key_out = out / "key"
    cards_out.mkdir(parents=True, exist_ok=True)
    key_out.mkdir(parents=True, exist_ok=True)

    # Load judge list (authoritative order n=1..12 + card paths).
    with open(JUDGE_CSV, newline="", encoding="utf-8") as f:
        judge_rows = list(csv.DictReader(f))
    assert len(judge_rows) == 12, f"expected 12 rows, got {len(judge_rows)}"

    # Load stored/mechanical labels keyed by (task, run).
    key: dict[tuple[str, str], dict] = {}
    with open(SAMPLE_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            run_short = str(r["run_id"]).split("__")[-1]
            key[(r["task"], run_short)] = {
                "run_id": r["run_id"],
                "t": r["t"],
                "w": r["w"],
                "gold": r.get("gold", ""),
                "binary": r.get("binary", ""),
                "y_stagnation": r.get("y_stagnation", ""),
                "mech_stagnant": r.get("mech_stagnant", ""),
            }

    # Assemble records, verifying every card exists.
    records = []
    for jr in judge_rows:
        task, run, card = jr["task"], jr["run"], jr["card"]
        src = REPO / card
        assert src.exists(), f"missing card file: {card}"
        k = key.get((task, run))
        assert k is not None, f"no stored/mechanical row for {(task, run)}"
        records.append({"n": jr["n"], "task": task, "run": run,
                        "card": card, "src": src, "key": k})

    # Seeded blind order.
    rng = random.Random(args.seed)
    order = list(range(len(records)))
    rng.shuffle(order)

    judge_fieldnames = ["blind_id", "task", "t", "w", "card_blind",
                        "your_verdict", "confidence", "reason_step_cites"]
    key_fieldnames = ["blind_id", "orig_n", "task", "run", "run_id", "t", "w",
                      "card_orig", "card_blind", "stored_gold", "stored_binary",
                      "mech_quiet_share", "mech_stagnant", "sha256_blind_card"]
    judge_rows_out = []
    key_rows_out = []
    packet_lines = [
        "# Human pilot — blind packet (12 windows)",
        "",
        f"Blind order seed: `{args.seed}` (shuffle of the 12 rows in `windows_to_judge.csv`).",
        "Do NOT open `key/` until all 12 verdicts + confidences + reasons are committed and timestamped.",
        "Do NOT open `research/docs/human_check_sample.md`, `human_check_readable.md`,",
        "`research/results/rebuild/human_check_sample.csv`, or run any scoring script until committed.",
        "",
        "For each row: open the blind card copy, apply `docs/3-judge-sheet.md`,",
        "fill `judge.csv` (`your_verdict`: stalled | progress | blocked-external | done-redundant | uncertain).",
        "",
        "| blind_id | task | t | w | blind card |",
        "|---|---|---|---|---|",
    ]

    for bi, idx in enumerate(order, start=1):
        rec = records[idx]
        blind_id = f"B{bi:02d}"
        blind_name = f"{blind_id}.md"
        dst = cards_out / blind_name
        text = rec["src"].read_text(encoding="utf-8", errors="replace")
        redacted, _ = redact_card(text, blind_id)
        header = (f"<!-- BLIND COPY {blind_id}. "
                  f"Outcome masked. Do not search the repo for card filenames. -->\n\n")
        dst.write_text(header + redacted, encoding="utf-8")
        h = hashlib.sha256((header + redacted).encode("utf-8")).hexdigest()
        k = rec["key"]
        judge_rows_out.append({
            "blind_id": blind_id, "task": rec["task"], "t": k["t"], "w": k["w"],
            "card_blind": f"research/docs/human_check_blind/cards/{blind_name}",
            "your_verdict": "", "confidence": "", "reason_step_cites": "",
        })
        key_rows_out.append({
            "blind_id": blind_id, "orig_n": rec["n"], "task": rec["task"], "run": rec["run"],
            "run_id": k["run_id"], "t": k["t"], "w": k["w"],
            "card_orig": rec["card"], "card_blind": f"research/docs/human_check_blind/cards/{blind_name}",
            "stored_gold": k["gold"], "stored_binary": k["binary"],
            "mech_quiet_share": k["y_stagnation"], "mech_stagnant": k["mech_stagnant"],
            "sha256_blind_card": h,
        })
        packet_lines.append(f"| {blind_id} | {rec['task']} | {k['t']} | {k['w']} | `cards/{blind_name}` |")

    with open(out / "judge.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=judge_fieldnames)
        w.writeheader()
        w.writerows(judge_rows_out)
    with open(key_out / "sealed_key.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=key_fieldnames)
        w.writeheader()
        w.writerows(key_rows_out)
    with open(key_out / "sealed_key.json", "w", encoding="utf-8") as f:
        json.dump({"seed": args.seed, "rows": key_rows_out}, f, indent=2)
    (out / "packet.md").write_text("\n".join(packet_lines) + "\n", encoding="utf-8")

    # SHA over blind cards + judge.csv + sealed key.
    sums = []
    for p in sorted(cards_out.glob("*.md")) + [out / "judge.csv",
                                               key_out / "sealed_key.csv",
                                               key_out / "sealed_key.json"]:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        sums.append(f"{h}  {p.relative_to(out)}")
    (key_out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    readme = "\n".join([
        "# human_check_blind — blinding rules",
        "",
        "- Judge works ONLY from `packet.md` + `cards/Bxx.md` + `judge.csv` + `docs/3-judge-sheet.md`.",
        "- Sealed: `key/` (mapping + stored/mechanical labels + SHA). Opening it before committing",
        "  all 12 verdicts invalidates the pilot. Record open time in the provenance log.",
        "- Also sealed until committed: `docs/human_check_sample.md`, `docs/human_check_readable.md`,",
        "  `results/rebuild/human_check_sample.csv`, any scoring script output.",
        "- Card copies are redacted (`final task reward: [HIDDEN]`). If any outcome leaks through card",
        "  prose, ignore it and note it in the reason column.",
        "- 10/12 cards are `cards_dense/` (rich), 2/12 are `cards/` (sparse, heavier `$NN` redaction:",
        "  orig n=3 compile-compcert, n=8 financial-document-processor). Difficulty differs by design;",
        "  mark low confidence / uncertain rather than guessing through redaction.",
        "- Fill every row: your_verdict ∈ {stalled|progress|blocked-external|done-redundant|uncertain},",
        "  confidence ∈ {high|medium|low}, reason_step_cites = 1 sentence with step numbers.",
        "- No model may fill `judge.csv`. A model-filled sheet is fabrication, not a result.",
        "",
    ])
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(f"wrote {out}/judge.csv, packet.md, {len(key_rows_out)} blind cards, key/ + SHA256SUMS (seed {args.seed})")


if __name__ == "__main__":
    main()
