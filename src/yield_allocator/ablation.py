from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .cli import load_problem
from .solver import Solution, SolveStats, SolverConfig, solve


EXACT_FEATURES = (
    "adaptive_bisection",
    "recursive_enumeration",
    "dual_bounds",
    "heuristic_incumbent",
    "best_bound",
)
DEPENDENCIES = {
    "adaptive_bisection": frozenset(),
    "recursive_enumeration": frozenset(),
    "dual_bounds": frozenset({"recursive_enumeration"}),
    "heuristic_incumbent": frozenset({"dual_bounds"}),
    "best_bound": frozenset({"dual_bounds"}),
}


@dataclass(frozen=True)
class Measurement:
    round: int
    base: str
    candidate: str
    features: tuple[str, ...]
    selected: bool
    exact: bool
    median_seconds: float
    incremental_speedup: float
    annual_income: float
    objective_gap: float
    stats: dict[str, int]


def config_for(features: set[str], *, heuristic_only: bool = False) -> SolverConfig:
    return SolverConfig(
        adaptive_bisection="adaptive_bisection" in features,
        recursive_enumeration="recursive_enumeration" in features,
        dual_bounds="dual_bounds" in features,
        heuristic_incumbent="heuristic_incumbent" in features,
        best_bound="best_bound" in features,
        heuristic_only=heuristic_only,
    )


def _measure(
    markets: list,
    budget: float,
    config: SolverConfig,
    trials: int,
) -> tuple[float, Solution, SolveStats]:
    durations = []
    solution = None
    final_stats = None
    for _ in range(trials):
        stats = SolveStats()
        gc.collect()
        was_enabled = gc.isenabled()
        gc.disable()
        started = time.perf_counter_ns()
        try:
            result = solve(markets, budget, config=config, stats=stats)
        finally:
            duration = time.perf_counter_ns() - started
            if was_enabled:
                gc.enable()
        if not abs(sum(result.allocations) - budget) <= max(1e-7, budget * 1e-12):
            raise RuntimeError("solver returned an invalid allocation")
        durations.append(duration / 1_000_000_000)
        solution = result
        final_stats = stats
    assert solution is not None and final_stats is not None
    return statistics.median(durations), solution, final_stats


def run_step_forward(
    path: Path,
    *,
    trials: int = 3,
) -> list[Measurement]:
    if trials < 1:
        raise ValueError("trials must be positive")
    budget, markets = load_problem(path)

    baseline_time, baseline_solution, baseline_stats = _measure(
        markets, budget, SolverConfig(), trials
    )
    optimum = baseline_solution.annual_income
    measurements = [
        Measurement(
            round=0,
            base="A0",
            candidate="baseline",
            features=(),
            selected=True,
            exact=True,
            median_seconds=baseline_time,
            incremental_speedup=1.0,
            annual_income=optimum,
            objective_gap=0.0,
            stats=asdict(baseline_stats),
        )
    ]

    selected: set[str] = set()
    remaining = set(EXACT_FEATURES)
    current_time = baseline_time
    round_number = 1

    while remaining:
        eligible = sorted(
            feature
            for feature in remaining
            if DEPENDENCIES[feature] <= selected
        )
        if not eligible:
            raise RuntimeError("no eligible step-forward feature remains")

        candidates = []
        for feature in eligible:
            features = selected | {feature}
            duration, solution, stats = _measure(
                markets,
                budget,
                config_for(features),
                trials,
            )
            gap = max(0.0, (optimum - solution.annual_income) / optimum)
            exact = abs(solution.annual_income - optimum) <= max(
                1e-6, abs(optimum) * 1e-10
            )
            candidates.append((feature, duration, solution, stats, gap, exact))

        exact_candidates = [candidate for candidate in candidates if candidate[5]]
        if not exact_candidates:
            raise RuntimeError(f"round {round_number} has no exact candidate")
        winner = min(exact_candidates, key=lambda candidate: candidate[1])[0]

        base_label = "+".join(sorted(selected)) or "A0"
        for feature, duration, solution, stats, gap, exact in candidates:
            measurements.append(
                Measurement(
                    round=round_number,
                    base=base_label,
                    candidate=feature,
                    features=tuple(sorted(selected | {feature})),
                    selected=feature == winner,
                    exact=exact,
                    median_seconds=duration,
                    incremental_speedup=current_time / duration,
                    annual_income=solution.annual_income,
                    objective_gap=gap,
                    stats=asdict(stats),
                )
            )

        winner_measurement = next(
            measurement
            for measurement in reversed(measurements)
            if measurement.round == round_number and measurement.selected
        )
        selected.add(winner)
        remaining.remove(winner)
        current_time = winner_measurement.median_seconds
        round_number += 1

    duration, solution, stats = _measure(
        markets,
        budget,
        config_for(selected, heuristic_only=True),
        trials,
    )
    measurements.append(
        Measurement(
            round=round_number,
            base="+".join(sorted(selected)),
            candidate="heuristic_only",
            features=tuple(sorted((*selected, "heuristic_only"))),
            selected=False,
            exact=False,
            median_seconds=duration,
            incremental_speedup=current_time / duration,
            annual_income=solution.annual_income,
            objective_gap=max(0.0, (optimum - solution.annual_income) / optimum),
            stats=asdict(stats),
        )
    )
    return measurements


def format_results(measurements: list[Measurement]) -> str:
    lines = [
        "| Round | Base | Candidate | Exact | Median s | Speedup | Nodes | Fixed solves | Marginal evaluations | Bound prunes | Gap | Selected |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in measurements:
        nodes = result.stats["nodes_visited"] or result.stats["combinations_visited"]
        lines.append(
            f"| {result.round} | {result.base} | {result.candidate} "
            f"| {'yes' if result.exact else 'no'} | {result.median_seconds:.6f} "
            f"| {result.incremental_speedup:.2f}x | {nodes} "
            f"| {result.stats['fixed_region_solves']} "
            f"| {result.stats['marginal_evaluations']} "
            f"| {result.stats['bound_prunes']} | {result.objective_gap:.6%} "
            f"| {'yes' if result.selected else 'no'} |"
        )
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Run the step-forward solver feature ablation."
    )
    argument_parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("benchmarks/all_crossing_20.toml"),
    )
    argument_parser.add_argument("--trials", type=int, default=3)
    argument_parser.add_argument("--json", action="store_true")
    return argument_parser


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        measurements = run_step_forward(arguments.input, trials=arguments.trials)
    except (OSError, ValueError) as error:
        parser().error(str(error))

    if arguments.json:
        output: Any = [asdict(measurement) for measurement in measurements]
        print(json.dumps(output, indent=2))
    else:
        print(format_results(measurements))
    return 0
