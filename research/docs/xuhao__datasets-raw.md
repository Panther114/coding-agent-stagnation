# datasets/raw — pristine upstream downloads (gitignored, never committed)

Re-fetch exactly what the study ran on:

```bash
.venv/bin/python research/scripts/download_data.py --only tb2     # 2 shards, ~221MB, 52,104 trials
.venv/bin/python research/scripts/download_data.py --only nebius  # 12 shards, ~1.11GB, 80,036 trajectories
```

Provenance: byte counts + URLs land in `download_manifest.json` here (gitignored; copy
values into `datasets/MANIFEST.json` when freezing). Known upstream quirk: TB2 ships
~4,952 intra-shard duplicate trial_names as UUID + empty-UUID pairs — the loader
dedupes by preferring the UUID-carrying twin (see `research/src/loaders.py`).
