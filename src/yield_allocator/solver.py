from __future__ import annotations

from dataclasses import dataclass
from itertools import product
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
class _Segment:
    market: Market
    branch: str
    lower: float
    upper: float

    def marginal(self, allocation: float) -> float:
        return self.market.marginal_income(allocation, self.branch)


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


def _allocation_at_price(segment: _Segment, price: float) -> float:
    if segment.marginal(segment.lower) <= price:
        return segment.lower
    if segment.marginal(segment.upper) >= price:
        return segment.upper

    lower, upper = segment.lower, segment.upper
    for _ in range(80):
        middle = (lower + upper) / 2
        if segment.marginal(middle) > price:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2


def _solve_segments(segments: tuple[_Segment, ...], budget: float) -> tuple[float, ...]:
    if sum(segment.lower for segment in segments) > budget:
        raise OptimizationError("infeasible segment lower bounds")
    if sum(segment.upper for segment in segments) < budget:
        raise OptimizationError("infeasible segment upper bounds")

    for segment in segments:
        _validate_concavity(segment)

    low_price = min(segment.marginal(segment.upper) for segment in segments)
    high_price = max(segment.marginal(segment.lower) for segment in segments)

    for _ in range(100):
        price = (low_price + high_price) / 2
        total = sum(_allocation_at_price(segment, price) for segment in segments)
        if total > budget:
            low_price = price
        else:
            high_price = price

    allocations = [
        _allocation_at_price(segment, (low_price + high_price) / 2)
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


def solve(markets: list[Market] | tuple[Market, ...], budget: float) -> Solution:
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

    for segments in product(*region_sets):
        if sum(segment.lower for segment in segments) > budget:
            continue
        if sum(segment.upper for segment in segments) < budget:
            continue
        allocations = _solve_segments(segments, budget)
        income = sum(
            market.income(allocation)
            for market, allocation in zip(markets, allocations, strict=True)
        )
        if income > best_income:
            best_income = income
            best_allocations = allocations

    if best_allocations is None:
        raise OptimizationError("no feasible allocation found")
    return Solution(budget, markets, best_allocations)
