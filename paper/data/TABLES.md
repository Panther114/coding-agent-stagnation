# Result tables (generated)

## The inversion, and its correction, on three disjoint shard sets

| set | shards | runs | on_target_self solved → failed | gold solved | gold failed | within-inst p | wrong-fix share |
|---|---|---|---|---|---|---|---|
| frozen | 0–3 | 26,679 | 0.594 → 0.670 | 0.477 | 0.407 | 7.0e-03 | 67.0% |
| held-out A | 4–7 | 26,680 | 0.593 → 0.677 | 0.492 | 0.421 | 3.6e-03 | 69.0% |
| held-out B | 8–11 | 26,676 | 0.614 → 0.686 | 0.512 | 0.415 | 2.8e-05 | 66.4% |

## Router: trained on shards 0–3, tested on unseen shards

| target | ours (cross-set mean) | min cell | position | AgentStop-style | gain over field |
|---|---|---|---|---|---|
| failure prediction | **0.7145** | 0.6752 | 0.6718 | 0.5589 | **+0.1556** |
| lost vs wrong-fix | **0.7324** | 0.6817 | 0.5993 | 0.596 | **+0.1364** |

## Cross-scaffold: the taxonomy does NOT transfer

| scaffold | footer | kept | revised | dead-end |
|---|---|---|---|---|
| SWE-agent (reference) | 0.958 | 0.157 | 0.652 | 0.191 |
| swegym | 0.0 | 0.734 | 0.229 | **0.037** |
| pi | 0.0 | 0.821 | 0.060 | **0.118** |
| smithmarines | 0.0 | 0.489 | 0.276 | **0.236** |
| thoughtworks | 0.0 | 0.706 | 0.115 | **0.179** |
