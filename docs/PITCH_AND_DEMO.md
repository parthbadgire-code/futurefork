# FutureFork: Pitch Script & Demo Checklist

**Team FutureLabs | Elite Coders CodeSprint 2026**
*Tagline: Simulate > Compare > Decide. Not just what to do, but what could happen if you choose differently.*

All demo numbers below are real engine output for the bundled **Personal UPI** sample with the default seed (42) and 300 Monte Carlo runs. If you change the dataset, seed or prompt, re-check them before presenting.

---

## 🎤 2-Minute Pitch Script

> **[0:00 – 0:25] The problem**
> *"Every big purchase is a cash-flow bet. Buy a laptop, fund a GPU lab, hire two engineers: it looks affordable today, and three months later a late salary or a surprise bill drains the reserve. People ask ChatGPT, but an LLM can't see your transactions and makes up numbers."*

> **[0:25 – 0:50] The solution and the Golden Rule**
> *"FutureFork reads your own bank statement, ERP ledger or P&L, takes your decision in plain English, and forks it into four ways to pay: upfront, EMI, phased, or trim-and-buy. Our rule is that AI interprets and explains, and math calculates. Every number comes from Google OR-Tools CP-SAT or a NumPy Monte Carlo simulation, and a Numeric Guard checks every figure in the AI's explanation."*

> **[0:50 – 1:40] Live demo**
> *"Here's a real personal UPI statement: salary, rent, groceries, twelve months. I type: 'Buy a ₹1.2L laptop on 12-month EMI without dropping below ₹30k emergency savings.'*
> *Paying upfront takes my lowest balance down to ₹79,867 and fails in 1.3% of 300 stress tests. EMI keeps it at ₹1,88,867 with 100% survival, but costs ₹12,000 in interest. The phased split keeps 99.9% survival with zero interest. So FutureFork shows me that the last 0.1% of safety costs ₹12,000. That's a trade-off a spreadsheet won't surface."*

> **[1:40 – 2:00] Impact**
> *"The same engine works for individuals, colleges and startups, on their own data, in seconds. FutureFork: Simulate, Compare, Decide."*

---

## 🎯 Demo Click-Through Checklist

1. **Start the stack**: backend on `:8000` and frontend on `:5173` with `VITE_USE_MOCKS=false`. Check that the header says **API live** with no **Mock data** badge.
2. **Upload & Build** tab → click the **Personal UPI** sample. You land on **Fork & Compare**.
3. Use the first example prompt: *"Buy a ₹1.2L laptop on 12-month EMI without dropping below ₹30k emergency savings"* → **Fork & Simulate**.
4. **Scenario Tree**: wait for the five cards (Baseline plus four forks) to finish. Point out:
   | Fork | Survival | Cash-out risk | Lowest balance | Interest |
   |---|---|---|---|---|
   | Baseline | 100% | 0% | ₹1,99,867 | – |
   | Upfront | 98.8% | 1.3% | ₹79,867 | ₹0 |
   | EMI (12 mo) | 100% | 0% | ₹1,88,867 | ₹12,000 |
   | Phased (50/50) | 99.9% | 0% | ₹1,39,867 | ₹0 |
   | Trim & Buy | 98.8% | 1.3% | ₹79,867 | ₹0 (no cuts needed) |
5. **Cash Flow Matrix**: select **Upfront**, tick **Show diff vs baseline**, and show the April purchase hit.
6. **Comparison Dashboard**: walk through the 12-month balance lines against the emergency-floor line.
7. **Decision Synthesis**: show the explanation and the **Numeric Guard: passed** label. Stress that every number in the text was checked against engine output.
8. *(Optional)* Show the **Crisis Shock Playground** sliders, but describe them honestly: they're a quick in-browser estimate, not engine output.

### Backup prompts
- *"Take a ₹2L vacation without dropping below ₹50k reserve"* (Personal): Upfront moves the purchase to May to protect the floor. EMI keeps 100% survival for ₹10,000 interest.
- Institute and startup samples run at a deficit even before any purchase, so expect high cash-out risk on every fork. That's useful for showing "this is unaffordable", but don't use them as the headline demo.

---

## 📊 7-Slide Deck Outline

| # | Slide | Content |
|---|---|---|
| 1 | **FutureFork** | Logo, tagline, team |
| 2 | **The Cash-Flow Trap** | Big purchases look affordable until timing and shocks hit; LLMs make up numbers |
| 3 | **The Golden Rule** | Plain English → parser → 4 forks → CP-SAT + Monte Carlo → guarded explanation |
| 4 | **Four Ways to Pay** | Upfront / EMI / Phased / Trim & Buy, with what the solver decides for each |
| 5 | **Live Demo** | The laptop decision table above |
| 6 | **Under the Hood** | 12-month balance model, soft emergency-floor constraint, 3 Monte Carlo shocks, Numeric Guard |
| 7 | **Open Source & Roadmap** | MIT-licensed; next: more fork types, multi-purchase plans, live bank feeds |
