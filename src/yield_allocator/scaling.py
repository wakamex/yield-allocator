from __future__ import annotations

import argparse
import gc
import json
import math
import random
import statistics
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from .benchmark import generate_markets
from .solver import PRESETS, SolveStats, solve


CONFIGURATIONS = {
    "current": PRESETS["recommended"],
    "previous": replace(
        PRESETS["recommended"],
        dual_reduced_cost_fixing=False,
        dual_ambiguity_branching=False,
    ),
}


@dataclass(frozen=True)
class ScalingRun:
    configuration: str
    markets: int
    case: int
    seed: int
    seconds: float
    annual_income: float
    stats: dict[str, int]
    source: str = "measured"


def _p95(values: Iterable[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("p95 requires at least one value")
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _exponent(sizes: tuple[int, ...], values: list[float]) -> float:
    if len(sizes) < 2:
        raise ValueError("an exponent requires at least two market sizes")
    xs = [math.log(size) for size in sizes]
    ys = [math.log(value) for value in values]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    return sum(
        (x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)
    ) / sum((x - mean_x) ** 2 for x in xs)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return (
        ordered[lower] * (upper - position)
        + ordered[upper] * (position - lower)
    )


def measure(
    output: Path,
    *,
    sizes: tuple[int, ...],
    cases: int,
    configurations: tuple[str, ...],
    budget: float,
    seed: int,
    profile: str,
    overwrite: bool = False,
) -> None:
    if cases < 1:
        raise ValueError("cases must be positive")
    if len(sizes) < 1 or any(size < 1 for size in sizes):
        raise ValueError("market sizes must be positive")
    if len(set(sizes)) != len(sizes):
        raise ValueError("market sizes must be unique")

    mode = "w" if overwrite else "x"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open(mode, encoding="utf-8") as stream:
        metadata = {
            "type": "metadata",
            "schema": 1,
            "budget": budget,
            "base_seed": seed,
            "profile": profile,
            "sizes": sizes,
            "cases": cases,
            "configurations": configurations,
        }
        stream.write(json.dumps(metadata, separators=(",", ":")) + "\n")
        stream.flush()

        warmup = generate_markets(min(sizes), budget, seed - 1, profile)
        for name in configurations:
            solve(warmup, budget, config=CONFIGURATIONS[name])

        completed = 0
        total = len(sizes) * cases * len(configurations)
        progress_interval = max(1, total // 100)
        for size in sizes:
            for case in range(cases):
                case_seed = seed + size * 1_000_003 + case * 97_409
                markets = generate_markets(size, budget, case_seed, profile)
                order = (
                    configurations
                    if case % 2 == 0
                    else tuple(reversed(configurations))
                )
                incomes = []
                for name in order:
                    stats = SolveStats()
                    gc.collect()
                    was_enabled = gc.isenabled()
                    gc.disable()
                    started = time.perf_counter_ns()
                    try:
                        solution = solve(
                            markets,
                            budget,
                            config=CONFIGURATIONS[name],
                            stats=stats,
                        )
                    finally:
                        elapsed = (time.perf_counter_ns() - started) / 1_000_000_000
                        if was_enabled:
                            gc.enable()
                    run = ScalingRun(
                        configuration=name,
                        markets=size,
                        case=case,
                        seed=case_seed,
                        seconds=elapsed,
                        annual_income=solution.annual_income,
                        stats=asdict(stats),
                    )
                    stream.write(
                        json.dumps(
                            {"type": "run", **asdict(run)},
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    stream.flush()
                    incomes.append(solution.annual_income)
                    completed += 1
                    if completed % progress_interval == 0 or completed == total:
                        print(
                            f"[{completed}/{total}] {name} {size} markets case {case}",
                            file=sys.stderr,
                        )
                if max(incomes) - min(incomes) > max(1e-6, abs(incomes[0]) * 1e-10):
                    raise RuntimeError(
                        f"objective mismatch for {size} markets case {case}"
                    )


def load_runs(path: Path) -> tuple[dict[str, Any], list[ScalingRun]]:
    with path.open(encoding="utf-8") as stream:
        lines = [json.loads(line) for line in stream if line.strip()]
    if not lines or lines[0].get("type") != "metadata":
        raise ValueError("first JSONL record must contain benchmark metadata")
    metadata = lines[0]
    runs = [
        ScalingRun(
            configuration=item["configuration"],
            markets=item["markets"],
            case=item["case"],
            seed=item["seed"],
            seconds=item["seconds"],
            annual_income=item["annual_income"],
            stats=item["stats"],
            source=item.get("source", "measured"),
        )
        for item in lines[1:]
        if item.get("type") == "run"
    ]
    return metadata, runs


def analyze_runs(
    runs: list[ScalingRun],
    *,
    bootstraps: int = 20_000,
    seed: int = 260826,
) -> dict[str, Any]:
    if bootstraps < 1:
        raise ValueError("bootstraps must be positive")
    if not runs:
        raise ValueError("analysis requires at least one run")
    configurations = tuple(sorted({run.configuration for run in runs}))
    sizes = tuple(sorted({run.markets for run in runs}))
    grouped = {
        configuration: {
            size: {
                run.case: run.seconds
                for run in runs
                if run.configuration == configuration and run.markets == size
            }
            for size in sizes
        }
        for configuration in configurations
    }
    cases_by_size = {
        size: tuple(sorted(grouped[configurations[0]][size])) for size in sizes
    }
    for configuration in configurations:
        for size in sizes:
            if tuple(sorted(grouped[configuration][size])) != cases_by_size[size]:
                raise ValueError(
                    f"incomplete case matrix for {configuration} at {size} markets"
                )

    p95_by_configuration = {
        configuration: [
            _p95(grouped[configuration][size].values()) for size in sizes
        ]
        for configuration in configurations
    }
    point_exponents = {
        configuration: _exponent(sizes, values)
        for configuration, values in p95_by_configuration.items()
    }
    bootstrap_exponents = {configuration: [] for configuration in configurations}
    rng = random.Random(seed)
    for _ in range(bootstraps):
        points = {configuration: [] for configuration in configurations}
        for size in sizes:
            cases = cases_by_size[size]
            sampled = [cases[rng.randrange(len(cases))] for _ in cases]
            for configuration in configurations:
                points[configuration].append(
                    _p95(grouped[configuration][size][case] for case in sampled)
                )
        for configuration in configurations:
            bootstrap_exponents[configuration].append(
                _exponent(sizes, points[configuration])
            )

    return {
        "sizes": sizes,
        "configurations": {
            configuration: {
                "p95_seconds": dict(
                    zip(sizes, p95_by_configuration[configuration], strict=True)
                ),
                "p95_exponent": point_exponents[configuration],
                "bootstrap_median_exponent": statistics.median(
                    bootstrap_exponents[configuration]
                ),
                "bootstrap_95_interval": (
                    _percentile(bootstrap_exponents[configuration], 0.025),
                    _percentile(bootstrap_exponents[configuration], 0.975),
                ),
            }
            for configuration in configurations
        },
        "bootstraps": bootstraps,
        "bootstrap_seed": seed,
    }


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Save and analyze run-level stochastic scaling measurements."
    )
    commands = argument_parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="measure and save JSONL records")
    run_parser.add_argument("output", type=Path)
    run_parser.add_argument(
        "--sizes", type=int, nargs="+", default=(400, 500, 600, 750)
    )
    run_parser.add_argument("--cases", type=int, default=200)
    run_parser.add_argument(
        "--configurations",
        choices=tuple(CONFIGURATIONS),
        nargs="+",
        default=tuple(CONFIGURATIONS),
    )
    run_parser.add_argument("--budget", type=float, default=10_000_000)
    run_parser.add_argument("--seed", type=int, default=20260826)
    run_parser.add_argument(
        "--profile", choices=("mixed", "all-crossing"), default="all-crossing"
    )
    run_parser.add_argument("--overwrite", action="store_true")

    analyze_parser = commands.add_parser(
        "analyze", help="bootstrap p95 scaling exponents from JSONL records"
    )
    analyze_parser.add_argument("input", type=Path)
    analyze_parser.add_argument("--bootstraps", type=int, default=20_000)
    analyze_parser.add_argument("--seed", type=int, default=260826)
    analyze_parser.add_argument("--output", type=Path)
    return argument_parser


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.command == "run":
        measure(
            arguments.output,
            sizes=tuple(arguments.sizes),
            cases=arguments.cases,
            configurations=tuple(arguments.configurations),
            budget=arguments.budget,
            seed=arguments.seed,
            profile=arguments.profile,
            overwrite=arguments.overwrite,
        )
        return 0

    metadata, runs = load_runs(arguments.input)
    result = analyze_runs(runs, bootstraps=arguments.bootstraps, seed=arguments.seed)
    output = json.dumps({"metadata": metadata, "analysis": result}, indent=2)
    if arguments.output is None:
        print(output)
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(output + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
