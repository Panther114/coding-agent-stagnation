"""Throwaway: remove the duplicated _PROGRESS_PCT definition."""
from pathlib import Path

p = Path(r"D:\Gavania\Academic\Competitions\Agent_Correction\research\src\agentstall\verify.py")
s = p.read_text(encoding="utf-8")
dup = '_PROGRESS_PCT = re.compile(r"\\[\\s*\\d+%\\]")\n'
print("occurrences of dup line:", s.count(dup))
lines = s.splitlines(keepends=True)
keep = []
seen = 0
for i, ln in enumerate(lines):
    if ln.rstrip("\n") == dup.rstrip("\n"):
        seen += 1
        if seen == 2:
            print(f"dropping duplicate at line {i+1}")
            continue
    keep.append(ln)
p.write_text("".join(keep), encoding="utf-8")
print("now:", p.read_text(encoding="utf-8").count(dup))
