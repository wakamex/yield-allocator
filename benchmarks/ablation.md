# Twenty-market step-forward solver ablation

The benchmark uses `all_crossing_20.toml`. Timings cover only the solve call.
Every exact configuration must reproduce the A0 annualized income and satisfy
the $10 million allocation constraint.

Input SHA-256: `e3a160d915259fa019d9954cf0f54c0a32600e43250b9849c6f590ba44e8c65a`

Environment and protocol:

- Python 3.14.7
- three timed repetitions per configuration
- median wall-clock solve time
- input loading and generation excluded
- garbage collection disabled during each solve
- exact annualized income: $629,524.8846603511
- exact allocation SHA-256: `59af0577389269dee52b498ce631237a38356833ae0b3c06406a7d93384c6ca3`

Each round holds the current winner fixed and tests every remaining eligible
feature one at a time. The fastest configuration that reproduces the exact A0
objective becomes the base for the next round. A candidate is eligible only
after its required search machinery is enabled.

| Round | Base | Candidate feature | Eligible | Exact | Median s | Incremental speedup | Nodes | Fixed solves | Marginal evaluations | Bound prunes | Objective gap | Selected |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | A0 | baseline | yes | yes | 19.223646 | 1.00x | 1,048,576 | 1,660 | 25,673,588 | 0 | 0% | yes |
| 1 | A0 | adaptive bisection | yes | yes | 6.185751 | 3.11x | 1,048,576 | 1,660 | 6,673,834 | 0 | 0% | yes |
| 1 | A0 | recursive enumeration | yes | yes | 18.104462 | 1.06x | 9,935 | 1,660 | 25,673,588 | 0 | 0% | no |
| 2 | adaptive bisection | recursive enumeration | yes | yes | 5.177422 | 1.19x | 9,935 | 1,660 | 6,673,834 | 0 | 0% | yes |
| 3 | adaptive bisection + recursive enumeration | dual bounds | yes | yes | 0.458180 | 11.30x | 67 | 2 | 531,413 | 29 | 0% | yes |
| 4 | previous winner | best-bound traversal | yes | yes | 0.254871 | 1.80x | 38 | 1 | 298,269 | 17 | 0% | yes |
| 4 | previous winner | heuristic incumbent | yes | yes | 0.270652 | 1.69x | 41 | 2 | 315,376 | 17 | 0% | no |
| 5 | previous winner + best-bound | heuristic incumbent | yes | yes | 0.268717 | 0.95x | 27 | 2 | 315,376 | 17 | 0% | yes, forced completion |
| 6 | all exact features | heuristic only | yes | no | 0.014212 | 18.91x | 0 | 1 | 17,107 | 0 | 7.965784% | no |

## Best exact configuration excludes heuristic initialization

The fastest exact configuration enables:

- adaptive bisection
- recursive enumeration
- dual bounds
- best-bound traversal

It leaves heuristic initialization disabled. Its 0.254871 second median is
75.42 times faster than A0. Adding the heuristic incumbent reduced the number
of visited nodes from 38 to 27, but its extra root relaxation and fixed-region
solve increased total time by 5.43 percent.

A conventional step-forward procedure that stops when no remaining feature
improves runtime would stop after round 4. Round 5 is included because the
requested experiment continued until every exact feature had been toggled.

H1 completed in 0.014212 seconds but returned $579,378.2934155287, which is
7.965784 percent below the exact objective. That gap is too large to use H1 as
an exact-solver replacement for this case.
