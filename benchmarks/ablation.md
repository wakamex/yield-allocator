# Twenty-market solver ablation

The benchmark uses `all_crossing_20.toml`. Timings cover only the solve call.
Every exact configuration must reproduce the A0 annualized income and satisfy
the $10 million allocation constraint.

Input SHA-256: `e3a160d915259fa019d9954cf0f54c0a32600e43250b9849c6f590ba44e8c65a`

| Preset | Adaptive bisection | Recursive enumeration | Dual bounds | Heuristic incumbent | Best-bound | Heuristic only | Exact | Median s | Speedup | Nodes | Fixed solves | Marginal evaluations | Bound prunes | Objective gap |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A0 | no | no | no | no | no | no | yes | pending | 1.00x | pending | pending | pending | 0 | 0 |
| A1 | yes | no | no | no | no | no | yes | pending | pending | pending | pending | pending | 0 | 0 |
| A2 | yes | yes | no | no | no | no | yes | pending | pending | pending | pending | pending | 0 | 0 |
| A3 | yes | yes | yes | no | no | no | yes | pending | pending | pending | pending | pending | pending | 0 |
| A4 | yes | yes | yes | yes | no | no | yes | pending | pending | pending | pending | pending | pending | 0 |
| A5 | yes | yes | yes | yes | yes | no | yes | pending | pending | pending | pending | pending | pending | 0 |
| H1 | yes | yes | yes | yes | yes | yes | no | pending | pending | pending | pending | pending | pending | pending |
