import React from 'react';
import { AlertTriangle, GitBranch, Loader2 } from 'lucide-react';
import { BranchType, FinancialScenarioResult, Scenario } from '../contracts/types';

interface ScenarioTreeProps {
  scenarios: Scenario[];
  results: Record<string, FinancialScenarioResult>;
  selectedId: string | null;
  onSelect: (scenarioId: string) => void;
}

export const BRANCH_STYLES: Record<BranchType, { label: string; color: string; badge: string }> = {
  baseline: { label: 'Baseline', color: '#10B981', badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
  upfront: { label: 'Upfront', color: '#06B6D4', badge: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' },
  emi: { label: 'EMI', color: '#F59E0B', badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
  phased: { label: 'Phased', color: '#8B5CF6', badge: 'bg-purple-500/20 text-purple-300 border-purple-500/30' },
  trim: { label: 'Trim', color: '#F43F5E', badge: 'bg-rose-500/20 text-rose-300 border-rose-500/30' },
};

export const branchOf = (s: Scenario): BranchType =>
  (s.change.type in BRANCH_STYLES ? s.change.type : 'baseline') as BranchType;

const scoreColor = (score: number) => (score >= 90 ? 'text-emerald-400' : score >= 70 ? 'text-amber-400' : 'text-rose-400');
const riskColor = (risk: number) => (risk <= 20 ? 'text-emerald-400' : risk <= 50 ? 'text-amber-400' : 'text-rose-400');

interface NodeCardProps {
  scenario: Scenario;
  result?: FinancialScenarioResult;
  selected: boolean;
  onSelect: () => void;
}

const NodeCard: React.FC<NodeCardProps> = ({ scenario, result, selected, onSelect }) => {
  const style = BRANCH_STYLES[branchOf(scenario)];
  const m = result?.metrics;

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={!result}
      className={`glass-card p-4 text-left w-full transition-all duration-200 border-2
                  ${result ? 'cursor-pointer hover:scale-[1.02] hover:shadow-glass' : 'cursor-default opacity-80'}
                  ${selected ? 'shadow-glass' : 'border-white/10'}`}
      style={{ borderColor: selected ? style.color : undefined }}
    >
      <div className="flex items-start justify-between mb-3 gap-2">
        <div>
          <span className={`text-[10px] font-bold uppercase tracking-wider border rounded-md px-2 py-0.5 ${style.badge}`}>
            {style.label}
          </span>
          <div className="text-xs font-semibold text-slate-200 mt-1.5 leading-snug">{scenario.name}</div>
        </div>
        {(scenario.status === 'running' || scenario.status === 'queued') && !result && (
          <Loader2 className="w-4 h-4 text-slate-500 animate-spin shrink-0" />
        )}
        {scenario.status === 'failed' && <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />}
      </div>

      {m ? (
        <>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="space-y-0.5">
              <div className="text-[9px] uppercase tracking-wider text-slate-500">Survival</div>
              <div className={`text-sm font-black font-mono tabular-nums ${scoreColor(m.survival_score_pct)}`}>{m.survival_score_pct}%</div>
            </div>
            <div className="space-y-0.5">
              <div className="text-[9px] uppercase tracking-wider text-slate-500">Cash-Out Risk</div>
              <div className={`text-sm font-black font-mono tabular-nums ${riskColor(m.cash_out_risk_pct)}`}>{m.cash_out_risk_pct}%</div>
            </div>
            <div className="space-y-0.5">
              <div className="text-[9px] uppercase tracking-wider text-slate-500">Runway</div>
              <div className="text-sm font-black font-mono tabular-nums text-cyan-400">{m.runway_months}mo</div>
            </div>
          </div>
          <div className="w-full h-1.5 bg-white/8 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${m.survival_score_pct}%`,
                backgroundColor: m.survival_score_pct >= 90 ? '#10B981' : m.survival_score_pct >= 70 ? '#F59E0B' : '#F43F5E',
              }}
            />
          </div>
        </>
      ) : (
        <div className="text-[11px] text-slate-500 mb-1">
          {scenario.status === 'failed' ? 'Not evaluated' : 'Solving with CP-SAT + Monte Carlo…'}
        </div>
      )}

      <p className="text-[10px] text-slate-500 leading-snug mt-2.5 line-clamp-3">{scenario.description}</p>
    </button>
  );
};

export const ScenarioTree: React.FC<ScenarioTreeProps> = ({ scenarios, results, selectedId, onSelect }) => {
  const baseline = scenarios.find((s) => s.parent_id === null);
  const forks = scenarios.filter((s) => s.parent_id !== null);

  return (
    <div className="space-y-5">
      {baseline && (
        <div className="max-w-sm">
          <NodeCard
            scenario={baseline}
            result={results[baseline.id]}
            selected={selectedId === baseline.id}
            onSelect={() => onSelect(baseline.id)}
          />
        </div>
      )}

      <div className="flex items-center gap-3">
        <div className="w-px h-6 bg-white/10 ml-6" />
        <div className="text-xs text-slate-500 flex items-center gap-1.5">
          <GitBranch className="w-3.5 h-3.5 text-slate-600" />
          {forks.length} competing forks
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {forks.map((s) => (
          <NodeCard key={s.id} scenario={s} result={results[s.id]} selected={selectedId === s.id} onSelect={() => onSelect(s.id)} />
        ))}
      </div>
    </div>
  );
};
