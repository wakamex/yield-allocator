# Yield allocator

This package solves the static lending allocation defined in
[`README.md`](README.md). It reads a TOML problem,
enumerates feasible utilization-curve regions, solves each region by equalizing
marginal income, and returns the highest-income allocation.

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
budget = 10_000_000

[[markets]]
name = "Market Alpha"
supply = 850_000_000
borrow = 710_000_000
kink = 0.92
slope_1 = 0.04
slope_2 = 0.10
base_rate = 0.0
reserve_factor = 0.0
# max_allocation = 5_000_000
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
