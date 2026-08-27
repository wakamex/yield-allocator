1. Recommendation

Add a cutoff-aware Lagrangian-bound fast path: evaluate each child at its parent’s dual price and immediately prune when that single evaluation is already below the incumbent cutoff. Only run the full 64-iteration dual-price search when the cheap bound cannot certify pruning.

2. Bottleneck evidence

The recommended solver visits only 7 nodes and performs one fixed-region solve, yet still executes 908 outer iterations and 37,569 marginal evaluations. The heuristic-only run needs just 97 outer iterations and 3,525 marginal evaluations and is 10.54× faster.

`_lagrangian_bound` always performs up to 64 price iterations, even for children that will ultimately be pruned. The roughly 811 additional outer iterations after heuristic initialization correspond to about 13 full dual searches. Thus the remaining cost is bound computation, not enumeration or solving feasible leaves.

3. Mechanism

Refactor the nested `evaluate(price)` logic into a reusable function returning the Lagrangian value

\[
pB+\sum_i \max_{s\in S_i,\ x\in s}(f_i(x)-px).
\]

This is a valid upper bound at every price; price minimization only tightens it.

Make `upper_bound` retain the `_DualResult.price`. When branching:

- Evaluate the child options once at the parent’s price.
- If that bound is at most `best_income + tolerance`, prune immediately.
- Otherwise run the existing full `_lagrangian_bound` and store its resulting price with the queued child.
- During that full search, optionally return early as soon as any evaluated dual value proves the same cutoff.

Do not use cutoff termination for the initial heuristic relaxation because it needs the selected segments and a useful price.

4. Expected performance effect

This targets most of the gap between the 25.668 ms exact run and the 2.440 ms heuristic-only run. Pruned children could fall from roughly 64 price evaluations to one. Promising nodes still pay the current cost, so a several-fold improvement is plausible; the observed 10.54× heuristic-only gap is the opportunity ceiling, not an expected guaranteed speedup.

5. Falsification test

On `all_crossing_20.toml`, run one recommended-config trial while instrumenting every child bound with a parent-price probe, without changing pruning decisions. Count how many probes already satisfy the incumbent cutoff and estimate the avoided outer iterations.

Falsify the idea if few of the approximately 13 post-heuristic dual searches can be certified early, or if a toggle benchmark does not materially reduce outer iterations, marginal evaluations, and median solve time.

6. Correctness test

The main risk is numerical underestimation of a segment’s maximized Lagrangian value, causing an invalid early prune near the incumbent.

For randomized small problems, both profiles, allocation caps, and deliberately near-tied markets:

- Compare the new solver’s objective against A0 exhaustive enumeration.
- For every node early-pruned by the new path, exhaustively solve all descendant region combinations and assert their best income is no greater than the recorded bound within the solver’s tolerance.
- Retain the existing feasibility and budget-sum checks.

This directly tests the safety property required by the new pruning rule.
