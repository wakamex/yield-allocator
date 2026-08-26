from __future__ import annotations

import argparse
from dataclasses import replace
import json
import tomllib
from pathlib import Path
from typing import Any

from .solver import PRESETS, Market, Solution, solve


def load_problem(path: Path) -> tuple[float, list[Market]]:
    with path.open("rb") as input_file:
        data = tomllib.load(input_file)

    try:
        budget = float(data["budget"])
        market_inputs = data["markets"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("input requires a numeric budget and a markets array") from error

    if not isinstance(market_inputs, list):
        raise ValueError("markets must be an array of tables")

    markets = []
    for index, values in enumerate(market_inputs, start=1):
        if not isinstance(values, dict):
            raise ValueError("each market must be a table")
        try:
            markets.append(Market(**values))
        except TypeError as error:
            raise ValueError(f"market {index}: {error}") from error
    return budget, markets


def result_data(solution: Solution) -> dict[str, Any]:
    market_results = []
    for market, allocation in zip(
        solution.markets, solution.allocations, strict=True
    ):
        market_results.append(
            {
                "name": market.name,
                "allocation": allocation,
                "initial_utilization": market.utilization(0),
                "final_utilization": market.utilization(allocation),
                "initial_supply_apr": market.supply_rate(0),
                "final_supply_apr": market.supply_rate(allocation),
                "annual_income": market.income(allocation),
            }
        )
    return {
        "budget": solution.budget,
        "portfolio_supply_apr": solution.portfolio_rate,
        "annual_income": solution.annual_income,
        "markets": market_results,
    }


def format_result(solution: Solution) -> str:
    data = result_data(solution)
    lines = [
        f"Budget: ${data['budget']:,.2f}",
        f"Portfolio supply APR: {data['portfolio_supply_apr']:.6%}",
        f"Annualized income: ${data['annual_income']:,.2f}",
        "",
    ]
    for market in data["markets"]:
        lines.extend(
            (
                market["name"],
                f"  Allocation: ${market['allocation']:,.2f}",
                f"  Utilization: {market['initial_utilization']:.6%} -> "
                f"{market['final_utilization']:.6%}",
                f"  Supply APR: {market['initial_supply_apr']:.6%} -> "
                f"{market['final_supply_apr']:.6%}",
                f"  Annualized income: ${market['annual_income']:,.2f}",
            )
        )
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Optimize a static USDC lending allocation."
    )
    argument_parser.add_argument("input", type=Path, help="TOML problem file")
    argument_parser.add_argument(
        "--json", action="store_true", help="print machine-readable JSON"
    )
    argument_parser.add_argument(
        "--preset", choices=tuple(PRESETS), default="a0", help="solver preset"
    )
    for feature in (
        "adaptive_bisection",
        "closed_form_inversion",
        "newton_price_search",
        "cached_segment_algebra",
        "recursive_enumeration",
        "dual_bounds",
        "dual_reduced_cost_fixing",
        "dual_ambiguity_branching",
        "heuristic_incumbent",
        "best_bound",
        "heuristic_only",
    ):
        argument_parser.add_argument(
            f"--{feature.replace('_', '-')}",
            action=argparse.BooleanOptionalAction,
            default=None,
        )
    return argument_parser


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        budget, markets = load_problem(arguments.input)
        config = PRESETS[arguments.preset]
        for feature in (
            "adaptive_bisection",
            "closed_form_inversion",
            "newton_price_search",
            "cached_segment_algebra",
            "recursive_enumeration",
            "dual_bounds",
            "dual_reduced_cost_fixing",
            "dual_ambiguity_branching",
            "heuristic_incumbent",
            "best_bound",
            "heuristic_only",
        ):
            value = getattr(arguments, feature)
            if value is not None:
                config = replace(config, **{feature: value})
        solution = solve(markets, budget, config=config)
    except (OSError, ValueError) as error:
        parser().error(str(error))

    if arguments.json:
        print(json.dumps(result_data(solution), indent=2))
    else:
        print(format_result(solution))
    return 0
