# Optimization result evaluation

Question: Did my clever Quanta prompting produce a better answer than generic prompting?

Answer: There is no clear evidence that it did. The structured generic prompt scored slightly higher, and `optimize harder` was effectively tied with the Quanta prompt. The Quanta prompt produced a different strong proposal, but it did not materially improve overall response quality in this comparison.

How was this tested? A sealed judge compared four anonymized responses using only what each response said, without knowing which prompt produced it or how any proposal later performed.

## Summary

| Prompting strategy | Overall |
| --- | ---: |
| Actual: cross-domain analogy to the Quanta article and paper | 91.7 |
| Counterfactual 1: tryhard standalone structured expert review with required fields | 93.7 |
| Counterfactual 2: historical conversation followed by `try harder` | 65.9 |
| Counterfactual 3: historical conversation followed by `optimize harder` | 90.4 |

## Evaluation setup

The comparison used the six weighted dimensions below. Only the Quanta response was later implemented and benchmarked, so this report keeps those outcomes outside the ranking rather than treating absent results for the counterfactuals as failures. The saved artifacts are the [actual Quanta prompt](actual-quanta-prompt.md), [actual Quanta response](actual-quanta-response.md), [blind judge prompt](sealed-proposal-evaluation-prompt.md), [private candidate mapping](sealed-proposal-evaluation-mapping.md), [judge answer](sealed-proposal-evaluation-answer.md), and [raw AOP result](sealed-proposal-evaluation-aop-run/result.json).

## Scores

| Prompting strategy | Bottleneck fit, 20% | Exactness and correctness, 20% | Performance leverage, 20% | Actionability, 15% | Evidence and falsifiability, 15% | Generality, 10% | Overall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Actual: cross-domain analogy to the Quanta article and paper | 95 | 91 | 94 | 91 | 91 | 84 | 91.7 |
| Counterfactual 1: tryhard standalone structured expert review with required fields | 97 | 94 | 89 | 97 | 96 | 87 | 93.7 |
| Counterfactual 2: historical conversation followed by `try harder` | 88 | 82 | 35 | 38 | 73 | 82 | 65.9 |
| Counterfactual 3: historical conversation followed by `optimize harder` | 91 | 92 | 88 | 93 | 90 | 87 | 90.4 |

Overall is the weighted mean of the six dimensions.

## Actual: cross-domain analogy to the Quanta article and paper, 91.7/100

[Prompt](actual-quanta-prompt.md) | [Result](actual-quanta-response.md)

The response's reduced-cost rule is mathematically strong: at the evaluated dual price, forcing a nonbest branch reduces the valid upper bound by its branch gap, so branches exceeding the incumbent gap can be eliminated exactly. It directly addresses the reported input-order tail and has the highest expected scaling leverage because it could reduce both node count and repeated dual work.

The main risks are omitted numerical-tolerance conditions and an optimistic `O(n × 2^a)` characterization because the dangerous set and dual price can change below the root. A direct exhaustive safety test would strengthen it.

## Counterfactual 1: tryhard standalone structured expert review with required fields, 93.7/100

[Full prompt](counterfactual-1-prompt.txt) | [Response](counterfactual-1-response.md) | [Raw result](counterfactual-1-result.json)

### Prompt before repository details

```text
You are reviewing a historical snapshot of an exact optimization solver.
Propose the single highest-leverage next performance experiment based only on the repository snapshot below.

Constraints:
- Preserve exactness. Do not replace the exact solver with an approximate method.
- Use the existing benchmark evidence to identify the current limiting mechanism.
- Select one primary idea. Do not return an unranked menu of optimizations.
- Explain the mechanism concretely enough that another engineer could implement it.
- State the cheapest benchmark or counterfactual that could falsify the idea.
- State the main correctness risk and how to test it.
- Do not assume code, results, or research that is absent from this snapshot.

Return these fields:
1. Recommendation
2. Bottleneck evidence
3. Mechanism
4. Expected performance effect
5. Falsification test
6. Correctness test
```

This is the best-balanced response. It precisely targets the measured discrepancy between very few visited nodes and many dual iterations, preserves the existing tight bound for promising nodes, and proposes an exceptionally cheap instrumentation-only counterfactual before implementation.

Its early-pruning rule is sound provided segment maximization is a conservative upper bound and tolerances are handled safely. Its main limitation is that it primarily removes the price-search factor while each probe still scans the markets, so it may improve latency more than asymptotic scaling.

## Counterfactual 2: historical conversation followed by `try harder`, 65.9/100

[Full prompt](counterfactual-2-prompt.txt) | [Response](counterfactual-2-response.md) | [Raw result](counterfactual-2-result.json)

### Prompt before repository details

```text
Continue the historical conversation below. Treat the final User message as the current request. Base your response only on the conversation and repository snapshot included here.

Assistant:
Implemented, benchmarked, committed, and pushed.

- Cached segment algebra: 2.33x faster on the previous recommended configuration
- Attributed geo-mean speedup: 2.2382x
- New recommended runtime: 0.025668 seconds
- Total speedup over A0: 806.91x
- Newton remains disabled because it was 0.23% slower in the final configuration
- 25 tests pass and package builds succeed

User:
can we estimate how slow a 100-market solution would be, using the recommended result, by timeboxing a run and extrapolating?

Assistant:
For 20 deterministic stochastic 100-market all-crossing cases, each timeboxed at 10 seconds:

- Median: 0.0185 seconds
- Slowest initial run: 1.1747 seconds
- Slowest repeated median: 1.2078 seconds
- Timeouts: 0 of 20

Fourteen cases were certified optimal at the root node. The harder cases visited about 100 nodes and consistently took 1.1 to 1.2 seconds. Branch-and-bound runtime is irregular, so the 0.0257-second 20-market result cannot be extrapolated directly by market count.

User:
can we estimate our big-o scaling?

Assistant:
The useful scaling model is runtime = O(n^2 + K * n * V), where n is markets, K is outer price iterations capped at 64, and V is branch-and-bound nodes evaluated. If c markets cross their kink, V can be O(2^c), giving O(n * 2^c), or O(n * 2^n) when all markets cross.

Observed across 20 stochastic cases at each size:

| Markets | Median | p95 | Maximum nodes |
| ---: | ---: | ---: | ---: |
| 20 | 0.0232 s | 0.0712 s | 23 |
| 40 | 0.0084 s | 0.1942 s | 41 |
| 60 | 0.0114 s | 0.4235 s | 65 |
| 80 | 0.0153 s | 0.7566 s | 81 |
| 100 | 0.0175 s | 1.1551 s | 101 |

Typical sampled behavior is approximately O(n), sampled upper-tail behavior is approximately O(n^2), and the exact worst case remains O(n * 2^n).

User:
where does the extra n come from in the worst case

Assistant:
The extra n is the work at every branch-and-bound node. Each dual upper-bound evaluation scans all n markets during the common-price search, so each node costs O(n). The implementation also copies and scans an n-element segment-choice tuple when creating children. If bounds could be updated incrementally after each branching decision, node processing might approach O(1) or O(log n). The worst-case search would remain exponential, but it could become closer to O(2^n) or O(2^n log n).

User:
try harder
```

This is a useful complexity correction and correctly emphasizes that rescanning the portfolio, tuple and feasibility scans, and heap operations are distinct costs. However, it mostly diagnoses the problem rather than proposing a proportionate next experiment.

The assertion that removing the extra factor requires all three listed redesigns is too strong outside the exact current traversal and bound architecture. Its broad dynamic-dual requirement offers little guidance about feasibility or expected payoff.

## Counterfactual 3: historical conversation followed by `optimize harder`, 90.4/100

[Full prompt](counterfactual-3-prompt.txt) | [Response](counterfactual-3-response.md) | [Raw result](counterfactual-3-result.json)

### Prompt before repository details

```text
Continue the historical conversation below. Treat the final User message as the current request. Base your response only on the conversation and repository snapshot included here. This is a sealed analysis task: propose a change, but do not modify files, run commands, benchmark, commit, push, or ask for tools.

Assistant:
Implemented, benchmarked, committed, and pushed.

- Cached segment algebra: 2.33x faster on the previous recommended configuration
- Attributed geo-mean speedup: 2.2382x
- New recommended runtime: 0.025668 seconds
- Total speedup over A0: 806.91x
- Newton remains disabled because it was 0.23% slower in the final configuration
- 25 tests pass and package builds succeed

User:
can we estimate how slow a 100-market solution would be, using the recommended result, by timeboxing a run and extrapolating?

Assistant:
For 20 deterministic stochastic 100-market all-crossing cases, each timeboxed at 10 seconds:

- Median: 0.0185 seconds
- Slowest initial run: 1.1747 seconds
- Slowest repeated median: 1.2078 seconds
- Timeouts: 0 of 20

Fourteen cases were certified optimal at the root node. The harder cases visited about 100 nodes and consistently took 1.1 to 1.2 seconds. Branch-and-bound runtime is irregular, so the 0.0257-second 20-market result cannot be extrapolated directly by market count.

User:
can we estimate our big-o scaling?

Assistant:
The useful scaling model is runtime = O(n^2 + K * n * V), where n is markets, K is outer price iterations capped at 64, and V is branch-and-bound nodes evaluated. If c markets cross their kink, V can be O(2^c), giving O(n * 2^c), or O(n * 2^n) when all markets cross.

Observed across 20 stochastic cases at each size:

| Markets | Median | p95 | Maximum nodes |
| ---: | ---: | ---: | ---: |
| 20 | 0.0232 s | 0.0712 s | 23 |
| 40 | 0.0084 s | 0.1942 s | 41 |
| 60 | 0.0114 s | 0.4235 s | 65 |
| 80 | 0.0153 s | 0.7566 s | 81 |
| 100 | 0.0175 s | 1.1551 s | 101 |

Typical sampled behavior is approximately O(n), sampled upper-tail behavior is approximately O(n^2), and the exact worst case remains O(n * 2^n).

User:
where does the extra n come from in the worst case

Assistant:
The extra n is the work at every branch-and-bound node. Each dual upper-bound evaluation scans all n markets during the common-price search, so each node costs O(n). The implementation also copies and scans an n-element segment-choice tuple when creating children. If bounds could be updated incrementally after each branching decision, node processing might approach O(1) or O(log n). The worst-case search would remain exponential, but it could become closer to O(2^n) or O(2^n log n).

User:
Optimize harder. Propose one concrete change, explain how it works, and describe how to evaluate it.
```

Its strongest feature is the clean observation that a fixed-price Lagrangian value remains a valid upper bound and can be updated incrementally, coupled with a sensible isolated ablation. It could remove almost all repeated dual work and several linear node-management costs.

Its main risk is selectivity: using the root price throughout the tree may loosen bounds enough to increase node count substantially, so the attractive complexity reduction is conditional.

## Ranking

1. Counterfactual 1: tryhard standalone structured expert review with required fields, 93.7
2. Actual: cross-domain analogy to the Quanta article and paper, 91.7
3. Counterfactual 3: historical conversation followed by `optimize harder`, 90.4
4. Counterfactual 2: historical conversation followed by `try harder`, 65.9

The judge treated the actual result and counterfactual 3 as effectively tied despite their 1.3-point difference. Counterfactual 1's lead over the actual result is modest and could reverse if the worst tail is dominated by walking through stable markets rather than repeated price searches. Counterfactual 2 is clearly separated because it lacks an actionable, cheap counterfactual.
