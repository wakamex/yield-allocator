from __future__ import annotations

from dataclasses import dataclass
import heapq
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
    closed_form_inversion: bool = False
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
    closed_form_evaluations: int = 0
    closed_form_fallbacks: int = 0
    nodes_visited: int = 0
    bound_prunes: int = 0
    dual_solves: int = 0
    incumbent_updates: int = 0


PRESETS = {
    "a0": SolverConfig(),
    "a1": SolverConfig(adaptive_bisection=True),
    "a2": SolverConfig(adaptive_bisection=True, recursive_enumeration=True),
    "a3": SolverConfig(
        adaptive_bisection=True,
        recursive_enumeration=True,
        dual_bounds=True,
    ),
    "a4": SolverConfig(
        adaptive_bisection=True,
        recursive_enumeration=True,
        dual_bounds=True,
        heuristic_incumbent=True,
    ),
    "a5": SolverConfig(
        adaptive_bisection=True,
        recursive_enumeration=True,
        dual_bounds=True,
        heuristic_incumbent=True,
        best_bound=True,
    ),
    "h1": SolverConfig(
        adaptive_bisection=True,
        recursive_enumeration=True,
        dual_bounds=True,
        heuristic_incumbent=True,
        best_bound=True,
        heuristic_only=True,
    ),
    "recommended": SolverConfig(
        adaptive_bisection=True,
        recursive_enumeration=True,
        dual_bounds=True,
        best_bound=True,
    ),
}


@dataclass(frozen=True)
class _Segment:
    market: Market
    branch: str
    lower: float
    upper: float
    inverse_linear: float
    inverse_constant: float

    def marginal(self, allocation: float) -> float:
        return self.market.marginal_income(allocation, self.branch)


@dataclass(frozen=True)
class _DualResult:
    bound: float
    price: float
    segments: tuple[_Segment, ...]


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

    def segment(branch: str, lower: float, upper: float) -> _Segment:
        intercept, slope = market._curve(branch)
        utilization = market.borrow / market.supply
        retained = 1 - market.reserve_factor
        return _Segment(
            market=market,
            branch=branch,
            lower=lower,
            upper=upper,
            inverse_linear=retained
            * (intercept * utilization - slope * utilization**2),
            inverse_constant=2 * retained * slope * utilization**2,
        )

    if kink > 0:
        if min(kink, upper) >= 0:
            segments.append(segment("high", 0.0, min(kink, upper)))
        if upper >= kink:
            segments.append(segment("low", kink, upper))
    else:
        segments.append(segment("low", 0.0, upper))

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
    closed_form: bool = False,
) -> float:
    if _marginal(segment, segment.lower, stats) <= price:
        return segment.lower
    if _marginal(segment, segment.upper, stats) >= price:
        return segment.upper

    if closed_form:
        if stats is not None:
            stats.closed_form_evaluations += 1
        allocation = _closed_form_allocation(segment, price)
        if allocation is not None:
            return allocation
        if stats is not None:
            stats.closed_form_fallbacks += 1

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


def _closed_form_allocation(segment: _Segment, price: float) -> float | None:
    linear = segment.inverse_linear
    constant = segment.inverse_constant

    if price == 0:
        if linear == 0:
            return None
        roots = (-constant / linear,)
    else:
        cubic_linear = -linear / price
        cubic_constant = -constant / price
        half_constant = cubic_constant / 2
        third_linear = cubic_linear / 3
        discriminant = half_constant**2 + third_linear**3
        if not math.isfinite(discriminant):
            return None

        scale = max(abs(half_constant**2), abs(third_linear**3), 1.0)
        if discriminant >= -1e-14 * scale:
            root_discriminant = math.sqrt(max(0.0, discriminant))
            first = math.cbrt(-half_constant + root_discriminant)
            second = (
                -cubic_linear / (3 * first)
                if first != 0
                else math.cbrt(-half_constant - root_discriminant)
            )
            primary = first + second
            roots = (primary, -primary / 2) if discriminant <= 1e-14 * scale else (primary,)
        else:
            radius = 2 * math.sqrt(-third_linear)
            cosine = -half_constant / math.sqrt(-(third_linear**3))
            angle = math.acos(max(-1.0, min(1.0, cosine))) / 3
            roots = tuple(
                radius * math.cos(angle - 2 * math.pi * index / 3)
                for index in range(3)
            )

    lower = 1 + segment.lower / segment.market.supply
    upper = 1 + segment.upper / segment.market.supply
    tolerance = max(1e-14, upper * 1e-12)
    valid = [
        min(upper, max(lower, root))
        for root in roots
        if math.isfinite(root) and lower - tolerance <= root <= upper + tolerance
    ]
    if not valid:
        return None

    root = min(
        valid,
        key=lambda value: abs(price * value**3 - linear * value - constant),
    )
    allocation = segment.market.supply * (root - 1)
    allocation = min(segment.upper, max(segment.lower, allocation))
    error = abs(segment.marginal(allocation) - price)
    if error > max(1e-12, abs(price) * 1e-9):
        return None
    return allocation


def _solve_segments(
    segments: tuple[_Segment, ...],
    budget: float,
    stats: SolveStats | None = None,
    *,
    adaptive: bool = False,
    closed_form: bool = False,
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
            _allocation_at_price(
                segment,
                price,
                stats,
                adaptive=adaptive,
                closed_form=closed_form,
            )
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
            closed_form=closed_form,
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


def _lagrangian_bound(
    region_options: tuple[tuple[_Segment, ...], ...],
    budget: float,
    stats: SolveStats | None,
    *,
    adaptive: bool,
    closed_form: bool,
) -> _DualResult:
    if stats is not None:
        stats.dual_solves += 1
    for options in region_options:
        for segment in options:
            _validate_concavity(segment)

    low_price = min(
        _marginal(segment, segment.upper, stats)
        for options in region_options
        for segment in options
    )
    high_price = max(
        _marginal(segment, segment.lower, stats)
        for options in region_options
        for segment in options
    )

    def evaluate(price: float) -> tuple[float, float, tuple[_Segment, ...]]:
        total_allocation = 0.0
        dual_value = price * budget
        selected = []
        for options in region_options:
            best_value = float("-inf")
            best_allocation = 0.0
            best_segment = options[0]
            for segment in options:
                allocation = _allocation_at_price(
                    segment,
                    price,
                    stats,
                    adaptive=adaptive,
                    closed_form=closed_form,
                )
                value = segment.market.income(allocation) - price * allocation
                if value > best_value:
                    best_value = value
                    best_allocation = allocation
                    best_segment = segment
            total_allocation += best_allocation
            dual_value += best_value
            selected.append(best_segment)
        return total_allocation, dual_value, tuple(selected)

    iterations = 64 if adaptive else 100
    for _ in range(iterations):
        if stats is not None:
            stats.outer_iterations += 1
        price = (low_price + high_price) / 2
        if price in (low_price, high_price):
            break
        total, _, _ = evaluate(price)
        if total > budget:
            low_price = price
        else:
            high_price = price

    candidates = (
        (low_price, evaluate(low_price)),
        ((low_price + high_price) / 2, evaluate((low_price + high_price) / 2)),
        (high_price, evaluate(high_price)),
    )
    price, (_, bound, segments) = min(candidates, key=lambda candidate: candidate[1][1])
    return _DualResult(bound, price, segments)


def _heuristic_allocation(
    region_options: tuple[tuple[_Segment, ...], ...],
    budget: float,
    stats: SolveStats | None,
    *,
    adaptive: bool,
    closed_form: bool,
) -> tuple[float, ...]:
    relaxation = _lagrangian_bound(
        region_options,
        budget,
        stats,
        adaptive=adaptive,
        closed_form=closed_form,
    )
    selected = list(relaxation.segments)

    def lagrangian_value(segment: _Segment) -> float:
        allocation = _allocation_at_price(
            segment,
            relaxation.price,
            stats,
            adaptive=adaptive,
            closed_form=closed_form,
        )
        return segment.market.income(allocation) - relaxation.price * allocation

    while sum(segment.lower for segment in selected) > budget:
        replacements = []
        for index, options in enumerate(region_options):
            for alternative in options:
                if alternative.lower < selected[index].lower:
                    loss = lagrangian_value(selected[index]) - lagrangian_value(alternative)
                    replacements.append((loss, index, alternative))
        if not replacements:
            raise OptimizationError("could not repair heuristic lower bounds")
        _, index, replacement = min(replacements, key=lambda item: item[0])
        selected[index] = replacement

    while sum(segment.upper for segment in selected) < budget:
        replacements = []
        for index, options in enumerate(region_options):
            for alternative in options:
                if alternative.upper > selected[index].upper:
                    loss = lagrangian_value(selected[index]) - lagrangian_value(alternative)
                    replacements.append((loss, index, alternative))
        if not replacements:
            raise OptimizationError("could not repair heuristic upper bounds")
        _, index, replacement = min(replacements, key=lambda item: item[0])
        selected[index] = replacement

    return _solve_segments(
        tuple(selected),
        budget,
        stats,
        adaptive=adaptive,
        closed_form=closed_form,
    )


def solve(
    markets: list[Market] | tuple[Market, ...],
    budget: float,
    *,
    config: SolverConfig | None = None,
    stats: SolveStats | None = None,
) -> Solution:
    config = config or SolverConfig()
    if config.dual_bounds and not config.recursive_enumeration:
        raise ValueError("dual_bounds requires recursive_enumeration")
    if config.heuristic_incumbent and not config.dual_bounds:
        raise ValueError("heuristic_incumbent requires dual_bounds")
    if config.best_bound and not config.dual_bounds:
        raise ValueError("best_bound requires dual_bounds")
    if config.heuristic_only and not config.heuristic_incumbent:
        raise ValueError("heuristic_only requires heuristic_incumbent")
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
            closed_form=config.closed_form_inversion,
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

    if config.dual_bounds:
        if config.heuristic_incumbent:
            best_allocations = _heuristic_allocation(
                region_sets,
                budget,
                stats,
                adaptive=config.adaptive_bisection,
                closed_form=config.closed_form_inversion,
            )
            best_income = sum(
                market.income(allocation)
                for market, allocation in zip(
                    markets, best_allocations, strict=True
                )
            )
            if stats is not None:
                stats.incumbent_updates += 1
            if config.heuristic_only:
                return Solution(budget, markets, best_allocations)

        def bounds(
            options: tuple[tuple[_Segment, ...], ...],
        ) -> tuple[float, float]:
            return (
                sum(min(region.lower for region in choices) for choices in options),
                sum(max(region.upper for region in choices) for choices in options),
            )

        def branch_index(
            options: tuple[tuple[_Segment, ...], ...],
        ) -> int | None:
            return next(
                (index for index, regions in enumerate(options) if len(regions) > 1),
                None,
            )

        def upper_bound(options: tuple[tuple[_Segment, ...], ...]) -> float:
            return _lagrangian_bound(
                options,
                budget,
                stats,
                adaptive=config.adaptive_bisection,
                closed_form=config.closed_form_inversion,
            ).bound

        def cannot_improve(bound: float) -> bool:
            tolerance = max(1e-7, abs(best_income) * 1e-12)
            return best_allocations is not None and bound <= best_income + tolerance

        def visit_bounded(
            options: tuple[tuple[_Segment, ...], ...],
            lower: float,
            upper: float,
        ) -> None:
            if stats is not None:
                stats.nodes_visited += 1
            if lower > budget or upper < budget:
                if stats is not None:
                    stats.feasibility_prunes += 1
                return

            bound = upper_bound(options)
            if cannot_improve(bound):
                if stats is not None:
                    stats.bound_prunes += 1
                return

            index = branch_index(options)
            if index is None:
                consider(tuple(regions[0] for regions in options))
                return

            for segment in options[index]:
                child = list(options)
                child[index] = (segment,)
                child_options = tuple(child)
                child_lower, child_upper = bounds(child_options)
                visit_bounded(
                    child_options,
                    child_lower,
                    child_upper,
                )

        if config.best_bound:
            root_lower, root_upper = bounds(region_sets)
            queue: list[
                tuple[
                    float,
                    int,
                    tuple[tuple[_Segment, ...], ...],
                    float,
                    float,
                ]
            ] = []
            serial = 0
            if root_lower <= budget <= root_upper:
                heapq.heappush(
                    queue,
                    (-upper_bound(region_sets), serial, region_sets, root_lower, root_upper),
                )

            while queue:
                negative_bound, _, options, _, _ = heapq.heappop(queue)
                node_bound = -negative_bound
                if stats is not None:
                    stats.nodes_visited += 1
                if cannot_improve(node_bound):
                    if stats is not None:
                        stats.bound_prunes += 1
                    continue

                index = branch_index(options)
                if index is None:
                    consider(tuple(regions[0] for regions in options))
                    continue

                for segment in options[index]:
                    child = list(options)
                    child[index] = (segment,)
                    child_options = tuple(child)
                    child_lower, child_upper = bounds(child_options)
                    if child_lower > budget or child_upper < budget:
                        if stats is not None:
                            stats.feasibility_prunes += 1
                        continue
                    child_bound = upper_bound(child_options)
                    if cannot_improve(child_bound):
                        if stats is not None:
                            stats.bound_prunes += 1
                        continue
                    serial += 1
                    heapq.heappush(
                        queue,
                        (
                            -child_bound,
                            serial,
                            child_options,
                            child_lower,
                            child_upper,
                        ),
                    )
        else:
            root_lower, root_upper = bounds(region_sets)
            visit_bounded(region_sets, root_lower, root_upper)
    elif config.recursive_enumeration:
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
