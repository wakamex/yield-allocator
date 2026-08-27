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
