# FutureFork 🍴

> **Simulate &gt; Compare &gt; Decide.**
> *Not just what to do, but what could happen if you choose differently.*

[![Elite Coders CodeSprint 2026](https://img.shields.io/badge/CodeSprint-2026_Finalist-blueviolet?style=for-the-badge)](https://github.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge)](https://python.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=for-the-badge)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/Frontend-React_18_+_Vite-61DAFB.svg?style=for-the-badge)](https://react.dev)
[![OR-Tools](https://img.shields.io/badge/Optimization-Google_OR--Tools-FF6F00.svg?style=for-the-badge)](https://developers.google.com/optimization)

**Team FutureLabs** | Elite Coders CodeSprint 2026
*Idea &rarr; MVP &rarr; Open Source &rarr; Pitch*

---

## 🌟 What is FutureFork?

Big purchases are where cash-flow plans quietly break. A college buys 40 GPU lab PCs, a startup hires two senior engineers, a person takes a ₹1.2L laptop on EMI, and three months later the reserve is gone because a fee payment came in late.

**FutureFork** turns a plain-English spending decision into a set of financially rigorous alternatives, evaluated against **your own transaction history**:

1. **Upload a CSV**: a bank or UPI statement, an institute ERP ledger, or a startup P&L. FutureFork proposes a column mapping, you confirm it, and it compiles a 12-month cash-flow baseline (**Node 0**).
2. **Describe the decision**: *"Buy 40 GPU lab PCs for ₹60L without dropping below ₹25L treasury reserve."* Indian notation (₹, lakh, crore, k) is understood natively.
3. **Fork into four strategies**: the decision is branched into competing ways to pay for it (Upfront, EMI, Phased, Trim & Buy).
4. **Solve and stress-test**: Google OR-Tools CP-SAT finds the best schedule for each fork that respects your emergency floor. A vectorized NumPy Monte Carlo engine then replays it 300 times under shocks such as late income, emergency expenses and spending drift.
5. **Compare and decide**: explore the forks on an interactive scenario tree, inspect month-by-month cash-flow matrices, and read an AI explanation whose numbers are verified against the engine output.

### Who it's for

| User type | Typical input | Example decision |
|---|---|---|
| **Individual** | Bank / UPI statement | *"Buy a ₹1.2L laptop on 12-month EMI without dropping below ₹30k emergency savings"* |
| **Institute** | College ERP expense ledger | *"Buy 40 GPU lab PCs for ₹60L without dropping below ₹25L treasury reserve"* |
| **Startup** | P&L / burn CSV | *"Hire 2 senior engineers at ₹20L/yr CTC each without extending runway below 6 months"* |

### 🛡️ The Golden Rule

> **AI agents interpret and explain. Mathematical models calculate and validate.**
> The LLM never invents, estimates, or changes a number shown on screen. Every balance, risk percentage, interest figure and runway estimate comes from **Google OR-Tools CP-SAT**, the deterministic metric engine, or the **NumPy Monte Carlo simulator**. An automated **Numeric Guard** checks every number in an AI explanation against the computed facts and rejects any explanation that doesn't match.

---

## 🍴 The Four Forks

Every decision is evaluated against **Node 0 (Baseline)**, your historical 12-month trajectory with no purchase, and four strategies:

| Fork | Strategy | What the solver decides |
|---|---|---|
| **A: Upfront** | Pay 100% in one month, zero interest | The earliest month the full payment fits without breaching the emergency floor |
| **B: EMI / Lease** | Spread the cost over 3–12 instalments with an annual financing rate | Instalment schedule, optional down payment, and total interest cost |
| **C: Phased** | Split the purchase into milestones (default 50/50) with no debt | Tranche timing aligned with inflow peaks |
| **D: Trim & Buy** | Cut flexible spending categories (capped, default 35%) | The minimum-pain cut per flexible category. Fixed categories such as salaries, rent and utilities are never touched |

### Metrics per fork

All metrics come from [`engine/metrics.py`](engine/metrics.py) and [`engine/simulator.py`](engine/simulator.py):

- **Lowest balance** and the month it occurs
- **Months below the emergency floor**
- **Cash-out risk (%)**: the probability of the balance going below ₹0 across the Monte Carlo runs
- **Survival score (%)**: a composite of solvency and how well the emergency floor is preserved
- **P10 / P50 / P90 lowest balance**: the worst-case, typical and best-case balance troughs
- **Runway (months)**: how long the ending balance lasts at the average monthly burn
- **Total purchase cost, financing interest and trim savings**

### Monte Carlo shocks (300 runs per fork)

1. **Inflow delay**: revenue, fees or salary slips from month *t* to *t+1*.
2. **Emergency outflow**: unexpected repair, medical or capital expenses.
3. **Category drift**: Gaussian spending drift on flexible categories, sized from each category's historical volatility.

---

## 🏗️ System Architecture

```
+---------------------------------------------------------------------------------+
|                        FRONTEND (React 18 + TypeScript + Vite)                  |
|   - UploadIngestor: CSV upload, column-mapping review, Node 0 commit            |
|   - DecisionInput: plain-English decision prompt                                |
|   - ScenarioTree: baseline + 4 fork cards with live solve status                |
|   - CashFlowMatrix: month-by-month balances vs. emergency floor                 |
|   - ComparisonDashboard: 4-fork side-by-side risk & cost comparison             |
|   - ExplanationPanel: AI narrative checked by the Numeric Guard                 |
+---------------------------------------+-----------------------------------------+
                                        | REST API / JSON
+---------------------------------------v-----------------------------------------+
|                           BACKEND (FastAPI + SQLAlchemy)                        |
|   - Routes: /datasets/inspect, /datasets/commit, /decisions, /run, /compare     |
|   - Orchestration: background runner, per-fork status, result cache            |
|   - Storage: SQLite (local) / PostgreSQL via Supabase (cloud)                   |
+--------------------+------------------------------------+-----------------------+
                     |                                    |
+--------------------v-------------+     +----------------v-----------------------+
|          AI LAYER                |     |   OPTIMIZATION & SIMULATION ENGINE     |
|   - Mapper: CSV column mapping   |     |   - Ingestor: CSV -> 12-month instance |
|   - Parser: ₹ / lakh / crore NLP |     |   - Change appliers: 4 fork transforms |
|   - Scenario: 4-fork (LangGraph) |     |   - CP-SAT cash-flow solver            |
|   - Explainer + Numeric Guard    |     |   - Vectorized NumPy Monte Carlo (300) |
|   (LLM optional; regex fallback) |     |   - Deterministic risk metrics         |
+----------------------------------+     +----------------------------------------+
```

**Layer boundaries**

- **Engine** (`engine/`, `data/ingestor.py`): pure Python. It never calls HTTP, a database or an LLM.
- **AI layer** (`ai/`): parses text and explains results. It is not allowed to compute or modify metrics. Every agent has a deterministic regex/template fallback, so the app works fully offline without an API key.
- **Backend** (`backend/`): the coordinator. It holds state, runs background jobs and caches results. If the engine can't evaluate a fork, that fork is marked `failed`; the backend never substitutes placeholder numbers.
- **Frontend** (`frontend/`): talks to the backend only through the REST API. It can also run on labelled placeholder data for UI-only work.
- **Contracts** (`contracts/`): [`schemas.py`](contracts/schemas.py) is the source of truth and is enforced as FastAPI response models. [`types.ts`](contracts/types.ts) mirrors it, and [`openapi.json`](contracts/openapi.json) is generated with `python scripts/export_openapi.py`.

---

## 🔁 Request Flow

| Step | Endpoint | What happens |
|---|---|---|
| 0 | `GET /datasets` | List datasets, including the three bundled samples seeded on startup |
| 1 | `POST /datasets/inspect` | Upload a CSV. Returns the proposed column mapping, a 5-row preview and an `upload_id` (15-minute TTL) |
| 2 | `POST /datasets/commit` | Confirm or edit the mapping. Compiles the 12-month **Node 0** baseline |
| 3 | `POST /decisions` | Parse the plain-English decision into a structured spec |
| 4 | `POST /decisions/{id}/scenarios` | Generate the baseline plus the 4 forks |
| 5 | `POST /decisions/{id}/run` | Dispatch CP-SAT and Monte Carlo evaluation in the background |
| 6 | `GET /runs/{run_id}` | Poll progress and per-fork status |
| 7 | `GET /decisions/{id}/compare` | Side-by-side results plus the guarded AI explanation |
| 8 | `POST /scenarios/{id}/branch` | Branch a child fork off any scenario |

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** with **pnpm** or npm
- *Optional*: Docker with Docker Compose

### Option A: Docker Compose

```bash
git clone https://github.com/team-futurelabs/futurefork.git
cd futurefork
docker compose up --build
```

- Web app: [http://localhost:5173](http://localhost:5173)
- API and interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Option B: Local development

#### 1. Backend & Engine

```bash
git clone https://github.com/team-futurelabs/futurefork.git
cd futurefork

python -m venv venv
source venv/bin/activate            # Windows: .\venv\Scripts\activate
pip install -r backend/requirements.txt

cp .env.example .env                # optional: add OPENAI_API_KEY or GROQ_API_KEY
python backend/main.py              # http://localhost:8000
```

On first start the backend creates its SQLite database and seeds the three sample datasets.

No API key? No problem. Without `OPENAI_API_KEY` or `GROQ_API_KEY`, every AI agent falls back to deterministic regex parsing and template explanations.

#### 2. Frontend

```bash
cd frontend
cp .env.example .env
pnpm install                        # or: npm install
pnpm dev                            # http://localhost:5173
```

The frontend talks to the live backend by default. For UI-only work without a backend, set `VITE_USE_MOCKS=true`; the header then shows a **Mock data** badge, and every number is a placeholder.

### Sample datasets

The three CSVs in [`data/samples/`](data/samples/) are ready to use from the **Upload & Build** tab, with no upload needed:

| Dataset id | File | Represents |
|---|---|---|
| `sample_personal` | `personal_upi.csv` | An individual's 12-month bank / UPI statement |
| `sample_institute` | `institute_erp_1.8cr.csv` | A college ERP expense ledger (~₹1.8 Cr annual budget), running at a deficit |
| `sample_startup` | `startup_pnl.csv` | A startup P&L / burn statement, burning cash |

Regenerate them with `python data/make_finance_samples.py`.

---

## ⚙️ Configuration

Set these in `.env` at the repo root (see [`.env.example`](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` hides exception details in API error responses |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Comma-separated allowed frontend origins (`*` allows any origin, without credentials) |
| `DATABASE_URL` | `sqlite:///./futurefork.db` | SQLite locally, or a Postgres/Supabase connection string |
| `OPENAI_API_KEY` / `GROQ_API_KEY` | *(empty)* | Optional LLM for mapping, parsing and explanations |
| `FUTUREFORK_OFFLINE` | *(unset)* | `1` forces the offline regex/template agents even when a key is set |
| `NUM_SIMULATION_RUNS` | `300` | Monte Carlo runs per fork |
| `RANDOM_SEED` | `42` | Seed for reproducible simulations |
| `CACHE_ENABLED` | `true` | Reuse results for identical dataset + fork + simulation settings |

Frontend (`frontend/.env`): `VITE_API_URL` (default `http://localhost:8000`) and `VITE_USE_MOCKS` (default `false`).

---

## 🧪 Testing

```bash
# Engine, ingestor & API tests (offline, throwaway database)
pytest

# Full end-to-end pipeline: upload -> inspect -> commit -> decide -> 4 forks -> compare
python scripts/e2e.py                       # in-process, no server needed
python scripts/e2e.py --url http://...      # against a deployed API
python scripts/e2e.py --csv path/to.csv     # with your own CSV

# AI evaluation suite (offline, includes Numeric Guard checks)
python ai/evals/test_prompts.py

# Frontend type-check & production build
cd frontend && pnpm run build
```

---

## 🧩 Adding a New Fork Type

1. **Transformer** ([`engine/changes.py`](engine/changes.py)): add `apply_<fork>(instance, goal, params)` that returns a modified `PurchaseGoal`. Add the fork to `BRANCH_TYPES`, `_BRANCH_ALIASES` and the `appliers` map in `apply_financial_change`.
2. **Solver** ([`engine/solver.py`](engine/solver.py)): add `solve_<fork>_branch(instance, goal)` that builds the CP-SAT model, and dispatch to it from `solve_financial_scenario`. `evaluate_financial_branch` then runs the Monte Carlo step automatically.
3. **Scenario agent** ([`ai/agents/scenario.py`](ai/agents/scenario.py)): add the fork to `_FORK_METADATA` and the fan-out list.
4. **Parser** ([`ai/agents/parser.py`](ai/agents/parser.py)): teach it the keywords that indicate the new financing preference.
5. **Explainer** ([`ai/agents/explainer.py`](ai/agents/explainer.py)): make sure the fork's metrics are added to the Numeric Guard's allowed facts.
6. **Contracts & UI**: add the branch to `BranchType` in [`contracts/schemas.py`](contracts/schemas.py) and both `types.ts` copies, and give it a colour and label in `ScenarioTree.tsx`, `ComparisonDashboard.tsx` and `ExplanationPanel.tsx`.
7. **Tests**: add cases to `engine/tests/test_financial_solver.py`, `backend/tests/test_api.py` and `ai/evals/test_prompts.py`.

---

## 📁 Repository Structure

```
futurefork/
├── ai/                          # AI layer (LLM optional, regex fallbacks)
│   ├── agents/
│   │   ├── mapper.py            # CSV column-mapping agent
│   │   ├── parser.py            # Decision parser (₹ / lakh / crore aware)
│   │   ├── scenario.py          # 4-fork scenario fan-out
│   │   └── explainer.py         # Explanations + Numeric Guard
│   ├── catalog.py               # Financial decision catalog
│   ├── llm.py                   # LLM wrapper (OpenAI / Groq) with telemetry
│   └── evals/test_prompts.py    # AI evaluation benchmark
├── backend/                     # FastAPI server
│   ├── main.py                  # App, CORS, error handling
│   ├── settings.py              # Environment / .env configuration
│   ├── api/routes.py            # REST endpoints
│   ├── orchestration/           # Background runner, cache, engine/AI bridge
│   ├── db/                      # SQLAlchemy models, repository, sample seeding
│   └── tests/                   # API tests
├── contracts/                   # API schemas (Pydantic), TypeScript mirror, OpenAPI
├── data/
│   ├── ingestor.py              # CSV -> 12-month FinancialProblemInstance
│   ├── make_finance_samples.py  # Sample CSV generator
│   └── samples/                 # Personal, institute & startup CSVs
├── engine/                      # Optimization & simulation engine
│   ├── model.py                 # Domain dataclasses (PurchaseGoal, schedules, results)
│   ├── changes.py               # Fork transformers
│   ├── solver.py                # OR-Tools CP-SAT cash-flow solver
│   ├── simulator.py             # Vectorized NumPy Monte Carlo
│   ├── metrics.py               # Deterministic risk metrics
│   └── tests/                   # Engine tests
├── frontend/                    # React 18 + TypeScript + Tailwind
│   └── src/
│       ├── components/          # UploadIngestor, ScenarioTree, CashFlowMatrix, ...
│       ├── api/client.ts        # REST client
│       ├── contracts/types.ts   # Frontend type contracts
│       └── mocks/fixtures.ts    # Offline mock data
├── docs/                        # Architecture, decisions (ADRs), pitch & demo
├── scripts/                     # e2e.py pipeline check, export_openapi.py
├── Dockerfile                   # Backend image
├── docker-compose.yml           # Backend + frontend for local use
└── render.yaml                  # Render deployment spec
```

---

## 🤝 Contributing & Community

FutureFork is open source under the [MIT License](LICENSE).
- Read the [Contributing Guidelines](CONTRIBUTING.md).
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Want to help? Pick up an item from [Good First Issues](docs/GOOD_FIRST_ISSUES.md).

---

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

**Team FutureLabs** | CodeSprint 2026
