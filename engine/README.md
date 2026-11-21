# FutureFork Optimization & Simulation Engine

> **The Golden Rule**: AI agents interpret and explain. Mathematical models calculate and validate. The LLM never produces a number that ends up on screen. Every number comes from the solver, the metric engine or the simulator.

The engine is a pure Python package with no dependencies on HTTP, databases or LLMs. Given a 12-month cash-flow baseline and a purchase goal, it applies one of four fork strategies, solves for the best schedule with Google OR-Tools CP-SAT, computes deterministic risk metrics, and stress-tests the result with a 300-run vectorized NumPy Monte Carlo simulation.

---

## 1. Domain Model ([`model.py`](model.py))

| Type | What it holds |
|---|---|
| `FinancialProblemInstance` | Node 0 baseline: 12 months × 8 categories of outflows, 12 monthly inflows, starting balance, each category's fixed/flexible tag and its historical mean and standard deviation |
| `PurchaseGoal` | The decision: total cost, emergency floor, target month, financing mode, EMI months, interest rate, phased splits, maximum trim % and flexible categories |
| `MonthlyCashSchedule` | One month of a solved plan: inflow, base and trimmed outflow, purchase cash-out, closing balance, floor breach |
| `ScenarioEvaluationResult` | One evaluated branch: 12 schedules, category trims, metrics, solver metadata and Monte Carlo results |

The baseline is compiled from CSV by [`data/ingestor.py`](../data/ingestor.py). Categories are consolidated to exactly 8 (the top 7 by spend plus "Other / Discretionary") and tagged `fixed` (salaries, rent, utilities, ...) or `flexible`.

---

## 2. Cash-Flow Model

For every branch the solver enforces the monthly balance recursion

$$B_t = B_{t-1} + \text{Inflow}_t - \text{Outflow}_t - \text{Purchase}_t + \text{Trim}_t, \qquad B_{-1} = B_0$$

and a deficit variable $D_t \ge F - B_t$, $D_t \ge 0$ against the emergency floor $F$. Each fork minimizes total floor deficit first and a fork-specific secondary term second. The floor is a soft constraint, so the solver always returns the least-bad plan instead of `INFEASIBLE`.

---

## 3. The Four Forks ([`changes.py`](changes.py), [`solver.py`](solver.py))

| Fork | Transformer | CP-SAT decision | Secondary objective |
|---|---|---|---|
| **Upfront** | `apply_upfront` | Purchase month $p$ (one-hot over 12 months) | Smallest delay from the target month |
| **EMI** | `apply_emi_split` | Instalment start month for an $N$-month plan with annual interest and optional down payment | Stay close to the target month |
| **Phased** | `apply_phased_delay` | Month of the second tranche (default 50/50 split, no interest) | Prefer an earlier second phase |
| **Trim** | `apply_discretionary_trim` | Cut $z_c \in [0, \text{max\_trim}]$ per flexible category (default up to 35%); fixed categories are never cut | Minimum weighted "pain" of cuts |

`normalize_branch_type` maps aliases (`phased_delay`, `discretionary_trim`, `lease`, ...) to the four canonical types and rejects anything else.

**Known limitation:** Trim & Buy always buys in the target month, while Upfront may move the purchase to the safest month. Trim can therefore end with a lower minimum balance than Upfront.

---

## 4. Metrics ([`metrics.py`](metrics.py))

| Metric | Definition |
|---|---|
| `lowest_balance`, `lowest_balance_month` | Minimum closing balance over the 12 months and when it occurs |
| `months_below_floor` | Months whose closing balance is below the emergency floor |
| `runway_months` | Ending balance ÷ average monthly outflow |
| `total_purchase_cost`, `total_financing_interest`, `total_trims_saved` | Cost breakdown of the plan |
| `cash_out_risk_pct` | Share of Monte Carlo runs whose balance goes below ₹0 |
| `floor_breach_risk_pct` | Share of runs that breach the emergency floor |
| `p10_lowest_balance` (`p10_worst_balance` in the API) | 10th-percentile lowest balance across runs |
| `survival_score_pct` | Composite 5–100 score: 100 when no run breaches the floor or goes below ₹0, reduced by breach risk, cash-out risk and deficit depth |

---

## 5. Monte Carlo Simulation ([`simulator.py`](simulator.py))

Each solved schedule is replayed 300 times (vectorized `(runs, 12, categories)` arrays, seeded for reproducibility) with three shocks:

1. **Inflow delay**: about 20% of runs have 40–85% of one month's inflow slip to the next month.
2. **Emergency outflow**: each month has a 5% chance of an unexpected expense sized from the dataset's typical outflow.
3. **Category drift**: flexible categories get Gaussian spend multipliers based on their historical coefficient of variation (clipped to 0.70–1.45).

The simulator returns the risk metrics above plus a monthly P10/P50/P90 balance band for the UI's confidence ribbon.

---

## 6. Public API

```python
from data.loader import load_sample_instance
from engine.model import PurchaseGoal
from engine.solver import evaluate_financial_branch, solve_all_financial_scenarios

instance = load_sample_instance("personal_upi.csv")
goal = PurchaseGoal(item_name="Laptop", total_cost=120_000, emergency_floor=30_000)

# One branch end to end: transformer -> CP-SAT -> Monte Carlo (used by the backend)
emi = evaluate_financial_branch(instance, "emi", goal, n_sims=300, seed=42)

# Baseline + all four forks in one call
results = solve_all_financial_scenarios(instance, goal)
```

`evaluate_financial_branch` raises on invalid input (unknown fork type, zero cost) rather than returning placeholder numbers.
