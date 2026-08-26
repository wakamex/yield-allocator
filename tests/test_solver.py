from __future__ import annotations

import json
from dataclasses import replace
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from yield_allocator.ablation import run_contributions, run_step_forward
from yield_allocator.benchmark import generate_markets, run_benchmark
from yield_allocator.cli import load_problem
from yield_allocator.solver import PRESETS, Market, SolveStats, SolverConfig, solve


ROOT = Path(__file__).parents[1]
TEST_CASE = ROOT / "examples" / "two_markets.toml"


class SolverTests(unittest.TestCase):
    def test_borrow_curve_is_continuous_at_kink(self) -> None:
        market = Market("market", 100, 85, 0.85, 0.03, 0.12)
        at_kink = market.kink_allocation

        self.assertAlmostEqual(market.borrow_rate(at_kink), 0.03 * 0.85)
        self.assertAlmostEqual(
            market.borrow_rate(at_kink - 1e-8),
            market.borrow_rate(at_kink + 1e-8),
            places=8,
        )

    def test_example_case_has_an_interior_solution(self) -> None:
        budget, markets = load_problem(TEST_CASE)
        solution = solve(markets, budget)

        self.assertAlmostEqual(solution.allocations[0], 2_453_738.774526704, places=3)
        self.assertAlmostEqual(solution.allocations[1], 5_046_261.225473296, places=3)
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

    def test_baseline_instrumentation(self) -> None:
        budget, markets = load_problem(TEST_CASE)
        stats = SolveStats()

        solve(markets, budget, config=SolverConfig(), stats=stats)

        self.assertEqual(stats.possible_region_combinations, 1)
        self.assertEqual(stats.combinations_visited, 1)
        self.assertEqual(stats.fixed_region_solves, 1)
        self.assertGreater(stats.marginal_evaluations, 0)

    def test_adaptive_bisection_matches_baseline_with_fewer_evaluations(self) -> None:
        budget, markets = load_problem(TEST_CASE)
        baseline_stats = SolveStats()
        adaptive_stats = SolveStats()

        baseline = solve(markets, budget, stats=baseline_stats)
        adaptive = solve(
            markets,
            budget,
            config=SolverConfig(adaptive_bisection=True),
            stats=adaptive_stats,
        )

        self.assertAlmostEqual(adaptive.annual_income, baseline.annual_income, places=6)
        for actual, expected in zip(
            adaptive.allocations, baseline.allocations, strict=True
        ):
            self.assertAlmostEqual(actual, expected, places=3)
        self.assertLess(
            adaptive_stats.marginal_evaluations,
            baseline_stats.marginal_evaluations,
        )

    def test_closed_form_inversion_matches_bisection(self) -> None:
        markets = generate_markets(8, 10_000_000, 8642, "all-crossing")
        baseline = solve(markets, 10_000_000)
        stats = SolveStats()

        closed_form = solve(
            markets,
            10_000_000,
            config=SolverConfig(closed_form_inversion=True),
            stats=stats,
        )

        self.assertAlmostEqual(closed_form.annual_income, baseline.annual_income, places=6)
        for actual, expected in zip(
            closed_form.allocations, baseline.allocations, strict=True
        ):
            self.assertAlmostEqual(actual, expected, places=3)
        self.assertGreater(stats.closed_form_evaluations, 0)
        self.assertEqual(stats.closed_form_fallbacks, 0)
        self.assertEqual(stats.inner_iterations, 0)

    def test_newton_price_search_matches_bisection(self) -> None:
        markets = generate_markets(8, 10_000_000, 9753, "all-crossing")
        baseline_stats = SolveStats()
        baseline = solve(markets, 10_000_000, stats=baseline_stats)
        stats = SolveStats()

        newton = solve(
            markets,
            10_000_000,
            config=SolverConfig(newton_price_search=True),
            stats=stats,
        )

        self.assertAlmostEqual(newton.annual_income, baseline.annual_income, places=6)
        for actual, expected in zip(
            newton.allocations, baseline.allocations, strict=True
        ):
            self.assertAlmostEqual(actual, expected, places=3)
        self.assertGreater(stats.newton_steps, 0)
        self.assertLess(stats.outer_iterations, baseline_stats.outer_iterations)

    def test_recommended_preset_matches_baseline(self) -> None:
        markets = generate_markets(8, 10_000_000, 7531, "all-crossing")
        baseline = solve(markets, 10_000_000)
        stats = SolveStats()

        recommended = solve(
            markets,
            10_000_000,
            config=PRESETS["recommended"],
            stats=stats,
        )

        self.assertAlmostEqual(
            recommended.annual_income, baseline.annual_income, places=6
        )
        self.assertGreater(stats.closed_form_evaluations, 0)
        self.assertEqual(stats.newton_steps, 0)
        self.assertTrue(PRESETS["recommended"].cached_segment_algebra)
        self.assertTrue(PRESETS["recommended"].dual_reduced_cost_fixing)
        self.assertFalse(PRESETS["recommended"].dual_ambiguity_branching)

    def test_cached_segment_algebra_matches_direct_evaluation(self) -> None:
        markets = generate_markets(8, 10_000_000, 6420, "all-crossing")
        baseline_stats = SolveStats()
        baseline = solve(markets, 10_000_000, stats=baseline_stats)
        stats = SolveStats()

        cached = solve(
            markets,
            10_000_000,
            config=SolverConfig(cached_segment_algebra=True),
            stats=stats,
        )

        self.assertAlmostEqual(cached.annual_income, baseline.annual_income, places=6)
        for actual, expected in zip(
            cached.allocations, baseline.allocations, strict=True
        ):
            self.assertAlmostEqual(actual, expected, places=3)
        self.assertEqual(
            stats.marginal_evaluations, baseline_stats.marginal_evaluations
        )

    def test_recursive_enumeration_prunes_infeasible_subtrees(self) -> None:
        markets = generate_markets(6, 10_000_000, 1234, "all-crossing")
        baseline = solve(markets, 10_000_000)
        stats = SolveStats()

        recursive = solve(
            markets,
            10_000_000,
            config=SolverConfig(recursive_enumeration=True),
            stats=stats,
        )

        self.assertAlmostEqual(recursive.annual_income, baseline.annual_income, places=6)
        self.assertEqual(stats.possible_region_combinations, 64)
        self.assertLess(stats.combinations_visited, 64)
        self.assertGreater(stats.feasibility_prunes, 0)

    def test_dual_bounds_match_baseline_and_prune(self) -> None:
        markets = generate_markets(8, 10_000_000, 4321, "all-crossing")
        baseline = solve(
            markets,
            10_000_000,
            config=SolverConfig(
                adaptive_bisection=True,
                recursive_enumeration=True,
            ),
        )
        stats = SolveStats()

        bounded = solve(
            markets,
            10_000_000,
            config=SolverConfig(
                adaptive_bisection=True,
                recursive_enumeration=True,
                dual_bounds=True,
            ),
            stats=stats,
        )

        self.assertAlmostEqual(bounded.annual_income, baseline.annual_income, places=6)
        self.assertGreater(stats.dual_solves, 0)
        self.assertGreater(stats.bound_prunes, 0)

    def test_heuristic_incumbent_preserves_exact_result(self) -> None:
        markets = generate_markets(8, 10_000_000, 9876, "all-crossing")
        exact_config = SolverConfig(
            adaptive_bisection=True,
            recursive_enumeration=True,
            dual_bounds=True,
        )
        baseline = solve(markets, 10_000_000, config=exact_config)
        stats = SolveStats()

        initialized = solve(
            markets,
            10_000_000,
            config=SolverConfig(
                adaptive_bisection=True,
                recursive_enumeration=True,
                dual_bounds=True,
                heuristic_incumbent=True,
            ),
            stats=stats,
        )

        self.assertAlmostEqual(initialized.annual_income, baseline.annual_income, places=6)
        self.assertGreater(stats.incumbent_updates, 0)

    def test_best_bound_preserves_exact_result(self) -> None:
        markets = generate_markets(8, 10_000_000, 2468, "all-crossing")
        depth_first = solve(
            markets,
            10_000_000,
            config=SolverConfig(
                adaptive_bisection=True,
                recursive_enumeration=True,
                dual_bounds=True,
                heuristic_incumbent=True,
            ),
        )
        stats = SolveStats()

        best_bound = solve(
            markets,
            10_000_000,
            config=SolverConfig(
                adaptive_bisection=True,
                recursive_enumeration=True,
                dual_bounds=True,
                heuristic_incumbent=True,
                best_bound=True,
            ),
            stats=stats,
        )

        self.assertAlmostEqual(best_bound.annual_income, depth_first.annual_income, places=6)
        self.assertGreater(stats.nodes_visited, 0)

    def test_dual_reduced_cost_fixing_preserves_exact_result(self) -> None:
        markets = generate_markets(8, 10_000_000, 1234, "all-crossing")
        exact = solve(markets, 10_000_000)
        control_config = replace(
            PRESETS["recommended"],
            dual_reduced_cost_fixing=False,
            dual_ambiguity_branching=False,
        )
        control_stats = SolveStats()
        solve(
            markets,
            10_000_000,
            config=control_config,
            stats=control_stats,
        )
        stats = SolveStats()

        fixed = solve(
            markets,
            10_000_000,
            config=replace(
                control_config,
                dual_reduced_cost_fixing=True,
            ),
            stats=stats,
        )

        self.assertAlmostEqual(fixed.annual_income, exact.annual_income, places=6)
        self.assertGreater(stats.reduced_cost_fixes, 0)
        self.assertLess(stats.dual_solves, control_stats.dual_solves)

    def test_dual_reduced_cost_fixing_is_lazy_when_root_prunes(self) -> None:
        seed = 20260826 + 8 * 1_000_003 + 97_409
        markets = generate_markets(8, 10_000_000, seed, "all-crossing")
        control_config = replace(
            PRESETS["recommended"],
            dual_reduced_cost_fixing=False,
        )
        control_stats = SolveStats()
        control = solve(
            markets,
            10_000_000,
            config=control_config,
            stats=control_stats,
        )
        stats = SolveStats()

        lazy = solve(
            markets,
            10_000_000,
            config=PRESETS["recommended"],
            stats=stats,
        )

        self.assertAlmostEqual(lazy.annual_income, control.annual_income, places=6)
        self.assertEqual(stats.nodes_visited, 1)
        self.assertEqual(stats.reduced_cost_fixes, 0)
        self.assertEqual(stats.marginal_evaluations, control_stats.marginal_evaluations)

    def test_dual_ambiguity_branching_preserves_exact_result(self) -> None:
        markets = generate_markets(8, 10_000_000, 1234, "all-crossing")
        exact = solve(markets, 10_000_000)
        control_config = replace(
            PRESETS["recommended"],
            dual_reduced_cost_fixing=False,
            dual_ambiguity_branching=False,
        )
        control_stats = SolveStats()
        solve(
            markets,
            10_000_000,
            config=control_config,
            stats=control_stats,
        )
        stats = SolveStats()

        prioritized = solve(
            markets,
            10_000_000,
            config=replace(
                control_config,
                dual_ambiguity_branching=True,
            ),
            stats=stats,
        )

        self.assertAlmostEqual(prioritized.annual_income, exact.annual_income, places=6)
        self.assertGreater(stats.ambiguity_branches, 0)
        self.assertLess(stats.nodes_visited, control_stats.nodes_visited)

    def test_heuristic_only_returns_feasible_bounded_result(self) -> None:
        markets = generate_markets(8, 10_000_000, 1357, "all-crossing")
        exact = solve(
            markets,
            10_000_000,
            config=SolverConfig(
                adaptive_bisection=True,
                recursive_enumeration=True,
                dual_bounds=True,
                heuristic_incumbent=True,
                best_bound=True,
            ),
        )
        stats = SolveStats()

        heuristic = solve(
            markets,
            10_000_000,
            config=SolverConfig(
                adaptive_bisection=True,
                recursive_enumeration=True,
                dual_bounds=True,
                heuristic_incumbent=True,
                best_bound=True,
                heuristic_only=True,
            ),
            stats=stats,
        )

        self.assertAlmostEqual(sum(heuristic.allocations), 10_000_000)
        self.assertLessEqual(heuristic.annual_income, exact.annual_income + 1e-6)
        self.assertEqual(stats.nodes_visited, 0)


class EntrypointTests(unittest.TestCase):
    def assert_entrypoint(self, command: list[str]) -> None:
        result = subprocess.run(
            [*command, str(TEST_CASE), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        self.assertEqual(output["budget"], 7_500_000)
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

    def test_solver_feature_override(self) -> None:
        command = shutil.which("yield-allocate")
        self.assertIsNotNone(command)
        result = subprocess.run(
            [
                command,
                str(TEST_CASE),
                "--adaptive-bisection",
                "--closed-form-inversion",
                "--newton-price-search",
                "--cached-segment-algebra",
                "--recursive-enumeration",
                "--dual-bounds",
                "--dual-reduced-cost-fixing",
                "--dual-ambiguity-branching",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout)["budget"], 7_500_000)

    def test_ablation_entrypoint(self) -> None:
        command = shutil.which("yield-ablate")
        self.assertIsNotNone(command)
        result = subprocess.run(
            [command, str(TEST_CASE), "--trials", "1", "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        output = json.loads(result.stdout)
        self.assertEqual(output[0]["candidate"], "baseline")
        self.assertTrue(output[0]["exact"])


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

    def test_contribution_factors_reproduce_total_speedup(self) -> None:
        progress = []
        result = run_contributions(
            TEST_CASE,
            trials=1,
            progress=lambda completed, total, name: progress.append(
                (completed, total, name)
            ),
        )
        product = 1.0
        for contribution in result.contributions:
            product *= contribution.attributed_speedup

        self.assertAlmostEqual(product, result.total_speedup, places=10)
        self.assertAlmostEqual(
            sum(item.log_speedup_share for item in result.contributions),
            1.0,
            places=10,
        )
        configurations = len(result.configuration_seconds)
        self.assertEqual(progress[-1][:2], (configurations, configurations))

    def test_heuristic_only_exactness_is_measured(self) -> None:
        results = run_step_forward(TEST_CASE, trials=1)
        heuristic = results[-1]

        self.assertEqual(heuristic.candidate, "heuristic_only")
        self.assertEqual(
            heuristic.exact,
            heuristic.objective_gap <= 1e-10,
        )


if __name__ == "__main__":
    unittest.main()
