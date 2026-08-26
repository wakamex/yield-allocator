# Yield allocator

This package allocates a fixed budget across utilization-based lending markets.
It reads market state and rate curves from TOML, accounts for the rate impact of
each deposit, and returns the highest-income allocation.

Run the included case:

```sh
uv --no-config run --locked yield-allocate examples/two_markets.toml
```

Get machine-readable output:

```sh
uv --no-config run --locked yield-allocate examples/two_markets.toml --json
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
uv --no-config run --locked python -m unittest discover -s tests -v
```

Run the deterministic stochastic benchmark through 10 markets:

```sh
uv --no-config run --locked yield-benchmark --max-markets 10 --trials 5
```

The default `mixed` profile generates markets below the kink, above an
unreachable kink, and above a kink reachable within the budget. The
`all-crossing` profile is an exponential-scaling stress test:

```sh
uv --no-config run --locked yield-benchmark \
  --profile all-crossing --max-markets 10 --trials 3
```

The seed defaults to `20260826` and can be changed with `--seed`. Market inputs
are identical for repeated runs with the same seed, market count, trial, and
profile. Runtime still varies with host load.

Select a solver preset or override individual features:

```sh
uv --no-config run --locked yield-allocate examples/two_markets.toml --preset a5

uv --no-config run --locked yield-allocate examples/two_markets.toml \
  --adaptive-bisection \
  --recursive-enumeration
```

Every feature flag also has a `--no-...` form, so a preset can be modified
without defining another preset.

The `recommended` preset is the fastest exact configuration selected by the
fixed 20-market step-forward ablation:

```sh
uv --no-config run --locked yield-allocate examples/two_markets.toml \
  --preset recommended
```

Run the fixed 20-market step-forward ablation:

```sh
uv --no-config run --locked yield-ablate --trials 3
```
