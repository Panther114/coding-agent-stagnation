"""Quick self-test for the action normalizer."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.stdout.reconfigure(encoding="utf-8")
from normalize import normalize_action  # noqa: E402

TESTS = [
    ("bash_command", 'grep -rn "def authenticate" /lexicon/lexicon/providers/memset.py'),
    ("bash_command", "cat > /app/ars.R << 'EOF'\nars <- function(n) {}\nEOF"),
    ("bash_command", "Rscript -e \"source('/app/ars.R'); test()\""),
    ("Bash", "sed -n '10,20p' /app/ars.R"),
    ("str_replace_editor", 'str_replace(path="/repo/pkg/mod.py", old_str="foo", new_str="bar")'),
    ("bash_command", "cd /app && python3 -m pytest tests/test_api.py -x"),
    ("execute_bash", 'find /repo -name "*.py" | xargs grep -l "Provider"'),
    ("Bash", "ls -la /app"),
    ("Grep", 'pattern: "authenticate"; path: /repo'),
    ("Read", '{"file_path": "/app/ars.R", "offset": 10}'),
    ("Edit", '{"file_path": "/app/ars.R", "old_string": "x", "new_string": "y"}'),
    ("bash_command", "apt-get install -y r-base"),
    ("mark_task_complete", "{}"),
    ("think", "I should reconsider the approach"),
]

for name, arg in TESTS:
    r = normalize_action(name, arg)
    print(f"{name:18} | tool={r.tool:8} verb={r.verb:16} kind={r.kind:8} "
          f"targets={list(r.targets[:3])} terms={list(r.search_terms[:1])}")
