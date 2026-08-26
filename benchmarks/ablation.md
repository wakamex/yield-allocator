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
- exact annualized income: $629,524.8846603513

Each round holds the current winner fixed and tests every remaining eligible
feature one at a time. The fastest exact candidate becomes the base for the
next round. A candidate is eligible only after its required search machinery
is enabled.

| Round | Base | Candidate | Exact | Median s | Incremental speedup | Nodes | Fixed solves | Outer iterations | Inner iterations | Marginal evaluations | Selected |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | A0 | baseline | yes | 19.376476 | 1.00x | 1,048,576 | 1,660 | 166,000 | 21,967,120 | 25,673,588 | yes |
| 1 | A0 | adaptive bisection | yes | 6.311355 | 3.07x | 1,048,576 | 1,660 | 64,667 | 5,272,868 | 6,673,834 | no |
| 1 | A0 | closed-form inversion | yes | 4.497027 | 4.31x | 1,048,576 | 1,660 | 166,000 | 0 | 3,706,468 | yes |
| 1 | A0 | Newton price search | yes | 7.076868 | 2.74x | 1,048,576 | 1,660 | 49,575 | 6,987,520 | 8,175,279 | no |
| 1 | A0 | recursive enumeration | yes | 18.283750 | 1.06x | 9,935 | 1,660 | 166,000 | 21,967,120 | 25,673,588 | no |
| 2 | closed form | adaptive bisection | yes | 2.469324 | 1.82x | 1,048,576 | 1,660 | 64,687 | 0 | 1,512,787 | yes |
| 2 | closed form | Newton price search | yes | 2.518239 | 1.79x | 1,048,576 | 1,660 | 49,662 | 0 | 1,189,778 | no |
| 2 | closed form | recursive enumeration | yes | 3.506381 | 1.28x | 9,935 | 1,660 | 166,000 | 0 | 3,706,468 | no |
| 3 | closed form + adaptive | Newton price search | yes | 2.497592 | 0.99x | 1,048,576 | 1,660 | 49,662 | 0 | 1,189,778 | no |
| 3 | closed form + adaptive | recursive enumeration | yes | 1.505581 | 1.64x | 9,935 | 1,660 | 64,687 | 0 | 1,512,787 | yes |
| 4 | previous winner | dual bounds | yes | 0.178181 | 8.45x | 67 | 2 | 3,538 | 0 | 117,628 | yes |
| 4 | previous winner | Newton price search | yes | 1.410784 | 1.07x | 9,935 | 1,660 | 49,662 | 0 | 1,189,778 | no |
| 5 | previous winner + dual bounds | best-bound traversal | yes | 0.106141 | 1.68x | 38 | 1 | 2,095 | 0 | 72,198 | no |
| 5 | previous winner + dual bounds | heuristic incumbent | yes | 0.053294 | 3.34x | 15 | 1 | 908 | 0 | 37,569 | yes |
| 5 | previous winner + dual bounds | Newton price search | yes | 0.169934 | 1.05x | 67 | 2 | 3,323 | 0 | 111,652 | no |
| 6 | previous winner + heuristic | best-bound traversal | yes | 0.049825 | 1.07x | 7 | 1 | 908 | 0 | 37,569 | yes |
| 6 | previous winner + heuristic | Newton price search | yes | 0.100419 | 0.53x | 41 | 2 | 2,069 | 0 | 72,420 | no |
| 7 | recommended | Newton price search | yes | 0.100516 | 0.50x | 27 | 2 | 2,069 | 0 | 72,420 | yes, forced completion |
| 8 | all exact features | heuristic only | no | 0.004287 | 23.45x | 0 | 1 | 82 | 0 | 3,243 | no |

## Recommended exact configuration runs in 0.049825 seconds

The fastest step-forward configuration enables:

- adaptive bisection
- closed-form inversion
- recursive enumeration
- dual bounds
- heuristic initialization
- best-bound traversal

It leaves Newton price search disabled. Its 0.049825 second median is 388.89
times faster than A0. Closed-form inversion wins the first round at 4.31x and
eliminates all 21,967,120 inner iterations. It evaluates 274,589 cubic roots
with zero bisection fallbacks.

Heuristic initialization reduces the bounded search from 67 nodes to 15 and
cuts runtime from 0.178181 to 0.053294 seconds. Best-bound traversal then
reduces the search to seven nodes and reaches 0.049825 seconds.

Adding Newton price search to that configuration increases runtime to 0.100516
seconds. The dual relaxation changes selected segments as price moves, so only
268 Newton proposals are accepted while 1,760 fall back to bisection. Round 7
is included only to complete every toggle and is not used for the recommended
preset.

H1 completes in 0.004287 seconds but returns $579,378.2934155285, which is
7.965784 percent below the exact objective.

## Geo-mean feature factors multiply to a 178.38x full-feature speedup

The dependency-aware Shapley calculation benchmarks all 48 valid exact feature
combinations and averages each feature's X-times speedup across the 420 valid
addition orders. This is a geometric mean. The attributed factors multiply to
the total measured speedup.

| Feature | Geo-mean attributed speedup | Share of log speedup |
| --- | ---: | ---: |
| Adaptive bisection | 1.4413x | 7.05% |
| Closed-form inversion | 3.2502x | 22.74% |
| Newton price search | 1.1609x | 2.88% |
| Recursive enumeration | 1.1717x | 3.06% |
| Dual bounds | 14.1092x | 51.06% |
| Heuristic incumbent | 1.5227x | 8.11% |
| Best-bound traversal | 1.3030x | 5.11% |

The factors multiply to 178.3765x, the three-trial median speedup from A0 to
the configuration with all seven exact features.

Newton price search has a positive order-averaged factor because it helps when
other price-search reductions are absent. It remains disabled in the
recommended preset because it causes a 101.74 percent regression when added to
that specific configuration. Order-averaged attribution does not replace the
final configuration-selection test.
