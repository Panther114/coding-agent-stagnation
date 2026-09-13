"""Record the decisive tally: more post-completion windows were contested than survived."""
import sys

sys.stdout.reconfigure(encoding="utf-8")
p = "docs/KEY_FINDINGS.md"
s = open(p, encoding="utf-8").read()

anchor = "The consequence is concrete: of the 59 `DONE_REDUNDANT` windows only **12 were read twice and"
i = s.find(anchor)
if i < 0:
    print("anchor not found")
    raise SystemExit(1)
j = s.find("treat\n     post-completion numbers as descriptive rather than measured.", i)
if j < 0:
    j = s.find("post-completion numbers as descriptive rather than measured.", i)
j += len("post-completion numbers as descriptive rather than measured.")

new = """The tally is decisive and worth stating plainly. **Twenty windows in the gold carry the split
     `PRODUCTIVE|DONE_REDUNDANT`, and all twenty were held out** — spread over five trajectories
     (`build-pov-ray__6eHBkqP` 7, `cobol-modernization__z8rbv6p` 7,
     `custom-memory-heap-crash__NAMeUua` 3, `compile-compcert__3AjSGCy` 2, `db-wal-recovery__tQJsCmY`
     1). Against that, the surviving `DONE_REDUNDANT` class contains only **12 windows read by more
     than one reader, and all 12 agreed**. So **more post-completion windows were contested and
     removed than survived with corroboration** (20 versus 12). The class the paper reasons about
     is the agreed subset of a boundary the codebook does not define; treat post-completion numbers
     as descriptive of the clearest instances, not as measurements of the category."""
s = s[:i] + new + s[j:]
open(p, "w", encoding="utf-8").write(s)
print("recorded; length", len(s))
