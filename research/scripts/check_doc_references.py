"""Reference integrity: every artifact the docs cite must exist.

The rebuild's rule is that no number in the prose is typed by hand and every claim names the
artifact that produced it. That rule is only enforced if the named artifacts are real, so this
walks every ``results/rebuild/<name>`` token in the documentation and fails on a missing file,
plus reports artifacts that exist but are named nowhere (unlikely to be wrong, but worth seeing).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "rebuild"
DOCS = [ROOT / "README.md", ROOT / "AI_ASSISTANCE_LOG.md", *sorted((ROOT / "docs").glob("*.md"))]

TOKEN = re.compile(r"results/rebuild/([A-Za-z0-9_\-{},\*]+\.(?:json|parquet))")
BRACE = re.compile(r"\{([^}]*)\}")

# Names that are legitimately cited without a file existing.  Each needs a reason, because an
# unexplained exemption is exactly the kind of silent hole this check exists to catch.
EXEMPT = {
    "human_check_scored.json":
        "output of score_human_sample.py; deliberately absent until the student scores the 12 "
        "windows (HANDOFF §5) — the agent must not fill it in",
    "data_ledger.json":
        "planned name in GAP_ANALYSIS_AND_PLAN.md; delivered as rebuild_numbers.json + "
        "extraction_verification.json instead (see the 'delivered as' note on that plan row)",
    "sequential.json":
        "planned name in GAP_ANALYSIS_AND_PLAN.md; delivered as waste_alarm.json + "
        "sequential_deadend.json + sustained_waste.json instead",
    "value.json":
        "planned name in GAP_ANALYSIS_AND_PLAN.md; delivered as cost.json + detector_value.json "
        "+ on_target.json instead",
}


def expand(name: str) -> list[str]:
    m = BRACE.search(name)
    if not m:
        return [name]
    out = []
    for part in m.group(1).split(","):
        out.extend(expand(name[: m.start()] + part.strip() + name[m.end():]))
    return out


def main() -> None:
    missing, cited = [], set()
    for doc in DOCS:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for raw in set(TOKEN.findall(text)):
            for name in expand(raw):
                if "*" in name:
                    continue
                cited.add(name)
                if not (RES / name).exists() and name not in EXEMPT:
                    missing.append({"doc": doc.name, "artifact": name})

    present = {p.name for p in RES.iterdir() if p.is_file()}
    uncited = sorted(present - cited)
    exemptions_used = sorted({m for m in cited if m in EXEMPT and not (RES / m).exists()})
    res = {
        "docs_scanned": [d.name for d in DOCS if d.exists()],
        "artifacts_present": len(present),
        "artifacts_cited": len(cited),
        "missing": missing,
        "uncited": uncited,
        "exemptions": {k: EXEMPT[k] for k in exemptions_used},
    }
    (RES / "doc_reference_integrity.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"docs scanned: {len(res['docs_scanned'])}")
    print(f"artifacts present: {len(present)}  cited: {len(cited)}  uncited: {len(uncited)}")
    if exemptions_used:
        print("exempt (cited as not-yet-existing, with reason):")
        for e in exemptions_used:
            print(f"  - {e}: {EXEMPT[e]}")
    if uncited:
        print("uncited (present but named nowhere):")
        for u in uncited:
            print(f"  - {u}")
    if missing:
        print("MISSING — cited but absent:")
        for m in missing:
            print(f"  - {m['doc']}: results/rebuild/{m['artifact']}")
        sys.exit(1)
    print("all cited artifacts exist")


if __name__ == "__main__":
    main()
