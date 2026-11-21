import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, BarChart3, Circle, GitBranch, Layers, RotateCcw, Sparkles, Upload } from 'lucide-react';
import { api, isMockMode } from './api/client';
import {
  DatasetType,
  DecisionSpec,
  Explanation,
  FinancialScenarioResult,
  Scenario,
} from './contracts/types';
import { CashFlowMatrix } from './components/CashFlowMatrix';
import { ComparisonDashboard } from './components/ComparisonDashboard';
import { DecisionInput, EXAMPLE_PROMPTS } from './components/DecisionInput';
import { ExplanationPanel } from './components/ExplanationPanel';
import { ScenarioTree } from './components/ScenarioTree';
import { UploadIngestor } from './components/UploadIngestor';
import { ToastContainer, ToastMessage } from './components/ui/Toast';

type Tab = 'upload' | 'fork';

interface ActiveDataset {
  id: string;
  name: string;
  type: DatasetType;
}

const POLL_MS = 1000;

export const App: React.FC = () => {
  const [tab, setTab] = useState<Tab>('upload');
  const [dataset, setDataset] = useState<ActiveDataset | null>(null);

  const [promptText, setPromptText] = useState('');
  const [decisionSpec, setDecisionSpec] = useState<DecisionSpec | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [results, setResults] = useState<Record<string, FinancialScenarioResult>>({});
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);

  const [isRunning, setIsRunning] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [runProgress, setRunProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');

  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);

  const addToast = (type: 'success' | 'error' | 'info', message: string, title?: string) => {
    const id = `toast_${Date.now()}_${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message, title }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4500);
  };

  useEffect(() => {
    api.getHealth().then((h) => setApiHealthy(h.status === 'ok')).catch(() => setApiHealthy(false));
  }, []);

  // ─── Poll the background run until every fork is evaluated ───────────────
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isRunning || !runId) return;
    pollRef.current = setInterval(async () => {
      try {
        const run = await api.getRunStatus(runId);
        setScenarios((prev) => prev.map((s) => ({ ...s, status: run.scenarios[s.id] ?? s.status })));
        if (run.progress_percent !== undefined) setRunProgress(run.progress_percent);
        if (run.overall_status === 'done' || run.overall_status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          const comp = await api.getComparison(run.decision_id);
          setScenarios(comp.scenarios);
          setResults(comp.results);
          setExplanation(comp.explanation);
          setSelectedId(comp.scenarios.find((s) => s.parent_id === null)?.id ?? null);
          setIsRunning(false);
          setRunProgress(100);
          const failed = comp.scenarios.filter((s) => s.status === 'failed').length;
          if (run.overall_status === 'failed') {
            addToast('error', 'No scenario could be evaluated.', 'Run Failed');
          } else if (failed > 0) {
            addToast('info', `${failed} fork(s) could not be evaluated. See the scenario cards for details.`, 'Partially Evaluated');
          } else {
            addToast('success', 'All forks evaluated with OR-Tools CP-SAT and Monte Carlo simulation.', 'Evaluation Complete');
          }
        }
      } catch (err) {
        if (pollRef.current) clearInterval(pollRef.current);
        setIsRunning(false);
        addToast('error', err instanceof Error ? err.message : 'Lost contact with the run', 'Polling Error');
      }
    }, POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [isRunning, runId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Handlers ─────────────────────────────────────────────────────────────
  const clearDecision = () => {
    setDecisionSpec(null);
    setScenarios([]);
    setResults({});
    setExplanation(null);
    setSelectedId(null);
    setRunId(null);
    setRunProgress(0);
  };

  const handleDatasetReady = (id: string, name: string, type: DatasetType) => {
    setDataset({ id, name, type });
    clearDecision();
    setPromptText(EXAMPLE_PROMPTS[type][0]);
    setTab('fork');
    addToast('success', `Baseline (Node 0) ready for "${name}". Describe a decision to fork it.`, 'Dataset Ready');
  };

  const handleRun = async (text: string) => {
    if (!dataset) return;
    clearDecision();
    setIsRunning(true);
    setRunProgress(10);
    setStatusMessage('Parsing your decision…');
    try {
      const spec = await api.createDecision(text, dataset.id);
      setDecisionSpec(spec);
      if (spec.status !== 'ok') {
        setIsRunning(false);
        setRunProgress(0);
        return;
      }
      setRunProgress(30);
      setStatusMessage('Forking into 4 strategies…');
      setScenarios(await api.generateScenarios(spec.id));
      setRunProgress(45);
      setStatusMessage('Solving with CP-SAT and running 300 Monte Carlo stress tests…');
      const { run_id } = await api.runDecision(spec.id);
      setRunId(run_id);
    } catch (err: unknown) {
      setIsRunning(false);
      setRunProgress(0);
      addToast('error', err instanceof Error ? err.message : 'Pipeline execution failed', 'Run Error');
    }
  };

  const handleReset = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setIsRunning(false);
    setDataset(null);
    setPromptText('');
    clearDecision();
    setTab('upload');
  };

  // ─── Derived ──────────────────────────────────────────────────────────────
  const forkResults = useMemo(
    () => scenarios.filter((s) => !s.id.startsWith('branch_')).map((s) => results[s.id]).filter(Boolean),
    [scenarios, results],
  );
  const selectedResult = selectedId ? results[selectedId] ?? null : null;
  const baselineResult = forkResults.find((r) => r.branch_type === 'baseline') ?? null;

  return (
    <div className="min-h-screen flex flex-col bg-[#090D16] text-slate-100 selection:bg-emerald-500/30 bg-grid-pattern">
      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-[#090D16]/90 backdrop-blur-xl border-b border-white/8 shadow-glass">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-glow">
              <GitBranch className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-extrabold text-lg tracking-tight text-white">
                Future<span className="text-emerald-400">Fork</span>
              </span>
              <p className="text-[11px] text-slate-500 font-medium hidden sm:block">Drop CSV · Fork Future · Decide with Confidence</p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            {isMockMode && (
              <span className="text-[10px] font-bold font-mono uppercase bg-amber-500/15 text-amber-300 border border-amber-500/30 rounded px-2 py-0.5">
                Mock data
              </span>
            )}
            <div className="hidden md:flex items-center gap-1.5 text-[11px] text-slate-500">
              <Circle className={`w-2 h-2 fill-current ${apiHealthy === true ? 'text-emerald-500' : apiHealthy === false ? 'text-rose-500' : 'text-slate-600'}`} />
              <span>{apiHealthy === true ? 'API live' : apiHealthy === false ? 'API offline' : 'Connecting…'}</span>
            </div>
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 border border-white/10 bg-white/5 hover:bg-white/8 transition-all duration-200"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Reset</span>
            </button>
          </div>
        </div>
        {isRunning && (
          <div className="w-full bg-white/5 h-0.5 relative overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 via-cyan-500 to-purple-500 transition-all duration-300"
              style={{ width: `${Math.max(5, runProgress)}%` }}
            />
          </div>
        )}
      </header>

      {/* ── Main ───────────────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div className="text-center space-y-2 pt-2 pb-4">
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white">
            Drop Your CSV. <span className="text-emerald-400">Fork Your Financial Future.</span>
          </h1>
          <p className="text-sm text-slate-400 max-w-2xl mx-auto">
            Upload a bank statement, ERP ledger or P&L, describe a big purchase, and compare four ways to pay for it,
            each optimized with CP-SAT and stress-tested with Monte Carlo simulation.
          </p>
        </div>

        <div className="flex items-center gap-1 border-b border-white/8">
          <button
            onClick={() => setTab('upload')}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold transition-all border-b-2 -mb-px ${
              tab === 'upload' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            <Upload className="w-4 h-4" />
            Upload & Build
          </button>
          <button
            onClick={() => (dataset ? setTab('fork') : addToast('info', 'Choose a sample dataset or upload a CSV first.', 'Dataset Required'))}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold transition-all border-b-2 -mb-px ${
              tab === 'fork'
                ? 'border-emerald-500 text-emerald-400'
                : dataset ? 'border-transparent text-slate-500 hover:text-slate-300' : 'border-transparent text-slate-600 cursor-not-allowed'
            }`}
          >
            <Layers className="w-4 h-4" />
            Fork & Compare
          </button>
        </div>

        {tab === 'upload' && (
          <div className="animate-in fade-in">
            <UploadIngestor onDatasetReady={handleDatasetReady} />
          </div>
        )}

        {tab === 'fork' && dataset && (
          <div className="space-y-6 animate-in fade-in">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Activity className="w-3.5 h-3.5 text-emerald-500" />
              <span>Dataset: <span className="text-slate-200 font-semibold">{dataset.name}</span></span>
              {forkResults.length > 0 && (
                <label className="ml-auto flex items-center gap-1.5 cursor-pointer select-none">
                  <input type="checkbox" checked={showDiff} onChange={(e) => setShowDiff(e.target.checked)} className="w-3.5 h-3.5 accent-amber-500" />
                  <span>Show diff vs baseline</span>
                </label>
              )}
            </div>

            <DecisionInput
              promptText={promptText}
              setPromptText={setPromptText}
              datasetType={dataset.type}
              onRun={handleRun}
              isRunning={isRunning}
              statusMessage={statusMessage}
              decisionSpec={decisionSpec}
            />

            {scenarios.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
                  <GitBranch className="w-3.5 h-3.5 text-emerald-500" />
                  Scenario Tree: select a fork to explore
                </h2>
                <ScenarioTree scenarios={scenarios} results={results} selectedId={selectedId} onSelect={setSelectedId} />
              </section>
            )}

            {forkResults.length > 0 && (
              <>
                <section className="space-y-3">
                  <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
                    <Activity className="w-3.5 h-3.5 text-cyan-500" />
                    12-Month Cash Flow Matrix
                  </h2>
                  <CashFlowMatrix
                    result={selectedResult}
                    baselineResult={baselineResult}
                    showDiff={showDiff && selectedResult?.branch_type !== 'baseline'}
                  />
                </section>

                <section className="space-y-3">
                  <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
                    <BarChart3 className="w-3.5 h-3.5 text-purple-500" />
                    Comparison Dashboard
                  </h2>
                  <ComparisonDashboard financialResults={forkResults} selectedFinancialId={selectedId} />
                </section>

                <section className="space-y-3">
                  <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                    Decision Synthesis
                  </h2>
                  <ExplanationPanel explanation={explanation} financialResults={forkResults} selectedFinancialId={selectedId} />
                </section>
              </>
            )}
          </div>
        )}
      </main>

      <ToastContainer toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))} />

      <footer className="border-t border-white/5 bg-[#090D16] py-5 mt-12 text-center text-xs text-slate-600">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            <strong className="text-slate-500">FutureFork</strong> · Elite Coders CodeSprint 2026 · Team FutureLabs
          </div>
          <div className="flex items-center gap-4 text-slate-700">
            <span>React 18 + Vite + Tailwind</span>
            <span>Recharts</span>
            <span>Google OR-Tools CP-SAT · NumPy Monte Carlo</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
