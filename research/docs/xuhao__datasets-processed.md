# datasets/processed — regenerable derivatives (gitignored, never committed)

Rebuild from raw with pinned env (`research/requirements.lock`):

```bash
.venv/bin/python research/scripts/build_step_table.py --corpus all   # steps/
.venv/bin/python research/scripts/extract_windows.py --corpus tb2 --w 10 --stride 3
.venv/bin/python research/scripts/extract_windows.py --corpus nebius --w 10 --stride 3
```

Acceptance: byte-compare against `datasets/MANIFEST.json` hashes (modulo wall-clock
fields). Small fixtures (`smoke_tb2/`, `xscaffold/`) stay versioned with code because
tests and probes read them.
