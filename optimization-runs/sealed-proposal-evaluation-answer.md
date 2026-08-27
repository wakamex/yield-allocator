Overall = 0.20 Bottleneck fit + 0.20 Exactness + 0.20 Performance leverage + 0.15 Actionability + 0.15 Evidence + 0.10 Generality.

| Candidate | Bottleneck fit | Exactness / soundness | Performance leverage | Actionability | Evidence / falsifiability | Generality / robustness | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 91 | 92 | 88 | 93 | 90 | 87 | 90.4 |
| B | 97 | 94 | 89 | 97 | 96 | 87 | 93.7 |
| C | 95 | 91 | 94 | 91 | 91 | 84 | 91.7 |
| D | 88 | 82 | 35 | 38 | 73 | 82 | 65.9 |

Ranking

1. Candidate B
2. Candidates C and A — effectively tied
4. Candidate D

Candidate A: Its strongest feature is the clean observation that a fixed-price Lagrangian value remains a valid upper bound and can be updated incrementally, coupled with a sensible isolated ablation. It could remove almost all repeated dual work and several linear node-management costs. Its main risk is selectivity: using the root price throughout the tree may loosen bounds enough to increase the node count substantially, so the attractive complexity reduction is conditional. Score: 90.4.

Candidate B: This is the best-balanced proposal. It precisely targets the measured discrepancy between very few visited nodes and many dual iterations, preserves the existing tight bound for promising nodes, and proposes an exceptionally cheap instrumentation-only counterfactual before implementation. Its early-pruning rule is sound provided segment maximization is a conservative upper bound and tolerances are handled safely. Its main limitation is that it primarily removes the K factor; each probe still scans the markets, so it may improve latency more than asymptotic scaling. Score: 93.7.

Candidate C: Its reduced-cost rule is mathematically strong: at the evaluated dual price, forcing a nonbest branch reduces the valid upper bound by its branch gap, so branches exceeding the incumbent gap can be eliminated exactly. It directly addresses the reported input-order tail and could reduce both node count and repeated dual work, giving it the highest scaling leverage. The main risks are omitted numerical-tolerance conditions and an optimistic O(n × 2^a) characterization, since the dangerous set and dual price can change below the root. A direct exhaustive safety test would strengthen it. Score: 91.7.

Candidate D: This is a useful complexity correction and correctly emphasizes that rescanning the portfolio, tuple and feasibility scans, and heap operations are distinct costs. However, it mostly diagnoses the problem rather than proposing a proportionate next experiment. The assertion that removing the extra factor requires all three listed redesigns is also too strong outside the exact current traversal and bound architecture. Its broad dynamic-dual requirement offers little guidance about feasibility or expected payoff. Score: 65.9.

Calibration note: B’s lead over C is modest and could reverse if the worst tail is dominated by walking through stable markets rather than repeated price searches. A and C are within normal scoring uncertainty: C has greater potential scaling leverage, while A has a cleaner implementation and validation plan. D is clearly separated because it lacks an actionable, cheap counterfactual.
