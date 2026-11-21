# 🌟 FutureFork Good First Issues

Beginner-friendly and intermediate issues across the engine, AI layer, backend and frontend. Several are real bugs found while connecting the UI to the live engine.

---

### 1. 🐛 Explainer drops the minus sign on negative balances
- **Area**: `ai/agents/explainer.py`
- **Difficulty**: Beginner
- **Problem**: For an unaffordable plan, the template explanation says "min balance=₹17.62L" when the balance is **-₹17.62L**. The Numeric Guard compares absolute values, so it doesn't catch this.
- **Definition of Done**: Negative balances render with a minus sign, and the guard rejects a sign mismatch. Add a test in `ai/evals/test_prompts.py`.

---

### 2. 🐛 Parser misses "keeping ₹X in reserve"
- **Area**: `ai/agents/parser.py`
- **Difficulty**: Beginner
- **Problem**: *"Buy ₹12L of GPU servers on EMI while keeping ₹20L in reserve"* parses the emergency floor as ₹0. Only phrasings like "without dropping below ₹X" are recognised.
- **Definition of Done**: "keeping/keep/maintain ₹X in reserve/savings/the bank" sets the floor. Add regression prompts to the eval suite.

---

### 3. ⚖️ Let Trim & Buy choose its purchase month
- **Area**: `engine/solver.py` (`solve_trim_branch`)
- **Difficulty**: Intermediate
- **Problem**: Trim always buys in the target month, while Upfront may move the purchase to a safer month, so Trim can end up worse than Upfront (for example, the ₹2L vacation on the personal sample).
- **Definition of Done**: Trim jointly optimizes purchase month and cuts. Test: Trim's minimum balance is never below Upfront's for the same goal.

---

### 4. 🎛️ Make the Crisis Playground engine-backed
- **Area**: `frontend/src/components/ComparisonDashboard.tsx`, `backend/api/routes.py`, `engine/simulator.py`
- **Difficulty**: Intermediate
- **Problem**: The stress sliders estimate survival scores in the browser with a hand-written formula, which bends the Golden Rule.
- **Definition of Done**: Sliders call an endpoint that re-runs the Monte Carlo simulation with the chosen shock parameters (inflow delay, surprise outflow, drift).

---

### 5. 🌿 Custom branch UI
- **Area**: `frontend/`
- **Difficulty**: Beginner
- **Goal**: `POST /scenarios/{id}/branch` already evaluates a user-defined child fork (e.g. "EMI, but 6 months"). Add a "Branch from here" action on scenario cards.
- **Definition of Done**: A child card appears under its parent with engine results.

---

### 6. 📤 Export the winning plan
- **Area**: `frontend/src/components/ComparisonDashboard.tsx`
- **Difficulty**: Beginner
- **Goal**: Export the selected fork's 12-month schedule (inflows, category outflows, purchase cash-out, closing balance) as CSV.
- **Definition of Done**: The downloaded file matches `cash_flow` and `simulation.monthly_balances` exactly.

---

### 7. 🧾 New fork type: lease-to-own
- **Area**: `engine/changes.py`, `engine/solver.py`, `ai/agents/scenario.py`
- **Difficulty**: Intermediate
- **Goal**: Add a fifth strategy with monthly lease payments and an optional buy-out at month N. Follow "Adding a New Fork Type" in the README.
- **Definition of Done**: The fork appears in the UI with solver-verified metrics and tests.

---

### 8. 📈 Longer horizons
- **Area**: `data/ingestor.py`, `engine/`
- **Difficulty**: Advanced
- **Goal**: Support 24-month horizons (currently fixed at 12 months).
- **Definition of Done**: Horizon is configurable end to end; all tests pass for 12 and 24.

---

### 9. 🗄️ Database migrations
- **Area**: `backend/db/`
- **Difficulty**: Intermediate
- **Goal**: Add Alembic so schema changes don't require deleting the local SQLite database.
- **Definition of Done**: `alembic upgrade head` creates the current schema; CI runs it.

---

### 10. 🔔 Webhook on run completion
- **Area**: `backend/orchestration/runner.py`, `backend/settings.py`
- **Difficulty**: Beginner
- **Goal**: Optional `WEBHOOK_URL` receives a JSON summary when a decision run finishes.
- **Definition of Done**: Payload includes each fork's survival score, cash-out risk and lowest balance.
