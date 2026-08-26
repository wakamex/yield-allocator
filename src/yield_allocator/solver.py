from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
from math import isfinite


class OptimizationError(ValueError):
    pass


@dataclass(frozen=True)
class Market:
    name: str
    supply: float
    borrow: float
    kink: float
    slope_1: float
    slope_2: float
    base_rate: float = 0.0
    reserve_factor: float = 0.0
    max_allocation: float | None = None

    def __post_init__(self) -> None:
        values = (
            self.supply,
            self.borrow,
            self.kink,
            self.slope_1,
            self.slope_2,
            self.base_rate,
            self.reserve_factor,
        )
        if not self.name.strip():
            raise ValueError("market name cannot be empty")
        if not all(isfinite(value) for value in values):
            raise ValueError(f"{self.name}: inputs must be finite")
        if self.supply <= 0:
            raise ValueError(f"{self.name}: supply must be positive")
        if not 0 <= self.borrow <= self.supply:
            raise ValueError(f"{self.name}: borrow must be between zero and supply")
        if not 0 < self.kink < 1:
            raise ValueError(f"{self.name}: kink must be between zero and one")
        if min(self.slope_1, self.slope_2, self.base_rate) < 0:
            raise ValueError(f"{self.name}: rates and slopes cannot be negative")
        if not 0 <= self.reserve_factor < 1:
            raise ValueError(f"{self.name}: reserve_factor must be in [0, 1)")
        if self.max_allocation is not None:
            if not isfinite(self.max_allocation) or self.max_allocation < 0:
                raise ValueError(f"{self.name}: max_allocation cannot be negative")

    def utilization(self, allocation: float) -> float:
        return self.borrow / (self.supply + allocation)

    def borrow_rate(self, allocation: float) -> float:
        utilization = self.utilization(allocation)
        if utilization <= self.kink:
            return self.base_rate + self.slope_1 * utilization
        return (
            self.base_rate
            + self.slope_1 * self.kink
            + (utilization - self.kink) / (1 - self.kink) * self.slope_2
        )

    def supply_rate(self, allocation: float) -> float:
        utilization = self.utilization(allocation)
        return utilization * self.borrow_rate(allocation) * (1 - self.reserve_factor)

    def income(self, allocation: float) -> float:
        return allocation * self.supply_rate(allocation)

    @property
    def kink_allocation(self) -> float:
        return self.borrow / self.kink - self.supply

    def _curve(self, branch: str) -> tuple[float, float]:
        if branch == "low":
            return self.base_rate, self.slope_1
        slope = self.slope_2 / (1 - self.kink)
        intercept = self.base_rate + self.slope_1 * self.kink - slope * self.kink
        return intercept, slope

    def marginal_income(self, allocation: float, branch: str) -> float:
        intercept, slope = self._curve(branch)
        total_supply = self.supply + allocation
        retained = 1 - self.reserve_factor
        return retained * (
            intercept * self.borrow * self.supply / total_supply**2
            + slope
            * self.borrow**2
            * (self.supply - allocation)
            / total_supply**3
        )

    def marginal_income_slope(self, allocation: float, branch: str) -> float:
        intercept, slope = self._curve(branch)
        total_supply = self.supply + allocation
        retained = 1 - self.reserve_factor
        return 2 * retained * (
            -intercept * self.borrow * self.supply / total_supply**3
            + slope
            * self.borrow**2
            * (allocation - 2 * self.supply)
            / total_supply**4
        )


@dataclass(frozen=True)
class Solution:
    budget: float
    markets: tuple[Market, ...]
    allocations: tuple[float, ...]

    @property
    def annual_income(self) -> float:
        return sum(
            market.income(allocation)
            for market, allocation in zip(self.markets, self.allocations, strict=True)
        )

    @property
    def portfolio_rate(self) -> float:
        return self.annual_income / self.budget if self.budget else 0.0


@dataclass(frozen=True)
class SolverConfig:
    adaptive_bisection: bool = False
    recursive_enumeration: bool = False
    dual_bounds: bool = False
    heuristic_incumbent: bool = False
    best_bound: bool = False
    heuristic_only: bool = False


@dataclass
class SolveStats:
    possible_region_combinations: int = 0
    combinations_visited: int = 0
    feasibility_prunes: int = 0
    fixed_region_solves: int = 0
    outer_iterations: int = 0
    inner_iterations: int = 0
    marginal_evaluations: int = 0
    nodes_visited: int = 0
    bound_prunes: int = 0
    dual_solves: int = 0
    incumbent_updates: int = 0


PRESETS = {
    "a0": SolverConfig(),
    "a1": SolverConfig(adaptive_bisection=True),
    "a2": SolverConfig(adaptive_bisection=True, recursive_enumeration=True),
}


@dataclass(frozen=True)
class _Segment:
    market: Market
    branch: str
    lower: float
    upper: float

    def marginal(self, allocation: float) -> float:
        return self.market.marginal_income(allocation, self.branch)


def _marginal(
    segment: _Segment, allocation: float, stats: SolveStats | None
) -> float:
    if stats is not None:
        stats.marginal_evaluations += 1
    return segment.marginal(allocation)


def _segments(market: Market, budget: float) -> tuple[_Segment, ...]:
    cap = budget if market.max_allocation is None else market.max_allocation
    upper = min(budget, cap)
    kink = market.kink_allocation
    segments: list[_Segment] = []

    if kink > 0:
        if min(kink, upper) >= 0:
            segments.append(_Segment(market, "high", 0.0, min(kink, upper)))
        if upper >= kink:
            segments.append(_Segment(market, "low", kink, upper))
    else:
        segments.append(_Segment(market, "low", 0.0, upper))

    return tuple(segment for segment in segments if segment.lower <= segment.upper)


def _validate_concavity(segment: _Segment) -> None:
    slopes = (
        segment.market.marginal_income_slope(segment.lower, segment.branch),
        segment.market.marginal_income_slope(segment.upper, segment.branch),
    )
    if max(slopes) > 1e-18:
        raise OptimizationError(
            f"{segment.market.name}: income is not concave on the feasible "
            f"{segment.branch}-utilization segment"
        )


def _allocation_at_price(
    segment: _Segment,
    price: float,
    stats: SolveStats | None = None,
    *,
    adaptive: bool = False,
) -> float:
    if _marginal(segment, segment.lower, stats) <= price:
        return segment.lower
    if _marginal(segment, segment.upper, stats) >= price:
        return segment.upper

    lower, upper = segment.lower, segment.upper
    iterations = 64 if adaptive else 80
    tolerance = max(1e-7, segment.upper * 1e-14)
    for _ in range(iterations):
        if stats is not None:
            stats.inner_iterations += 1
        middle = (lower + upper) / 2
        if adaptive and (upper - lower <= tolerance or middle in (lower, upper)):
            break
        if _marginal(segment, middle, stats) > price:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2


def _solve_segments(
    segments: tuple[_Segment, ...],
    budget: float,
    stats: SolveStats | None = None,
    *,
    adaptive: bool = False,
) -> tuple[float, ...]:
    if sum(segment.lower for segment in segments) > budget:
        raise OptimizationError("infeasible segment lower bounds")
    if sum(segment.upper for segment in segments) < budget:
        raise OptimizationError("infeasible segment upper bounds")

    for segment in segments:
        _validate_concavity(segment)

    if stats is not None:
        stats.fixed_region_solves += 1
    low_price = min(_marginal(segment, segment.upper, stats) for segment in segments)
    high_price = max(_marginal(segment, segment.lower, stats) for segment in segments)

    iterations = 64 if adaptive else 100
    allocation_tolerance = max(1e-7, budget * 1e-12)
    for _ in range(iterations):
        if stats is not None:
            stats.outer_iterations += 1
        price = (low_price + high_price) / 2
        if adaptive and price in (low_price, high_price):
            break
        total = sum(
            _allocation_at_price(segment, price, stats, adaptive=adaptive)
            for segment in segments
        )
        if adaptive and abs(total - budget) <= allocation_tolerance:
            low_price = high_price = price
            break
        if total > budget:
            low_price = price
        else:
            high_price = price

    allocations = [
        _allocation_at_price(
            segment,
            (low_price + high_price) / 2,
            stats,
            adaptive=adaptive,
        )
        for segment in segments
    ]
    residual = budget - sum(allocations)

    if residual > 0:
        for index, segment in enumerate(segments):
            change = min(residual, segment.upper - allocations[index])
            allocations[index] += change
            residual -= change
    elif residual < 0:
        for index, segment in enumerate(segments):
            change = min(-residual, allocations[index] - segment.lower)
            allocations[index] -= change
            residual += change

    if abs(residual) > max(1e-7, budget * 1e-12):
        raise OptimizationError("could not satisfy the allocation constraint")
    return tuple(allocations)


def solve(
    markets: list[Market] | tuple[Market, ...],
    budget: float,
    *,
    config: SolverConfig | None = None,
    stats: SolveStats | None = None,
) -> Solution:
    config = config or SolverConfig()
    if any(
        (
            config.dual_bounds,
            config.heuristic_incumbent,
            config.best_bound,
            config.heuristic_only,
        )
    ):
        raise ValueError("this solver configuration is not implemented yet")
    markets = tuple(markets)
    if not markets:
        raise ValueError("at least one market is required")
    if not isfinite(budget) or budget < 0:
        raise ValueError("budget must be finite and nonnegative")
    if budget == 0:
        return Solution(budget, markets, (0.0,) * len(markets))

    capacity = sum(
        market.max_allocation if market.max_allocation is not None else budget
        for market in markets
    )
    if capacity < budget:
        raise OptimizationError("market allocation caps are below the budget")

    best_allocations: tuple[float, ...] | None = None
    best_income = float("-inf")
    region_sets = tuple(_segments(market, budget) for market in markets)
    if stats is not None:
        stats.possible_region_combinations = math.prod(
            len(regions) for regions in region_sets
        )

    def consider(segments: tuple[_Segment, ...]) -> None:
        nonlocal best_allocations, best_income
        if stats is not None:
            stats.combinations_visited += 1
        if sum(segment.lower for segment in segments) > budget:
            if stats is not None:
                stats.feasibility_prunes += 1
            return
        if sum(segment.upper for segment in segments) < budget:
            if stats is not None:
                stats.feasibility_prunes += 1
            return
        allocations = _solve_segments(
            segments,
            budget,
            stats,
            adaptive=config.adaptive_bisection,
        )
        income = sum(
            market.income(allocation)
            for market, allocation in zip(markets, allocations, strict=True)
        )
        if income > best_income:
            best_income = income
            best_allocations = allocations
            if stats is not None:
                stats.incumbent_updates += 1

    if config.recursive_enumeration:
        suffix_lower = [0.0] * (len(markets) + 1)
        suffix_upper = [0.0] * (len(markets) + 1)
        for index in range(len(markets) - 1, -1, -1):
            suffix_lower[index] = suffix_lower[index + 1] + min(
                segment.lower for segment in region_sets[index]
            )
            suffix_upper[index] = suffix_upper[index + 1] + max(
                segment.upper for segment in region_sets[index]
            )

        def visit(
            index: int,
            selected: tuple[_Segment, ...],
            lower: float,
            upper: float,
        ) -> None:
            if stats is not None:
                stats.nodes_visited += 1
            if lower + suffix_lower[index] > budget:
                if stats is not None:
                    stats.feasibility_prunes += 1
                return
            if upper + suffix_upper[index] < budget:
                if stats is not None:
                    stats.feasibility_prunes += 1
                return
            if index == len(markets):
                consider(selected)
                return
            for segment in region_sets[index]:
                visit(
                    index + 1,
                    (*selected, segment),
                    lower + segment.lower,
                    upper + segment.upper,
                )

        visit(0, (), 0.0, 0.0)
    else:
        for segments in product(*region_sets):
            consider(segments)

    if best_allocations is None:
        raise OptimizationError("no feasible allocation found")
    return Solution(budget, markets, best_allocations)
