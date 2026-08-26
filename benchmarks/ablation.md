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
| 0 | A0 | baseline | yes | 20.711849 | 1.00x | 1,048,576 | 1,660 | 166,000 | 21,967,120 | 25,673,588 | yes |
| 1 | A0 | adaptive bisection | yes | 6.694979 | 3.09x | 1,048,576 | 1,660 | 64,667 | 5,272,868 | 6,673,834 | no |
| 1 | A0 | cached segment algebra | yes | 11.551759 | 1.79x | 1,048,576 | 1,660 | 166,000 | 21,967,120 | 25,673,588 | no |
| 1 | A0 | closed-form inversion | yes | 4.682656 | 4.42x | 1,048,576 | 1,660 | 166,000 | 0 | 3,706,468 | yes |
| 1 | A0 | Newton price search | yes | 7.556211 | 2.74x | 1,048,576 | 1,660 | 49,575 | 6,987,520 | 8,175,279 | no |
| 1 | A0 | recursive enumeration | yes | 19.538432 | 1.06x | 9,935 | 1,660 | 166,000 | 21,967,120 | 25,673,588 | no |
| 2 | closed form | adaptive bisection | yes | 2.663867 | 1.76x | 1,048,576 | 1,660 | 64,687 | 0 | 1,512,787 | no |
| 2 | closed form | cached segment algebra | yes | 2.465823 | 1.90x | 1,048,576 | 1,660 | 166,000 | 0 | 3,706,468 | yes |
| 2 | closed form | Newton price search | yes | 2.608519 | 1.80x | 1,048,576 | 1,660 | 49,662 | 0 | 1,189,778 | no |
| 2 | closed form | recursive enumeration | yes | 3.625453 | 1.29x | 9,935 | 1,660 | 166,000 | 0 | 3,706,468 | no |
| 3 | closed form + cache | adaptive bisection | yes | 1.743550 | 1.41x | 1,048,576 | 1,660 | 64,674 | 0 | 1,512,488 | no |
| 3 | closed form + cache | Newton price search | yes | 1.811335 | 1.36x | 1,048,576 | 1,660 | 49,740 | 0 | 1,191,363 | no |
| 3 | closed form + cache | recursive enumeration | yes | 1.595580 | 1.55x | 9,935 | 1,660 | 166,000 | 0 | 3,706,468 | yes |
| 4 | previous winner | adaptive bisection | yes | 0.693875 | 2.30x | 9,935 | 1,660 | 64,674 | 0 | 1,512,488 | no |
| 4 | previous winner | dual bounds | yes | 0.093968 | 16.98x | 67 | 2 | 3,650 | 0 | 120,199 | yes |
| 4 | previous winner | Newton price search | yes | 0.763651 | 2.09x | 9,935 | 1,660 | 49,740 | 0 | 1,191,363 | no |
| 5 | previous winner + dual bounds | adaptive bisection | yes | 0.092523 | 1.02x | 67 | 2 | 3,536 | 0 | 117,573 | no |
| 5 | previous winner + dual bounds | best-bound traversal | yes | 0.055678 | 1.69x | 38 | 1 | 2,149 | 0 | 73,378 | no |
| 5 | previous winner + dual bounds | heuristic incumbent | yes | 0.027471 | 3.42x | 15 | 1 | 963 | 0 | 38,779 | yes |
| 5 | previous winner + dual bounds | Newton price search | yes | 0.082629 | 1.14x | 67 | 2 | 3,284 | 0 | 110,384 | no |
| 6 | previous winner + heuristic | adaptive bisection | yes | 0.026646 | 1.03x | 15 | 1 | 908 | 0 | 37,569 | no |
| 6 | previous winner + heuristic | best-bound traversal | yes | 0.025852 | 1.06x | 7 | 1 | 963 | 0 | 38,779 | yes |
| 6 | previous winner + heuristic | Newton price search | yes | 0.025901 | 1.06x | 15 | 1 | 904 | 0 | 37,461 | no |
| 7 | previous winner + best bound | adaptive bisection | yes | 0.025668 | 1.01x | 7 | 1 | 908 | 0 | 37,569 | yes |
| 7 | previous winner + best bound | Newton price search | yes | 0.026319 | 0.98x | 7 | 1 | 904 | 0 | 37,461 | no |
| 8 | recommended | Newton price search | yes | 0.025727 | 1.00x | 7 | 1 | 904 | 0 | 37,461 | yes, forced completion |
| 9 | all exact features | heuristic only | observed yes | 0.002440 | 10.54x | 0 | 1 | 97 | 0 | 3,525 | no |

## Eight-feature exact configuration runs in 0.025668 seconds

The original step-forward configuration enables:

- adaptive bisection
- cached segment algebra
- closed-form inversion
- recursive enumeration
- dual bounds
- heuristic initialization
- best-bound traversal

It leaves Newton price search disabled. Its 0.025668 second median is 806.91
times faster than A0. Closed-form inversion wins the first round at 4.42x and
eliminates all 21,967,120 inner iterations.

Cached segment algebra gives a 1.79x speedup by itself and a 1.90x speedup after
closed-form inversion. In the contribution run, adding it to the previous
recommended configuration reduces the median from 0.058937 to 0.025312 seconds,
a 2.33x speedup with identical search work.

Dual bounds reduce the search from 9,935 nodes and 1,660 fixed solves to 67
nodes and two fixed solves. Heuristic initialization then cuts the search to 15
nodes, and best-bound traversal cuts it to seven.

Adding Newton price search to the final configuration takes 0.025727 seconds,
0.23 percent slower than the recommended configuration. It remains available
as a toggle but is disabled in the preset.

The heuristic-only run happened to match the exact objective on this input and
completed in 0.002440 seconds. It does not provide an exactness certificate, so
it is not promoted as an exact solver.

## Reduced-cost fixing lowers the hot path to 0.006802 seconds

A targeted follow-up tested the two dual-guided branch features on the
eight-feature configuration. It used 51 interleaved timed repetitions of the
same fixed 20-market solve. Garbage collection and input loading were excluded.

| Reduced-cost fixing | Ambiguity branching | Exact | Median s | Speedup | Nodes | Dual solves | Marginal evaluations | Branches fixed |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| off | off | yes | 0.027510 | 1.00x | 7 | 16 | 37,569 | 0 |
| on | off | yes | 0.006802 | 4.04x | 1 | 4 | 8,791 | 19 |
| off | on | yes | 0.007737 | 3.56x | 1 | 4 | 11,043 | 0 |
| on | on | yes | 0.006800 | 4.05x | 1 | 4 | 8,791 | 19 |

Reduced-cost fixing is selected for the recommended preset. Ambiguity branching
has no measurable marginal effect after fixing: it produces identical search
work and changes the median by 0.02 percent.

The selected feature was also tested on the same 20 deterministic 100-market
all-crossing seeds used for the scaling check, with three timed repetitions per
case.

| Configuration | Median s | p95 s | Max s | Maximum nodes |
| --- | ---: | ---: | ---: | ---: |
| Previous recommended | 0.017491 | 1.191071 | 1.205860 | 101 |
| With ambiguity branching | 0.017479 | 1.063409 | 1.212035 | 101 |
| With reduced-cost fixing | 0.017628 | 0.027900 | 0.028366 | 2 |

Ambiguity branching leaves the median unchanged and improves p95 by 1.12x, but
it does not reduce the maximum search size. Reduced-cost fixing also leaves the
median essentially unchanged, improves p95 by 42.69x, and reduces the maximum
search from 101 nodes to two. Every objective matched.

The full ten-feature contribution benchmark was not rerun for this targeted
follow-up.

## Eight-feature geo-mean factors multiply to a 797.18x speedup

The earlier dependency-aware Shapley calculation benchmarks all 96 valid exact
feature combinations and averages each feature's X-times speedup across the
3,360 valid addition orders. This is a geometric mean. The attributed factors
multiply to the total measured speedup.

| Feature | Geo-mean attributed speedup | Share of log speedup |
| --- | ---: | ---: |
| Adaptive bisection | 1.4628x | 5.69% |
| Closed-form inversion | 4.0589x | 20.97% |
| Newton price search | 1.3312x | 4.28% |
| Cached segment algebra | 2.2382x | 12.06% |
| Recursive enumeration | 1.1786x | 2.46% |
| Dual bounds | 13.1107x | 38.52% |
| Heuristic incumbent | 2.1681x | 11.58% |
| Best-bound traversal | 1.3450x | 4.44% |

The factors multiply to 797.1803x, the three-trial median speedup from A0 to
the configuration with all eight exact features. The eight-feature
configuration excluding Newton price search is 818.95x faster than A0 in the
same contribution run.

Newton price search has a positive order-averaged factor because it helps when
other price-search reductions are absent. The final configuration test still
finds no benefit from adding it to the recommended feature set.
