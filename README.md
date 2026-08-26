# Yield allocator

This package allocates a fixed budget across utilization-based lending markets.
It reads market state and rate curves from TOML, accounts for the rate impact of
each deposit, and returns the highest-income allocation.

## Current observed scaling stays near-linear; previous tails are quadratic

The benchmarks observed near-linear scaling across the current distribution.
The previous configuration had a linear median but a quadratic chain-like
sample maximum. Neither configuration exposed an exponential tree in the
measured cases.

The 200-seed all-crossing benchmark from 400 through 750 markets produced:

| Distribution statistic | Current | Previous |
| --- | ---: | ---: |
| Median exponent | 0.949 | 0.954 |
| p95 time range | 0.096s to 0.164s | 3.588s to 15.323s |
| Sample-maximum exponent | 0.898 | 1.939 |
| Maximum nodes visited | 6 | 751 |

The previous sample maximum visited about one node per market, and every node
scanned all markets, producing approximately quadratic time. Reduced-cost
fixing kept the current sample maximum to six nodes. This changes the observed
tail. The exact search still has an unobserved theoretical worst case with up
to `2^k` segment combinations for `k` ambiguous markets. Reduced-cost fixing
has not been proven to remove that worst case, but the current benchmarks do
not show it.

At 1,000 through 10,000 markets, current p95 runtime is effectively linear with
exponent 1.005 under fixed budget and 1.007 under proportional budget. See the
[benchmark report](benchmarks/ablation.md) and saved
[distribution analysis](benchmarks/results/p95-scaling-200-seed-analysis.json).

Run the included case:

```sh
uv run --locked yield-allocate examples/two_markets.toml
```

Get machine-readable output:

```sh
uv run --locked yield-allocate examples/two_markets.toml --json
```

The input has one budget and one table per market:

```toml
budget = 7_500_000

[[markets]]
name = "Market Alpha"
supply = 850_000_000
borrow = 710_000_000
kink = 0.87
slope_1 = 0.035
slope_2 = 0.18
base_rate = 0.005
reserve_factor = 0.10
# max_allocation = 4_000_000
```

`base_rate` and `reserve_factor` default to zero. `max_allocation` is optional.
Rates use decimal APR values.

Run the tests:

```sh
uv run --locked python -m unittest discover -s tests -v
```

Run the deterministic stochastic benchmark through 10 markets:

```sh
uv run --locked yield-benchmark --max-markets 10 --trials 5
```

The default `mixed` profile generates markets below the kink, above an
unreachable kink, and above a kink reachable within the budget. The
`all-crossing` profile is a branching stress test:

```sh
uv run --locked yield-benchmark \
  --profile all-crossing --max-markets 10 --trials 3
```

The seed defaults to `20260826` and can be changed with `--seed`. Market inputs
are identical for repeated runs with the same seed, market count, trial, and
profile. Runtime still varies with host load.

Save every stochastic scaling run as JSONL, then bootstrap the p95 exponent
from the saved measurements:

```sh
uv run --locked yield-scaling run benchmarks/results/p95-scaling.jsonl \
  --sizes 400 500 600 750 --cases 200

uv run --locked yield-scaling analyze benchmarks/results/p95-scaling.jsonl \
  --bootstraps 50000 \
  --output benchmarks/results/p95-scaling-analysis.json
```

Pass `--sizes 1000 3000 10000` to the analyze command to fit a local exponent
without rerunning measurements.

The run command records the seed, market count, configuration, elapsed time,
objective, solver counters, positive allocations, interior-critical
allocations, kink allocations, and capped allocations for every case. It writes
each record as soon as the solve finishes so partial results survive an
interrupted long run.

The committed 200-seed [run-level measurements](benchmarks/results/p95-scaling-200-seed.jsonl)
and [bootstrap analysis](benchmarks/results/p95-scaling-200-seed-analysis.json)
can be reanalyzed without rerunning the solver.

The committed 200-seed [market-growth measurements](benchmarks/results/market-growth-200-seed.jsonl)
and [growth analysis](benchmarks/results/market-growth-200-seed-analysis.json)
cover 100 through 10,000 markets.

Scale budget with market count by setting a per-market amount. This overrides
the fixed `--budget` value:

```sh
uv run --locked yield-scaling run benchmarks/results/proportional.jsonl \
  --sizes 100 200 400 750 1000 3000 10000 \
  --cases 200 \
  --configurations current \
  --budget-per-market 100000
```

The committed [proportional-budget measurements](benchmarks/results/market-growth-proportional-budget-200-seed.jsonl)
and [analysis](benchmarks/results/market-growth-proportional-budget-200-seed-analysis.json)
use $100,000 per market.

Select a solver preset or override individual features:

```sh
uv run --locked yield-allocate examples/two_markets.toml --preset a5

uv run --locked yield-allocate examples/two_markets.toml \
  --adaptive-bisection \
  --recursive-enumeration
```

Every feature flag also has a `--no-...` form, so a preset can be modified
without defining another preset.

`--closed-form-inversion` replaces the per-market inner bisection with a cached
cubic inverse. `--newton-price-search` applies safeguarded Newton updates to the
common portfolio price and falls back to a bracket midpoint when needed.
`--cached-segment-algebra` precomputes fixed coefficients and endpoint
marginals used in the hot loops. `--dual-reduced-cost-fixing` removes a branch
when its parent dual bound proves that it cannot beat the incumbent. It computes
the branch values only after the ordinary bound fails to prune the node.
`--dual-ambiguity-branching` branches first on the market whose segment values
are closest at the dual price.

The `recommended` preset is the fastest exact configuration selected by the
fixed 20-market [ablation](benchmarks/ablation.md) and hot-path follow-up. It
enables adaptive stopping, closed-form inversion, cached segment algebra,
recursive enumeration, dual bounds, reduced-cost fixing, heuristic
initialization, and best-bound traversal. Newton price search and ambiguity
branching remain available as overrides but are disabled in this preset.

```sh
uv run --locked yield-allocate examples/two_markets.toml \
  --preset recommended
```

Run the fixed 20-market step-forward ablation:

```sh
uv run --locked yield-ablate --trials 3
```

Attribute the total speedup across features using every dependency-valid feature
order:

```sh
uv run --locked yield-ablate --contributions --trials 3
```

Progress is written to stderr as `[completed/total] configuration`. JSON output
on stdout remains machine-readable.

The reported geo-mean factor is the geometric mean of a feature's X-times
speedup across valid addition orders. The feature factors multiply to the total
speedup. A current ten-feature contribution run covers 288 configurations and
120,960 valid orders. The benchmark report records the earlier eight-feature
run.
