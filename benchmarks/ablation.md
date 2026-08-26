# Twenty-market step-forward solver ablation

The benchmark uses `all_crossing_20.toml`. Timings cover only the solve call.
Every exact configuration must reproduce the A0 annualized income and satisfy
the $10 million allocation constraint.

Input SHA-256: `e3a160d915259fa019d9954cf0f54c0a32600e43250b9849c6f590ba44e8c65a`

Each round holds the current winner fixed and tests every remaining eligible
feature one at a time. The fastest configuration that reproduces the exact A0
objective becomes the base for the next round. A candidate is eligible only
after its required search machinery is enabled.

| Round | Base | Candidate feature | Eligible | Exact | Median s | Incremental speedup | Nodes | Fixed solves | Marginal evaluations | Bound prunes | Objective gap | Selected |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | A0 | baseline | yes | yes | pending | 1.00x | pending | pending | pending | 0 | 0 | yes |
