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
