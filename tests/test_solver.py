from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from yield_allocator.benchmark import generate_markets, run_benchmark
from yield_allocator.cli import load_problem
from yield_allocator.solver import Market, solve


ROOT = Path(__file__).parents[1]
TEST_CASE = ROOT / "examples" / "test_case.toml"


class SolverTests(unittest.TestCase):
    def test_borrow_curve_is_continuous_at_kink(self) -> None:
        market = Market("market", 100, 92, 0.92, 0.04, 0.10)
        at_kink = market.kink_allocation

        self.assertAlmostEqual(market.borrow_rate(at_kink), 0.04 * 0.92)
        self.assertAlmostEqual(
            market.borrow_rate(at_kink - 1e-8),
            market.borrow_rate(at_kink + 1e-8),
            places=8,
        )

    def test_example_case_has_an_interior_solution(self) -> None:
        budget, markets = load_problem(TEST_CASE)
        solution = solve(markets, budget)

        self.assertAlmostEqual(solution.allocations[0], 10_000_000, places=3)
        self.assertAlmostEqual(solution.allocations[1], 0, places=3)
        self.assertAlmostEqual(solution.portfolio_rate, 0.025627138862664)
        self.assertAlmostEqual(solution.annual_income, 192_203.54146998)

    def test_interior_solution_matches_grid_oracle(self) -> None:
        markets = [
            Market("one", 100, 80, 0.9, 0.04, 0.1),
            Market("two", 100, 75, 0.9, 0.045, 0.1),
        ]
        solution = solve(markets, 10)
        grid_step = 0.001
        _, grid_allocation = max(
            (
                markets[0].income(index * grid_step)
                + markets[1].income(10 - index * grid_step),
                index * grid_step,
            )
            for index in range(10_001)
        )

        self.assertAlmostEqual(solution.allocations[0], grid_allocation, delta=grid_step)
        self.assertAlmostEqual(sum(solution.allocations), 10)

    def test_caps_are_respected(self) -> None:
        markets = [
            Market("one", 100, 50, 0.8, 0.04, 0.1, max_allocation=2),
            Market("two", 100, 40, 0.8, 0.04, 0.1),
        ]

        solution = solve(markets, 5)

        self.assertLessEqual(solution.allocations[0], 2)
        self.assertAlmostEqual(sum(solution.allocations), 5)


class EntrypointTests(unittest.TestCase):
    def assert_entrypoint(self, command: list[str]) -> None:
        result = subprocess.run(
            [*command, str(TEST_CASE), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        self.assertEqual(output["budget"], 10_000_000)
        self.assertEqual(len(output["markets"]), 2)

    def test_module_entrypoint(self) -> None:
        self.assert_entrypoint([sys.executable, "-m", "yield_allocator"])

    def test_script_entrypoint(self) -> None:
        command = shutil.which("yield-allocate")
        self.assertIsNotNone(command)
        self.assert_entrypoint([command])

    def test_benchmark_entrypoint(self) -> None:
        command = shutil.which("yield-benchmark")
        self.assertIsNotNone(command)
        result = subprocess.run(
            [command, "--max-markets", "2", "--trials", "1", "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        self.assertEqual(output["results"][0]["markets"], 2)


class BenchmarkTests(unittest.TestCase):
    def test_market_generation_is_repeatable(self) -> None:
        first = generate_markets(4, 10_000_000, 1234)
        second = generate_markets(4, 10_000_000, 1234)

        self.assertEqual(first, second)

    def test_all_crossing_profile_crosses_within_budget(self) -> None:
        markets = generate_markets(4, 10_000_000, 1234, "all-crossing")

        self.assertTrue(
            all(0 < market.kink_allocation < 10_000_000 for market in markets)
        )

    def test_small_benchmark(self) -> None:
        rows = run_benchmark(max_markets=3, trials=1, seed=1234)

        self.assertEqual([row.markets for row in rows], [2, 3])
        self.assertTrue(all(row.median_ms > 0 for row in rows))


if __name__ == "__main__":
    unittest.main()
