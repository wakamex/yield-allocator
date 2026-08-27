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
