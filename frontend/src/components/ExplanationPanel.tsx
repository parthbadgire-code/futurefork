import React from 'react';
import { Card } from './ui/Card';
import { Badge } from './ui/Badge';
import { Sparkles, CheckCircle2, Lightbulb, Compass } from 'lucide-react';
import { BranchType, Explanation, FinancialScenarioResult } from '../contracts/types';

// ─── Utility: parse ₹, %, Month N patterns ──────────────────────────────────

function parseExplanationPills(text: string, onHighlight?: (month: number) => void): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Pattern: ₹ amounts, percentages, Month references
  const regex = /(₹[\d,.]+(L|K|Cr)?|[\d.]+%|Month\s+\d+|\d+\s+months?)/gi;
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    // Add text before match
    if (match.index > lastIdx) {
      parts.push(text.slice(lastIdx, match.index));
    }

    const token = match[0];
    const isRupee = token.startsWith('₹');
    const isPercent = token.endsWith('%');
    const isMonth = /month/i.test(token);

    let pillClass = '';
    if (isRupee) pillClass = 'metric-pill-emerald';
    else if (isPercent) pillClass = 'metric-pill-amber';
    else if (isMonth) pillClass = 'metric-pill-cyan';
    else pillClass = 'metric-pill-cyan';

    const monthNum = isMonth ? parseInt(token.replace(/\D/g, ''), 10) : null;

    parts.push(
      <button
        key={`${match.index}-${token}`}
        className={`${pillClass} cursor-pointer hover:opacity-80 active:scale-95 transition-all duration-100 inline-block mx-0.5`}
        onClick={() => { if (monthNum !== null && onHighlight) onHighlight(monthNum); }}
        title={monthNum !== null ? `Highlight Month ${monthNum}` : undefined}
      >
        {token}
      </button>
    );

    lastIdx = match.index + token.length;
  }

  if (lastIdx < text.length) {
    parts.push(text.slice(lastIdx));
  }

  return parts;
}

const POLICY_LABEL_MAP: Record<BranchType, string> = {
  baseline: 'Baseline (Node 0)',
  upfront:  'Upfront Purchase',
  emi:      'EMI / Instalments',
  phased:   'Phased Purchase',
  trim:     'Trim & Buy',
};

const POLICY_COLOR_MAP: Record<BranchType, string> = {
  baseline: 'border-emerald-500/30 bg-emerald-500/5',
  upfront:  'border-cyan-500/30 bg-cyan-500/5',
  emi:      'border-amber-500/30 bg-amber-500/5',
  phased:   'border-purple-500/30 bg-purple-500/5',
  trim:     'border-rose-500/30 bg-rose-500/5',
};

const SURVIVAL_COLOR = (pct: number) =>
  pct >= 90 ? 'text-emerald-400' : pct >= 70 ? 'text-amber-400' : 'text-rose-400';

// ─── Financial Explanation Panel ─────────────────────────────────────────────

interface ExplanationPanelProps {
  explanation: Explanation | null;
  financialResults: FinancialScenarioResult[];
  selectedFinancialId: string | null;
  onHighlightMonth?: (month: number) => void;
}

export const ExplanationPanel: React.FC<ExplanationPanelProps> = ({
  explanation,
  financialResults,
  selectedFinancialId,
  onHighlightMonth,
}) => {
  if (financialResults.length === 0) return null;
  const best = financialResults.reduce((a, b) =>
    b.metrics.survival_score_pct > a.metrics.survival_score_pct ? b : a
  );

  return (
    <div className="glass-card p-6 space-y-6 animate-in fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-white/8 gap-2">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-200">AI Decision Synthesis</h3>
            <p className="text-xs text-slate-500">Grounded strictly in CP-SAT solver + Monte Carlo simulation outputs</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="purple" size="sm" dot>
            {explanation?.source === 'llm' ? 'AI-written from computed results' : 'Template from computed results'}
          </Badge>
          <span className={`text-[10px] font-mono ${explanation?.guard_passed ? 'text-emerald-500' : 'text-rose-400'}`}>
            Numeric Guard: {explanation?.guard_passed ? 'passed' : 'failed'}
          </span>
        </div>
      </div>

      {/* Guarded explanation */}
      {explanation?.summary && (
        <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
          {parseExplanationPills(explanation.summary, onHighlightMonth)}
        </p>
      )}

      {/* Recommendation */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-500/10 via-cyan-500/5 to-purple-500/10 border border-emerald-500/20 space-y-2">
        <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
          <Lightbulb className="w-4 h-4" />
          Recommended Policy: <span className="text-white">{POLICY_LABEL_MAP[best.branch_type]}</span>
        </div>
        <div className="text-sm text-slate-300 leading-relaxed font-mono tabular-nums">
          Survival score{' '}
          <span className={`font-black ${SURVIVAL_COLOR(best.metrics.survival_score_pct)}`}>
            {best.metrics.survival_score_pct}%
          </span>
          {' '}· Cash-out risk{' '}
          <span className={`font-black ${SURVIVAL_COLOR(100 - best.metrics.cash_out_risk_pct)}`}>
            {best.metrics.cash_out_risk_pct}%
          </span>
          {' '}· Runway{' '}
          <span className="text-cyan-400 font-black">{best.metrics.runway_months} months</span>
        </div>
        <div className="text-[11px] text-slate-500 pt-1 flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          <span>Highest survival score across forks; every figure comes from CP-SAT and {best.simulation.n_runs} Monte Carlo runs.</span>
        </div>
      </div>

      {/* Per-scenario breakdown */}
      <div className="space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 flex items-center gap-2">
          <Compass className="w-3.5 h-3.5 text-slate-500" />
          Per-Fork Consequence Analysis
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {financialResults.map((r) => (
            <div
              key={r.scenario_id}
              className={`p-4 rounded-xl border space-y-2 transition-all hover:shadow-glass ${
                POLICY_COLOR_MAP[r.branch_type] ?? 'border-white/10 bg-white/3'
              } ${r.scenario_id === selectedFinancialId ? 'ring-1 ring-inset ring-white/20' : ''}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-200">{r.name ?? POLICY_LABEL_MAP[r.branch_type]}</span>
                <span className={`text-xs font-black font-mono tabular-nums ${SURVIVAL_COLOR(r.metrics.survival_score_pct)}`}>
                  {r.metrics.survival_score_pct}% survival
                </span>
              </div>
              {r.explanation && (
                <p className="text-xs text-slate-400 leading-relaxed">
                  {parseExplanationPills(r.explanation, onHighlightMonth)}
                </p>
              )}
              <div className="flex gap-3 text-[10px] font-mono tabular-nums mt-1">
                <span className="metric-pill-rose">{r.metrics.cash_out_risk_pct}% risk</span>
                <span className="metric-pill-cyan">{r.metrics.runway_months}mo runway</span>
                <span className={r.metrics.p10_worst_balance < 0 ? 'metric-pill-rose' : 'metric-pill-emerald'}>
                  P10: {r.metrics.p10_worst_balance < 0 ? '-₹' : '₹'}
                  {Math.abs(r.metrics.p10_worst_balance).toLocaleString('en-IN')}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
