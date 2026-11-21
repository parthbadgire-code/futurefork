// Mock data for frontend-only development (VITE_USE_MOCKS=true).
// These numbers are illustrative placeholders. With the real backend every number
// comes from the CP-SAT solver and the Monte Carlo simulator.

import {
  BranchType,
  CashFlowMatrixData,
  ComparisonResponse,
  DatasetType,
  FinancialScenarioResult,
  InspectResponse,
  Scenario,
} from '../contracts/types';

// ─── Sample dataset presets (ids match the datasets the backend seeds) ─────

export interface FinancialDatasetPreset {
  id: string;
  label: string;
  name: string;
  dataset_type: DatasetType;
  description: string;
}

export const SAMPLE_DATASETS: FinancialDatasetPreset[] = [
  {
    id: 'sample_personal',
    label: 'Personal UPI',
    name: 'Sample: Personal UPI Statement',
    dataset_type: 'personal',
    description: 'Salary credits, rent, groceries, subscriptions and travel over 12 months.',
  },
  {
    id: 'sample_institute',
    label: 'Institute ₹1.8Cr ERP',
    name: 'Sample: Institute ERP Ledger (~₹1.8 Cr)',
    dataset_type: 'institute',
    description: 'College ERP ledger: salaries, utilities, labs, events and infrastructure.',
  },
  {
    id: 'sample_startup',
    label: 'Startup P&L',
    name: 'Sample: Startup P&L / Burn',
    dataset_type: 'startup',
    description: 'B2B SaaS P&L: MRR, payroll burn, cloud infra and marketing.',
  },
];

// ─── Inspect ───────────────────────────────────────────────────────────────

export const MOCK_INSPECT_RESPONSE: InspectResponse = {
  upload_id: 'upl_mock000000000000',
  filename: 'transactions.csv',
  headers: ['Date', 'Narration', 'Category', 'Debit', 'Credit', 'Balance'],
  proposed_mapping: {
    date_col: 'Date',
    amount_col: null,
    debit_col: 'Debit',
    credit_col: 'Credit',
    category_col: 'Category',
    description_col: 'Narration',
    type_col: null,
    date_format: null,
    starting_balance: 0,
  },
  mapping_confidence: 0.92,
  mapping_source: 'regex',
  dataset_type: 'personal',
  preview_rows: [
    { Date: '01/04/2024', Narration: 'SALARY/ACME LTD', Category: 'Income / Salary', Debit: '', Credit: '₹ 1,45,000.00', Balance: '₹ 2,95,000.00' },
    { Date: '02/04/2024', Narration: 'Rent Payment', Category: 'Rent', Debit: '₹ 32,000.00', Credit: '', Balance: '₹ 2,63,000.00' },
    { Date: '03/04/2024', Narration: 'UPI/Zepto Quick', Category: 'Groceries', Debit: '₹ 2,836.72', Credit: '', Balance: '₹ 2,60,163.28' },
    { Date: '04/04/2024', Narration: 'Electricity Bill', Category: 'Utilities', Debit: '₹ 3,800.00', Credit: '', Balance: '₹ 2,56,363.28' },
    { Date: '05/04/2024', Narration: 'SIP Investment', Category: 'Investments', Debit: '₹ 25,000.00', Credit: '', Balance: '₹ 2,31,363.28' },
  ],
  ttl_seconds: 900,
};

// ─── Mock comparison ───────────────────────────────────────────────────────

const MONTHS = ['2024-04', '2024-05', '2024-06', '2024-07', '2024-08', '2024-09', '2024-10', '2024-11', '2024-12', '2025-01', '2025-02', '2025-03'];

const BASE_CATEGORIES: { name: string; type: 'fixed' | 'flexible'; base: number }[] = [
  { name: 'Rent', type: 'fixed', base: 32000 },
  { name: 'Groceries', type: 'fixed', base: 14000 },
  { name: 'Utilities', type: 'fixed', base: 5500 },
  { name: 'Investments', type: 'fixed', base: 25000 },
  { name: 'Food & Dining', type: 'flexible', base: 9000 },
  { name: 'Shopping', type: 'flexible', base: 11000 },
  { name: 'Travel', type: 'flexible', base: 8000 },
  { name: 'Entertainment', type: 'flexible', base: 4000 },
];

interface MockBranch {
  branch: BranchType;
  name: string;
  description: string;
  purchase: number[];     // purchase cash-out per month
  trim: number;           // fraction cut from flexible categories
  interest: number;
  risk: number;
  survival: number;
}

const COST = 120000;
const FLOOR = 30000;
const emi = (months: number, total: number) => Array.from({ length: 12 }, (_, i) => (i < months ? Math.round(total / months) : 0));

const MOCK_BRANCHES: MockBranch[] = [
  { branch: 'baseline', name: 'Baseline (Node 0)', description: 'Your historical 12-month cash flow with no purchase and no spending changes.', purchase: Array(12).fill(0), trim: 0, interest: 0, risk: 0, survival: 100 },
  { branch: 'upfront', name: 'Upfront Purchase', description: 'Pay the full purchase cost immediately in a single payment with zero interest.', purchase: [COST, ...Array(11).fill(0)], trim: 0, interest: 0, risk: 1.3, survival: 98.8 },
  { branch: 'emi', name: 'EMI / Installment Financing', description: 'Spread the capital outlay across monthly installments with an annual financing rate.', purchase: emi(12, COST + 6000), trim: 0, interest: 6000, risk: 0, survival: 100 },
  { branch: 'phased', name: 'Phased / Milestone Purchase', description: 'Split the purchase into two equal tranches (50/50) to smooth the cash-flow impact.', purchase: [COST / 2, 0, 0, 0, 0, COST / 2, 0, 0, 0, 0, 0, 0], trim: 0, interest: 0, risk: 0, survival: 99.9 },
  { branch: 'trim', name: 'Trim & Buy', description: 'Optimally reduce discretionary spending to protect the emergency reserve while purchasing.', purchase: [COST, ...Array(11).fill(0)], trim: 0.2, interest: 0, risk: 0.3, survival: 99.6 },
];

function mockResult(decisionId: string, b: MockBranch): FinancialScenarioResult {
  const inflows = MONTHS.map((_, i) => 145000 + (i % 4 === 3 ? 2500 : 0));
  const categories = BASE_CATEGORIES.map((c) => ({
    name: c.name,
    type: c.type,
    values: MONTHS.map((_, i) => Math.round(c.base * (1 + 0.08 * Math.sin(i + c.base)) * (c.type === 'flexible' ? 1 - b.trim : 1))),
  }));
  const cashFlow: CashFlowMatrixData = { months: MONTHS, inflows, purchase_cash_out: b.purchase, categories };

  let balance = 150000;
  const balances = MONTHS.map((_, i) => {
    const out = categories.reduce((s, c) => s + c.values[i], 0) + b.purchase[i];
    balance += inflows[i] - out;
    return Math.round(balance);
  });
  const lowest = Math.min(...balances);
  const p10 = Math.round(lowest * 0.85);
  const trimsSaved = b.trim > 0
    ? Math.round(BASE_CATEGORIES.filter((c) => c.type === 'flexible').reduce((s, c) => s + c.base * 12 * b.trim, 0))
    : 0;

  return {
    scenario_id: `${decisionId}_${b.branch}`,
    decision_id: decisionId,
    branch_type: b.branch,
    name: b.name,
    is_feasible: lowest >= FLOOR,
    purchase_month: b.branch === 'baseline' ? -1 : 0,
    solver: { status: 'OPTIMAL', solver: b.branch === 'baseline' ? 'Deterministic-Audit' : 'OR-Tools-CP-SAT', runtime_s: 0.02 },
    metrics: {
      cash_out_risk_pct: b.risk,
      floor_breach_risk_pct: b.risk,
      survival_score_pct: b.survival,
      p10_worst_balance: p10,
      lowest_balance: lowest,
      lowest_balance_month: MONTHS[balances.indexOf(lowest)],
      months_below_floor: balances.filter((x) => x < FLOOR).length,
      runway_months: Math.round((balances[11] / 110000) * 10) / 10,
      ending_balance: balances[11],
      emergency_floor: FLOOR,
      total_purchase_cost: b.branch === 'baseline' ? 0 : COST,
      total_financing_interest: b.interest,
      total_trims_saved: trimsSaved,
    },
    simulation: {
      n_runs: 300,
      prob_cash_out: b.risk / 100,
      monthly_balances: balances,
      balance_p10: balances.map((v) => Math.round(v * 0.85)),
      balance_p90: balances.map((v) => Math.round(v * 1.1)),
      per_metric: {
        survival_score_pct: { mean: b.survival, std: 0, p10: b.survival, p90: b.survival },
        cash_out_risk_pct: { mean: b.risk, std: 0, p10: b.risk, p90: b.risk },
      },
    },
    cash_flow: cashFlow,
    category_trims: Object.fromEntries(BASE_CATEGORIES.filter((c) => c.type === 'flexible').map((c) => [c.name, b.trim])),
    explanation: null,
  };
}

export function buildMockComparison(decisionId: string, text: string, datasetId: string): ComparisonResponse {
  const scenarios: Scenario[] = MOCK_BRANCHES.map((b) => ({
    id: `${decisionId}_${b.branch}`,
    decision_id: decisionId,
    parent_id: b.branch === 'baseline' ? null : `${decisionId}_baseline`,
    name: b.name,
    description: b.description,
    change: { type: b.branch, params: { total_cost: COST, emergency_floor: FLOOR } },
    status: 'done',
  }));
  const results = Object.fromEntries(MOCK_BRANCHES.map((b) => [`${decisionId}_${b.branch}`, mockResult(decisionId, b)]));
  return {
    decision_id: decisionId,
    decision_spec: {
      id: decisionId,
      text,
      dataset_id: datasetId,
      dataset_type: 'personal',
      change: { type: 'emi', params: { total_cost: COST, emergency_floor: FLOOR } },
      status: 'ok',
      message: null,
    },
    scenarios,
    results,
    explanation: {
      summary:
        'Mock mode: this explanation is a placeholder. Connect the backend (VITE_USE_MOCKS=false) for an explanation generated from solver results and checked by the Numeric Guard.',
      source: 'template',
      guard_passed: true,
      violations: [],
    },
  };
}
