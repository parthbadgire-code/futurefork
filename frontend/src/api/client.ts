import {
  ChangeSpec,
  CommitRequest,
  CommitResponse,
  ComparisonResponse,
  DatasetSummary,
  DecisionSpec,
  FinancialScenarioResult,
  InspectResponse,
  RunStatus,
  Scenario,
} from '../contracts/types';
import { buildMockComparison, MOCK_INSPECT_RESPONSE, SAMPLE_DATASETS } from '../mocks/fixtures';

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const isMockMode = USE_MOCKS;

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Reads the backend's {error, message} body (or FastAPI's {detail: {...}}) into an Error. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      const detail = body?.detail ?? body;
      message = detail?.message || (typeof detail === 'string' ? detail : message);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(message || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

// Mock-mode state
const mockDecisions: Record<string, { text: string; datasetId: string; startedAt: number }> = {};

export const api = {
  async getHealth(): Promise<{ status: string }> {
    if (USE_MOCKS) return { status: 'ok' };
    return request('/health');
  },

  async getDatasets(): Promise<DatasetSummary[]> {
    if (USE_MOCKS) {
      return SAMPLE_DATASETS.map((d) => ({
        id: d.id,
        name: d.name,
        description: d.description,
        stats: { months: 12, categories: 8, starting_balance: 0, total_inflow: 0, total_outflow: 0, category_types: {} },
        baseline_metrics: {},
      }));
    }
    return request('/datasets');
  },

  async inspectDataset(file: File): Promise<InspectResponse> {
    if (USE_MOCKS) {
      await delay(500);
      return { ...MOCK_INSPECT_RESPONSE, filename: file.name };
    }
    const formData = new FormData();
    formData.append('file', file);
    return request('/datasets/inspect', { method: 'POST', body: formData });
  },

  async commitDataset(payload: CommitRequest): Promise<CommitResponse> {
    if (USE_MOCKS) {
      await delay(400);
      return {
        dataset_id: `ds_mock_${Date.now()}`,
        name: payload.dataset_name || 'Mock Dataset',
        dataset_type: payload.dataset_type || 'personal',
        stats: { months: 12, categories: 8, starting_balance: payload.starting_balance || 0, total_inflow: 0, total_outflow: 0, category_types: {} },
        baseline_metrics: {},
      };
    }
    return request('/datasets/commit', json(payload));
  },

  async createDecision(text: string, datasetId: string): Promise<DecisionSpec> {
    if (USE_MOCKS) {
      await delay(300);
      const id = `dec_mock${Date.now()}`;
      const hasAmount = /\d/.test(text);
      mockDecisions[id] = { text, datasetId, startedAt: Date.now() };
      return {
        id,
        text,
        dataset_id: datasetId,
        dataset_type: 'personal',
        change: { type: 'emi', params: {} },
        status: hasAmount ? 'ok' : 'needs_clarification',
        message: hasAmount ? null : 'Please include an amount like ₹60L, ₹1.2 lakh, or ₹30,000.',
      };
    }
    return request('/decisions', json({ text, dataset_id: datasetId }));
  },

  async generateScenarios(decisionId: string): Promise<Scenario[]> {
    if (USE_MOCKS) {
      const d = mockDecisions[decisionId];
      return buildMockComparison(decisionId, d?.text ?? '', d?.datasetId ?? '').scenarios.map((s) => ({ ...s, status: 'queued' }));
    }
    return request(`/decisions/${decisionId}/scenarios`, { method: 'POST' });
  },

  async runDecision(decisionId: string): Promise<{ run_id: string }> {
    if (USE_MOCKS) {
      if (mockDecisions[decisionId]) mockDecisions[decisionId].startedAt = Date.now();
      return { run_id: `run_${decisionId}` };
    }
    return request(`/decisions/${decisionId}/run`, { method: 'POST' });
  },

  async getRunStatus(runId: string): Promise<RunStatus> {
    if (USE_MOCKS) {
      const decisionId = runId.replace(/^run_/, '');
      const started = mockDecisions[decisionId]?.startedAt ?? 0;
      const done = Date.now() - started > 1200;
      const ids = buildMockComparison(decisionId, '', '').scenarios.map((s) => s.id);
      return {
        run_id: runId,
        decision_id: decisionId,
        overall_status: done ? 'done' : 'running',
        scenarios: Object.fromEntries(ids.map((id) => [id, done ? 'done' : 'running'])),
        progress_percent: done ? 100 : 50,
      };
    }
    return request(`/runs/${runId}`);
  },

  async getScenarioResult(scenarioId: string): Promise<FinancialScenarioResult> {
    if (USE_MOCKS) {
      const decisionId = scenarioId.replace(/_(baseline|upfront|emi|phased|trim)$/, '');
      return buildMockComparison(decisionId, '', '').results[scenarioId];
    }
    return request(`/scenarios/${scenarioId}/result`);
  },

  async getComparison(decisionId: string): Promise<ComparisonResponse> {
    if (USE_MOCKS) {
      const d = mockDecisions[decisionId];
      return buildMockComparison(decisionId, d?.text ?? '', d?.datasetId ?? '');
    }
    return request(`/decisions/${decisionId}/compare`);
  },

  async branchScenario(parentScenarioId: string, name: string, change: ChangeSpec): Promise<Scenario> {
    if (USE_MOCKS) {
      throw new Error('Custom branches need the backend (set VITE_USE_MOCKS=false).');
    }
    return request(`/scenarios/${parentScenarioId}/branch`, json({ name, change }));
  },
};
