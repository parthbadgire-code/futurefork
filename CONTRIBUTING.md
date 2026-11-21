# Contributing to FutureFork 🍴

Thank you for your interest in contributing to FutureFork! We welcome contributions from developers, researchers, students, and open-source enthusiasts.

---

## 📜 Code of Conduct

All contributors are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Please ensure respectful and inclusive communication at all times.

---

## 🧭 The Golden Rule of FutureFork

When contributing to the AI or Optimization engine:
> **AI agents interpret and explain. Mathematical models calculate and validate.**
> Never let an LLM or prompt generate numerical metrics that appear in the UI. Numbers must strictly originate from `engine/metrics.py`, `engine/solver.py`, or `engine/simulator.py`, and must pass through the regex **Numeric Guard** in `ai/agents/explainer.py`.

---

## 🛠️ Development Setup

1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/<your-username>/futurefork.git
   cd futurefork
   ```

2. **Backend Setup**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r backend/requirements.txt
   python backend/main.py   # seeds the sample datasets on first start
   ```

3. **Frontend Setup**:
   ```bash
   cd frontend
   pnpm install
   pnpm dev
   ```

---

## 🌿 Git Workflow & Branch Conventions

- Branch from `main`.
- Use descriptive branch naming prefixes:
  - `feature/<short-description>`: New features or engine change types
  - `fix/<bug-description>`: Bug fixes
  - `perf/<optimization-area>`: Solver or simulation performance enhancements
  - `docs/<doc-topic>`: Documentation or tutorial updates
  - `test/<test-suite>`: Test coverage expansions
- Write clear, imperatively phrased commit messages (e.g., `feat(engine): add lease-to-own fork transformer`).

---

## 🧪 Testing Checklist Before Submitting a PR

Before opening a pull request, verify that all test suites pass cleanly:

```bash
# 1. Engine & Backend Unit Tests
pytest backend/tests engine/tests -v

# 2. Automated End-to-End API Pipeline
python scripts/e2e.py

# 3. AI Evaluation Benchmark (offline, includes Numeric Guard checks)
python ai/evals/test_prompts.py

# 4. Frontend Typecheck and Production Build
cd frontend && pnpm run build
```

---

## 📋 Pull Request Submission

1. Ensure all tests above pass without errors.
2. Provide a clear summary in your PR description:
   - What changed and why.
   - If adding a new fork strategy, include test cases and verify the Numeric Guard passes.
3. Link relevant issues (e.g., `Fixes #12`).
4. At least one maintainer review is required before merging.

Thank you for helping make decision-making transparent, mathematical, and explainable! 🚀
