from __future__ import annotations

import argparse
import gc
import json
import math
import random
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any

from .solver import Market, solve


@dataclass(frozen=True)
class BenchmarkRow:
    markets: int
    trials: int
    mean_crossing_markets: float
    mean_region_combinations: float
    median_ms: float
    p95_ms: float
    max_ms: float


def generate_markets(
    count: int,
    budget: float,
    seed: int,
    profile: str = "mixed",
) -> list[Market]:
    if count < 1:
        raise ValueError("market count must be positive")
    if budget <= 0:
        raise ValueError("budget must be positive")
    if profile not in {"mixed", "all-crossing"}:
        raise ValueError("profile must be mixed or all-crossing")

    rng = random.Random(seed)
    markets = []
    for index in range(count):
        supply = rng.uniform(500_000_000, 3_000_000_000)
        kink = rng.uniform(0.80, 0.95)
        slope_1 = rng.uniform(0.01, 0.08)
        slope_2 = rng.uniform(0.05, 0.40)
        base_rate = rng.uniform(0, 0.02)
        reserve_factor = rng.uniform(0, 0.25)

        if profile == "all-crossing" or rng.random() < 0.5:
            kink_allocation = rng.uniform(0.05 * budget, 0.95 * budget)
            borrow = kink * (supply + kink_allocation)
        elif rng.random() < 0.8:
            utilization = rng.uniform(0.45, 0.98 * kink)
            borrow = utilization * supply
        else:
            maximum_kink_allocation = supply * (1 / kink - 1)
            lower = 1.05 * budget
            upper = min(2 * budget, 0.95 * maximum_kink_allocation)
            if upper > lower:
                kink_allocation = rng.uniform(lower, upper)
                borrow = kink * (supply + kink_allocation)
            else:
                utilization = rng.uniform(0.45, 0.98 * kink)
                borrow = utilization * supply

        markets.append(
            Market(
                name=f"Market {index + 1}",
                supply=supply,
                borrow=borrow,
                kink=kink,
                slope_1=slope_1,
                slope_2=slope_2,
                base_rate=base_rate,
                reserve_factor=reserve_factor,
            )
        )
    return markets


def crossing_market_count(markets: list[Market], budget: float) -> int:
    return sum(0 < market.kink_allocation < budget for market in markets)


def run_benchmark(
    *,
    min_markets: int = 2,
    max_markets: int = 10,
    trials: int = 5,
    budget: float = 10_000_000,
    seed: int = 20260826,
    profile: str = "mixed",
) -> list[BenchmarkRow]:
    if not 1 <= min_markets <= max_markets:
        raise ValueError("market range must be positive and ordered")
    if trials < 1:
        raise ValueError("trials must be positive")

    warmup = generate_markets(min(2, min_markets), budget, seed - 1, profile)
    solve(warmup, budget)

    rows = []
    for market_count in range(min_markets, max_markets + 1):
        durations = []
        crossing_counts = []
        region_counts = []

        for trial in range(trials):
            case_seed = seed + market_count * 1_000_003 + trial * 97_409
            markets = generate_markets(market_count, budget, case_seed, profile)
            crossing = crossing_market_count(markets, budget)

            gc.collect()
            gc.disable()
            started = time.perf_counter_ns()
            try:
                solution = solve(markets, budget)
            finally:
                duration = time.perf_counter_ns() - started
                gc.enable()

            if not math.isclose(sum(solution.allocations), budget, rel_tol=1e-12):
                raise RuntimeError("benchmark solver returned an invalid allocation")
            durations.append(duration / 1_000_000)
            crossing_counts.append(crossing)
            region_counts.append(2**crossing)

        ordered = sorted(durations)
        p95_index = math.ceil(0.95 * len(ordered)) - 1
        rows.append(
            BenchmarkRow(
                markets=market_count,
                trials=trials,
                mean_crossing_markets=statistics.fmean(crossing_counts),
                mean_region_combinations=statistics.fmean(region_counts),
                median_ms=statistics.median(durations),
                p95_ms=ordered[p95_index],
                max_ms=max(durations),
            )
        )
    return rows


def format_results(rows: list[BenchmarkRow], configuration: dict[str, Any]) -> str:
    lines = [
        f"Profile: {configuration['profile']}",
        f"Seed: {configuration['seed']}",
        f"Budget: ${configuration['budget']:,.0f}",
        "",
        "| Markets | Trials | Mean crossing | Mean regions | Median ms | p95 ms | Max ms |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.markets} | {row.trials} | {row.mean_crossing_markets:.1f} "
            f"| {row.mean_region_combinations:.1f} | {row.median_ms:.3f} "
            f"| {row.p95_ms:.3f} | {row.max_ms:.3f} |"
        )
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Benchmark the yield allocator on deterministic random markets."
    )
    argument_parser.add_argument("--min-markets", type=int, default=2)
    argument_parser.add_argument("--max-markets", type=int, default=10)
    argument_parser.add_argument("--trials", type=int, default=5)
    argument_parser.add_argument("--budget", type=float, default=10_000_000)
    argument_parser.add_argument("--seed", type=int, default=20260826)
    argument_parser.add_argument(
        "--profile", choices=("mixed", "all-crossing"), default="mixed"
    )
    argument_parser.add_argument("--json", action="store_true")
    return argument_parser


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    configuration = {
        "min_markets": arguments.min_markets,
        "max_markets": arguments.max_markets,
        "trials": arguments.trials,
        "budget": arguments.budget,
        "seed": arguments.seed,
        "profile": arguments.profile,
    }
    try:
        rows = run_benchmark(**configuration)
    except ValueError as error:
        parser().error(str(error))

    if arguments.json:
        print(
            json.dumps(
                {"configuration": configuration, "results": [asdict(row) for row in rows]},
                indent=2,
            )
        )
    else:
        print(format_results(rows, configuration))
    return 0
