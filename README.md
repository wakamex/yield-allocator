# Yield allocator

This package allocates a fixed budget across utilization-based lending markets.
It reads market state and rate curves from TOML, accounts for the rate impact of
each deposit, and returns the highest-income allocation.

Run the included case:

```sh
uv run --frozen yield-allocate examples/two_markets.toml
```

Get machine-readable output:

```sh
uv run --frozen yield-allocate examples/two_markets.toml --json
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
uv run --frozen python -m unittest discover -s tests -v
```

Run the deterministic stochastic benchmark through 10 markets:

```sh
uv run --frozen yield-benchmark --max-markets 10 --trials 5
```

The default `mixed` profile generates markets below the kink, above an
unreachable kink, and above a kink reachable within the budget. The
`all-crossing` profile is an exponential-scaling stress test:

```sh
uv run --frozen yield-benchmark \
  --profile all-crossing --max-markets 10 --trials 3
```

The seed defaults to `20260826` and can be changed with `--seed`. Market inputs
are identical for repeated runs with the same seed, market count, trial, and
profile. Runtime still varies with host load.

Select a solver preset or override individual features:

```sh
uv run --frozen yield-allocate examples/two_markets.toml --preset a5

uv run --frozen yield-allocate examples/two_markets.toml \
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
uv run --frozen yield-allocate examples/two_markets.toml \
  --preset recommended
```

Run the fixed 20-market step-forward ablation:

```sh
uv run --frozen yield-ablate --trials 3
```

Attribute the total speedup across features using every dependency-valid feature
order:

```sh
uv run --frozen yield-ablate --contributions --trials 3
```

Progress is written to stderr as `[completed/total] configuration`. JSON output
on stdout remains machine-readable.

The reported geo-mean factor is the geometric mean of a feature's X-times
speedup across valid addition orders. The feature factors multiply to the total
speedup. A current ten-feature contribution run covers 288 configurations and
120,960 valid orders. The benchmark report records the earlier eight-feature
run.
