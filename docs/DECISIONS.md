# FutureFork Architectural Decision Records (ADR)

## ADR 001: Golden Rule - Strict Separation of LLMs and Mathematical Engines
- **Date**: 2026-11-15
- **Status**: Accepted
- **Context**: LLMs hallucinate numbers and cannot reliably verify constraints such as an emergency-floor breach or EMI interest.
- **Decision**: AI agents interpret text, produce structured decision specs, and explain computed results. The CP-SAT solver, the metric engine and the NumPy Monte Carlo simulator compute every number that reaches the screen.
- **Consequence**: Explanations pass through a regex Numeric Guard. As of ADR 006, the backend never substitutes placeholder numbers when the engine fails.

## ADR 002: Schema-First API Contracts
- **Date**: 2026-11-15
- **Status**: Accepted (amended 2026-11-21)
- **Context**: Four teammates worked in parallel on frontend, backend, engine and AI.
- **Decision**: Response schemas are defined in `contracts/schemas.py` and mirrored in `contracts/types.ts` / `frontend/src/contracts/types.ts`. Since 2026-11-21 the schemas are enforced as FastAPI `response_model`s, and `contracts/openapi.json` is generated from the running app.
- **Consequence**: The frontend can be built against mocks with the same shape (`VITE_USE_MOCKS=true`).

## ADR 003: Soft Constraints for CP-SAT
- **Date**: 2026-11-15
- **Status**: Accepted (re-scoped 2026-11-21)
- **Context**: Aggressive purchase decisions can make it impossible to stay above the emergency floor in every month.
- **Decision**: The emergency floor is a soft constraint. Each fork minimizes total floor deficit first, then a fork-specific secondary objective.
- **Consequence**: The solver always returns the least-bad plan. Breaches are reported through `months_below_floor` and the risk metrics instead of an `INFEASIBLE` error.

## ADR 004: JSON Payload Storage for DB Models
- **Date**: 2026-11-15
- **Status**: Accepted
- **Context**: Rapid hackathon iteration kept changing scenario and result metadata.
- **Decision**: Core entities store flexible payload blobs (`jsonb` on Postgres / JSON text on SQLite). Results store the raw engine output, and the API projects it into the contract at read time.
- **Consequence**: No runtime schema migrations during the sprint. Changing a table's columns still requires recreating local SQLite databases.

## ADR 005: Financial Decisions Only; Timetabling Removed
- **Date**: 2026-11-21
- **Status**: Accepted
- **Context**: FutureFork began as a university timetabling tool, then pivoted to financial cash-flow decisions. Both code paths coexisted, the timetable path was the default for evaluation, and the live pipeline returned timetable or placeholder output for financial datasets.
- **Decision**: Remove the timetable domain entirely: engine models, appliers, solver, simulator and metrics, sample data, AI stubs, the LangGraph timetable graph, UI mode, and contracts. Keep a single engine entry point, `evaluate_financial_branch`.
- **Consequence**: One product, one evaluation path, one contract.

## ADR 006: Fail Honestly Instead of Falling Back to Placeholder Numbers
- **Date**: 2026-11-21
- **Status**: Accepted
- **Context**: The backend bridge returned hardcoded metrics (for example "28% cash-out risk") whenever the engine raised. That broke ADR 001 without anyone noticing, and lenient tests accepted it.
- **Decision**: Engine failures propagate. The runner marks that scenario `failed`, and the other forks still run. Tests assert that results come from the engine.
- **Consequence**: Bad inputs and engine bugs become visible in the UI and in CI instead of being hidden behind plausible-looking numbers.
