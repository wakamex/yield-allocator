# Sealed proposal evaluation

You are judging four anonymized candidate responses produced from the same historical solver discussion.

The common objective is to identify the strongest direction for improving an exact allocation solver's branch-tail latency and scaling. Exactness must be preserved.

Evaluate every candidate ex ante using only its response text. Do not assume that any proposal was implemented. Do not infer or reward which response was actually used. Do not use later benchmark outcomes, commits, prompt wording, provenance, or candidate order as evidence. Historical measurements mentioned inside a candidate may support its diagnosis, but claimed future benefits remain predictions.

Score each candidate from 0 to 100 on:

- Bottleneck fit, weighted 20 percent
- Exactness and technical soundness, weighted 20 percent
- Expected performance leverage, weighted 20 percent
- Actionability, weighted 15 percent
- Evidence and falsifiability, weighted 15 percent
- Generality and robustness, weighted 10 percent

Compute overall as the weighted mean. Apply the same standard to all candidates. Penalize unsupported complexity claims, missing correctness conditions, broad redesigns without a cheap counterfactual, and diagnoses that do not yield a proportionate next experiment. Do not penalize a response merely because it proposes more than one method when the methods are separable and prioritized.

Return:

1. A score table with every dimension and overall.
2. A ranking, including ties when differences are not meaningful.
3. One concise paragraph per candidate explaining its strongest feature, main risk, and score.
4. A short calibration note stating which score differences are uncertain.
5. Plain-text equations only. Do not use LaTeX.


## Candidate A

The concrete change I’d try is an incremental fixed-price Lagrangian bound.

Today every branch-and-bound child reruns `_lagrangian_bound`, performing up to 64 price iterations and scanning every market each time. Instead, solve the dual once at the root price \(\lambda\) and retain each market’s contribution:

\[
q_i(\lambda)=\max_{s\in S_i,\ x\in s}\left(f_i(x)-\lambda x\right)
\]

The root upper bound is:

\[
U(\lambda)=\lambda B+\sum_i q_i(\lambda)
\]

When a child fixes market \(j\) to segment \(s\), its valid upper bound is available in constant time:

\[
U_{\text{child}}(\lambda)
=U_{\text{parent}}(\lambda)-q_j(\lambda)+q_{j,s}(\lambda)
\]

This remains an exact branch-and-bound algorithm: any fixed-price Lagrangian value is a valid upper bound. Minimizing over price only makes the bound tighter; it is not required for correctness.

Implementation-wise, `_DualResult` would retain the per-segment contributions at its chosen price. Search nodes would use bitmasks plus incrementally updated lower/upper capacity sums, avoiding the current \(n\)-element tuple copies and `bounds()` scans. Fixed-region solving would still happen at feasible leaves.

If the fixed-price bound remains selective, traversal changes from approximately \(O(KnV)\) to \(O(Kn + V\log V)\), with the root dual solve providing the \(Kn\) term. The formal worst case remains exponential, and feasible leaves still cost \(O(n)\); the risk is that the cheaper bound is looser and increases \(V\).

I would evaluate it as an isolated `incremental_dual_bounds` ablation:

- Verify objectives against A0 for thousands of deterministic all-crossing cases through 10–12 markets, including caps and kink-boundary cases.
- Run paired current-versus-new benchmarks at 20, 40, 60, 80, and 100 markets using identical seeds.
- Separately report the previously observed hard 100-market cases, since root-certified cases will hide the improvement.
- Record runtime, nodes, fixed solves, marginal evaluations, heap size, and new counters for incremental bound evaluations and full dual solves.
- Promote it only if exactness is unchanged and the 100-market p95 improves without a compensating explosion in nodes.

The key success signal would be full dual solves falling from roughly one per generated child to one per overall solve, while node counts remain near their current values.

## Candidate B

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

## Candidate C

Correct: the ablations improved practical scaling enormously, but they did not improve the adversarial Big-O bound.

The useful idea from the spectral-independence work is to identify a small dangerous set and freeze everything else. We can do that here with a simpler, deterministic, exact test.

Exact dual-gap fixing

At a dual price `p`, calculate for each market and branch:

`branch value = maximum of income(x) - p*x within that branch`

Let:

- `U` be the portfolio dual upper bound
- `L` be the best feasible income found
- `d_i` be the difference between market `i`’s best and second-best branches

If:

`U - d_i <= L`

then choosing the second branch cannot beat the incumbent. We can eliminate it exactly without solving that child node.

Only markets satisfying:

`d_i < U - L`

remain dangerous.

The 100-market evidence is unusually strong:

- 14 of 20 cases had zero dangerous markets and were certified at the root.
- The remaining six cases each had exactly one dangerous market at the root.
- The current solver branches in input order, so it sometimes walked through 15, 29, 60, or 99 markets before reaching that market.

This explains the quadratic tail. We are repeatedly proving that obviously stable branches are stable.

If we branch directly on the dangerous market, those sampled cases could plausibly require a constant number of dual evaluations. Since each evaluation costs `O(n)`, their observed scaling could move from `O(n²)` toward `O(n)`.

Connection to affine spectral independence

| Spectral-independence work | Our solver |
| --- | --- |
| Starts with fractional binary choices | Starts with a Lagrangian relaxation of kink choices |
| Measures joint discrepancy dependence | Measures branch dependence through the common price |
| Blocks stable constraints | Can fix branches whose reduced cost exceeds the dual gap |
| Continues with dangerous coordinates | Can branch only on near-tied markets |
| Needs an SDP because many constraints interact | Has one budget constraint and one scalar price |

The principle transfers, but the SDP machinery does not. Their problem has many overlapping balance constraints. Our market interactions are mediated by one common price, making exact reduced-cost analysis simpler and stronger.

A more useful scaling parameter

Instead of counting all `c` crossing markets, define `a` as the number of markets that survive dual-gap fixing.

The useful output-sensitive target becomes approximately:

`O(n × 2^a)`

The adversarial case still has `a = n`, so worst-case scaling remains `O(n × 2^n)`. But our sampled 100-market cases had `a` equal to zero or one at the root.

Another structural bound comes from kink allocations. Every crossed market consumes at least its kink allocation. Therefore, any feasible crossed set must satisfy:

`sum of crossed kink allocations <= budget`

If every kink requires at least a fraction `alpha` of the budget, no solution can cross more than `floor(1 / alpha)` markets. This gives a fixed-parameter alternative to treating every market as independently binary.

Recommended next ablations

I would implement these separately:

1. `dual_reduced_cost_fixing`
   - Eliminate branches using `U - d_i <= L`.
   - Avoid child dual solves for eliminated branches.
   - Preserve exactness.

2. `dual_ambiguity_branching`
   - Branch on the surviving market with the smallest branch gap.
   - Preserve exactness.
   - Test whether the 100-market p95 changes from quadratic toward linear.

Track dangerous-market count, branches fixed, avoided dual solves, nodes, and runtime. This is the clearest insight from the paper that maps to our solver.

The referenced work supports the dangerous-set design principle, but it does not directly solve our allocation problem. The exact reduced-cost rule above comes from our one-price dual structure and should be much cheaper than affine spectral independence.

## Candidate D

The earlier answer was incomplete, and the suggestion that incremental bounds could yield `O(2^n log n)` was wrong.

For the recommended solver, let:

- `n` = total markets
- `c` = markets with two possible kink regions
- `V` = branch-and-bound nodes generated
- `K ≤ 64` = price-search iterations

The runtime is more accurately:

\[
T = O(n^2 + V(Kn + n + \log V))
\]

With fixed numerical precision, `K` is constant:

\[
T = O(n^2 + V(n+\log V))
\]

The dominant extra `n` comes from `_lagrangian_bound` in [solver.py](/workspace/src/yield_allocator/solver.py). At every trial price, it must evaluate

\[
pB+\sum_{i=1}^{n}
\max_{s\in options_i}\max_x(f_{i,s}(x)-px)
\]

That sum scans every market. Fixing one market’s branch changes only one summand, but it also changes the minimizing common price `p`, so the bound cannot be updated by merely adding or subtracting one cached scalar. The entire portfolio response is currently recomputed at each node.

There are additional linear costs per node:

- copying the `n`-element options tuple for each child;
- recomputing lower and upper feasibility sums across all `n` markets;
- scanning for the next branch index.

Best-bound traversal adds `O(log V)` heap work. If `V=2^c`, then `log V=c`; for `c=n`, that is another `O(n)` per node. Thus even with an O(1) dual-bound update, the current heap would still contribute `O(n2^n)`. My earlier `O(2^n log n)` claim confused `log V` with `log n`.

Consequently:

\[
V \le 2^{c+1}-1
\]

and

\[
T = O(n^2+n2^c)
\]

For `c=n`, a full-tree run is `Θ(n2^n)` for this implementation. The observed hard cases had `V≈n`, explaining the sampled `O(n²)` tail: roughly `n` nodes times `n` markets per bound.

One further caveat: the benchmark generator forces every kink allocation to be at least `0.05B`. Therefore at most 20 low-region choices can coexist feasibly. Holding that 5% floor fixed while increasing `n`, this generated family is not asymptotically `2^n`; feasibility limits it to a high-degree polynomial tree. The general solver remains exponential because real inputs may have arbitrarily small positive kink allocations.

Actually removing the extra `n` would require all three:

1. Persistent nodes with incremental feasibility bounds.
2. A dynamic representation of the aggregate dual function that supports one-market branch changes without rescanning every market.
3. Either abandoning the binary heap for constant-time traversal or accepting its `O(c)` worst-case cost.

So the extra `n` is not merely tuple-copy overhead. It is principally the global common-price dual solve, with the best-bound heap independently restoring the same factor in the exponential case.
