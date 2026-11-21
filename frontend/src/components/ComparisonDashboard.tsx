import React, { useState } from 'react';
import { Card } from './ui/Card';
import { Badge } from './ui/Badge';
import { BranchType, FinancialScenarioResult } from '../contracts/types';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  ReferenceLine,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ComposedChart,
  ErrorBar,
} from 'recharts';
import {
  CheckCircle2,
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  Zap,
  Download,
} from 'lucide-react';

interface ComparisonDashboardProps {
  financialResults: FinancialScenarioResult[];
  selectedFinancialId: string | null;
}

// ─── Color helpers ───────────────────────────────────────────────────────────

const FINANCIAL_COLORS: Record<BranchType, string> = {
  baseline: '#10B981',
  upfront:  '#06B6D4',
  emi:      '#F59E0B',
  phased:   '#8B5CF6',
  trim:     '#F43F5E',
};

const FINANCIAL_LABELS: Record<BranchType, string> = {
  baseline: 'Baseline',
  upfront:  'Upfront Buy',
  emi:      'EMI / Instalments',
  phased:   'Phased Purchase',
  trim:     'Trim & Buy',
};

// ─── Tooltip helper ──────────────────────────────────────────────────────────

const fmtRs = (v: number) => {
  if (Math.abs(v) >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`;
  if (Math.abs(v) >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
  if (Math.abs(v) >= 1000) return `₹${(v / 1000).toFixed(0)}K`;
  return `₹${Math.round(v).toLocaleString('en-IN')}`;
};

// ─── Financial Comparison ────────────────────────────────────────────────────

interface FinancialComparisonProps {
  financialResults: FinancialScenarioResult[];
  selectedFinancialId: string | null;
}

const FinancialComparison: React.FC<FinancialComparisonProps> = ({ financialResults, selectedFinancialId }) => {
  const [floorLevel, setFloorLevel] = useState(financialResults[0]?.metrics.emergency_floor ?? 0);
  const [inflowDelay, setInflowDelay] = useState(0);    // 0–45 days
  const [surpriseOutflow, setSurpriseOutflow] = useState(0); // 0–2500000
  const [spendDrift, setSpendDrift] = useState(0);      // 0–30 %

  // Interpolate survival score based on sliders (pure client-side, no backend calls)
  const interpolateSurvival = (result: FinancialScenarioResult): number => {
    const base = result.simulation.per_metric.survival_score_pct;
    // Fraction across sliders
    const fInflow  = inflowDelay / 45;
    const fOutflow = surpriseOutflow / 2500000;
    const fDrift   = spendDrift / 30;
    const shock    = (fInflow * 0.4 + fOutflow * 0.4 + fDrift * 0.2);
    // Interpolate between p90 (best) and p10 (worst) based on shock
    const interpolated = base.p90 - shock * (base.p90 - base.p10);
    return Math.max(0, Math.min(100, Math.round(interpolated)));
  };

  // Build 12-month balance chart data
  const monthLabels = financialResults[0]?.cash_flow.months ?? [];
  const balanceChartData = monthLabels.map((month, i) => {
    const row: Record<string, number | string> = { month };
    financialResults.forEach((r) => {
      row[FINANCIAL_LABELS[r.branch_type]] = r.simulation.monthly_balances[i] ?? 0;
    });
    return row;
  });

  // Radar chart data
  const radarData = [
    {
      subject: 'Survival',
      ...financialResults.reduce((acc, r) => { acc[FINANCIAL_LABELS[r.branch_type]] = r.metrics.survival_score_pct; return acc; }, {} as Record<string, number>),
    },
    {
      subject: 'Cash Safety',
      ...financialResults.reduce((acc, r) => { acc[FINANCIAL_LABELS[r.branch_type]] = Math.max(0, 100 - r.metrics.cash_out_risk_pct); return acc; }, {} as Record<string, number>),
    },
    {
      subject: 'Runway',
      ...financialResults.reduce((acc, r) => { acc[FINANCIAL_LABELS[r.branch_type]] = Math.min(100, Math.round((r.metrics.runway_months / 18) * 100)); return acc; }, {} as Record<string, number>),
    },
    {
      subject: 'P10 Buffer',
      ...financialResults.reduce((acc, r) => {
        const v = r.metrics.p10_worst_balance;
        // Normalize to 0-100 (0 = negative, 100 = ₹10L+)
        acc[FINANCIAL_LABELS[r.branch_type]] = Math.max(0, Math.min(100, Math.round((v / 1000000) * 100)));
        return acc;
      }, {} as Record<string, number>),
    },
    {
      subject: 'Floor Clearance',
      ...financialResults.reduce((acc, r) => {
        // Higher P10 balance relative to floor = better
        const clearance = Math.max(0, r.metrics.p10_worst_balance - floorLevel);
        acc[FINANCIAL_LABELS[r.branch_type]] = Math.min(100, Math.round(clearance / 10000));
        return acc;
      }, {} as Record<string, number>),
    },
  ];

  // Export winning plan as CSV
  const handleExport = () => {
    const best = financialResults.reduce((a, b) =>
      b.metrics.survival_score_pct > a.metrics.survival_score_pct ? b : a
    );
    const rows = [
      ['FutureFork — Winning Plan Export'],
      ['Fork', FINANCIAL_LABELS[best.branch_type]],
      ['Survival Score', `${best.metrics.survival_score_pct}%`],
      ['Cash-Out Risk', `${best.metrics.cash_out_risk_pct}%`],
      ['Runway', `${best.metrics.runway_months} months`],
      ['P10 Worst Balance', fmtRs(best.metrics.p10_worst_balance)],
      [],
      ['Month', 'Balance'],
      ...monthLabels.map((m, i) => [m, best.simulation.monthly_balances[i]]),
    ];
    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `futurefork-${FINANCIAL_LABELS[best.branch_type].replace(/\s+/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const tooltipStyle = {
    backgroundColor: '#0F1623',
    borderRadius: '10px',
    border: '1px solid rgba(255,255,255,0.1)',
    fontSize: '12px',
    color: '#E2E8F0',
  };

  return (
    <div className="space-y-6">
      {/* ── Metrics Summary Table ──────────────────────────────────────────── */}
      <div className="glass-card p-5 overflow-x-auto">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-200">Fork Comparison — Key Metrics</h3>
            <p className="text-xs text-slate-500">Emerald ≥90% survival · Amber 70-89% · Rose &lt;70%</p>
          </div>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-emerald-400 border border-white/10 bg-white/5 hover:bg-emerald-500/10 hover:border-emerald-500/30 transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            Export Winning Plan
          </button>
        </div>
        <table className="w-full text-left text-xs min-w-[600px]">
          <thead>
            <tr className="border-b border-white/8">
              <th className="pb-3 pr-4 text-slate-500 font-semibold">Fork</th>
              <th className="pb-3 pr-4 text-slate-500 font-semibold tabular-nums">Survival</th>
              <th className="pb-3 pr-4 text-slate-500 font-semibold tabular-nums">Cash-Out Risk</th>
              <th className="pb-3 pr-4 text-slate-500 font-semibold tabular-nums">Runway</th>
              <th className="pb-3 pr-4 text-slate-500 font-semibold tabular-nums">P10 Balance</th>
              <th className="pb-3 text-slate-500 font-semibold">Verdict</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {financialResults.map((r) => {
              const sc = r.metrics.survival_score_pct;
              const survivalColor = sc >= 90 ? 'text-emerald-400' : sc >= 70 ? 'text-amber-400' : 'text-rose-400';
              const riskColor = r.metrics.cash_out_risk_pct <= 20 ? 'text-emerald-400' : r.metrics.cash_out_risk_pct <= 50 ? 'text-amber-400' : 'text-rose-400';
              const verdict = sc >= 90 ? '✅ Resilient' : sc >= 70 ? '⚠️ Moderate' : '🔴 High Risk';
              const isSelected = r.scenario_id === selectedFinancialId;

              return (
                <tr key={r.scenario_id} className={`transition-colors ${isSelected ? 'bg-white/5' : 'hover:bg-white/3'}`}>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: FINANCIAL_COLORS[r.branch_type] }} />
                      <span className="font-semibold text-slate-200">{FINANCIAL_LABELS[r.branch_type]}</span>
                      {isSelected && <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 rounded px-1.5 py-0.5">Selected</span>}
                    </div>
                  </td>
                  <td className={`py-3 pr-4 font-black font-mono tabular-nums text-sm ${survivalColor}`}>{sc}%</td>
                  <td className={`py-3 pr-4 font-black font-mono tabular-nums text-sm ${riskColor}`}>{r.metrics.cash_out_risk_pct}%</td>
                  <td className="py-3 pr-4 font-mono tabular-nums text-cyan-400 font-bold">{r.metrics.runway_months}mo</td>
                  <td className={`py-3 pr-4 font-mono tabular-nums text-sm ${r.metrics.p10_worst_balance < 0 ? 'text-rose-400' : 'text-slate-300'}`}>
                    {fmtRs(r.metrics.p10_worst_balance)}
                  </td>
                  <td className="py-3 text-xs">{verdict}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ── 12-Month Balance Trajectory + Radar ───────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Balance trajectory */}
        <div className="glass-card p-5">
          <div className="mb-4">
            <h4 className="text-sm font-bold text-slate-200">12-Month Balance Trajectories</h4>
            <p className="text-xs text-slate-500">Emergency floor: {fmtRs(floorLevel)}</p>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={balanceChartData} margin={{ top: 5, right: 15, left: 5, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={v => fmtRs(v as number)} width={56} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [fmtRs(v as number), '']} />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px', color: '#64748b' }} />
                <ReferenceLine y={floorLevel} stroke="#F43F5E" strokeDasharray="5 3" strokeWidth={1.5} label={{ value: 'Floor', fill: '#F43F5E', fontSize: 10 }} />
                {financialResults.map((r) => (
                  <Line
                    key={r.scenario_id}
                    type="monotone"
                    dataKey={FINANCIAL_LABELS[r.branch_type]}
                    stroke={FINANCIAL_COLORS[r.branch_type]}
                    strokeWidth={r.scenario_id === selectedFinancialId ? 2.5 : 1.5}
                    dot={false}
                    strokeOpacity={r.scenario_id === selectedFinancialId ? 1 : 0.5}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          {/* Floor slider */}
          <div className="mt-3 space-y-1">
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>Emergency Floor</span>
              <span className="font-mono tabular-nums text-rose-400">{fmtRs(floorLevel)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={2000000}
              step={50000}
              value={floorLevel}
              onChange={(e) => setFloorLevel(Number(e.target.value))}
              className="w-full accent-rose-500 cursor-pointer"
            />
          </div>
        </div>

        {/* Radar chart */}
        <div className="glass-card p-5">
          <div className="mb-4">
            <h4 className="text-sm font-bold text-slate-200">Multi-Objective Trade-off Radar</h4>
            <p className="text-xs text-slate-500">Larger surface area = better overall balance</p>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.08)" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: '#64748b' }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9, fill: '#475569' }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px', color: '#64748b' }} />
                {financialResults.map((r) => (
                  <Radar
                    key={r.scenario_id}
                    name={FINANCIAL_LABELS[r.branch_type]}
                    dataKey={FINANCIAL_LABELS[r.branch_type]}
                    stroke={FINANCIAL_COLORS[r.branch_type]}
                    fill={FINANCIAL_COLORS[r.branch_type]}
                    fillOpacity={r.scenario_id === selectedFinancialId ? 0.25 : 0.08}
                    strokeWidth={r.scenario_id === selectedFinancialId ? 2 : 1}
                  />
                ))}
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── 60fps Crisis Shock Playground ─────────────────────────────────── */}
      <div className="glass-card p-5 space-y-5">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <h4 className="text-sm font-bold text-slate-200">Crisis Shock Playground</h4>
          <span className="text-[10px] font-mono text-slate-500 bg-white/5 border border-white/8 rounded px-2 py-0.5">
            Client-side · Zero backend latency · Monte Carlo percentile interpolation
          </span>
        </div>
        <p className="text-[11px] text-amber-300/80 bg-amber-500/5 border border-amber-500/20 rounded-lg px-3 py-2">
          Illustrative only: these stressed scores are a rough in-browser estimate, not engine output.
          Re-run the decision for solver-verified numbers.
        </p>

        {/* Sliders */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-400">
              <span>Inflow Delay</span>
              <span className="font-mono tabular-nums text-cyan-400">{inflowDelay} days</span>
            </div>
            <input type="range" min={0} max={45} step={1} value={inflowDelay} onChange={e => setInflowDelay(Number(e.target.value))} className="w-full accent-cyan-500 cursor-pointer" />
            <div className="flex justify-between text-[10px] text-slate-600"><span>0 days</span><span>45 days</span></div>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-400">
              <span>Surprise Outflow</span>
              <span className="font-mono tabular-nums text-amber-400">{fmtRs(surpriseOutflow)}</span>
            </div>
            <input type="range" min={0} max={2500000} step={50000} value={surpriseOutflow} onChange={e => setSurpriseOutflow(Number(e.target.value))} className="w-full accent-amber-500 cursor-pointer" />
            <div className="flex justify-between text-[10px] text-slate-600"><span>₹0</span><span>₹25L</span></div>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-400">
              <span>Spend Drift</span>
              <span className="font-mono tabular-nums text-rose-400">{spendDrift}%</span>
            </div>
            <input type="range" min={0} max={30} step={1} value={spendDrift} onChange={e => setSpendDrift(Number(e.target.value))} className="w-full accent-rose-500 cursor-pointer" />
            <div className="flex justify-between text-[10px] text-slate-600"><span>0%</span><span>30%</span></div>
          </div>
        </div>

        {/* Stressed survival scores */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {financialResults.map((r) => {
            const stressed = interpolateSurvival(r);
            const baseline = r.metrics.survival_score_pct;
            const delta = stressed - baseline;
            const color = stressed >= 90 ? '#10B981' : stressed >= 70 ? '#F59E0B' : '#F43F5E';

            return (
              <div
                key={r.scenario_id}
                className="glass-card p-3 space-y-2"
                style={{ borderLeft: `3px solid ${FINANCIAL_COLORS[r.branch_type]}` }}
              >
                <div className="text-[10px] text-slate-500 font-semibold truncate">{FINANCIAL_LABELS[r.branch_type]}</div>
                <div className="font-black text-xl font-mono tabular-nums" style={{ color }}>
                  {stressed}%
                </div>
                <div className="flex items-center gap-1 text-[10px] font-mono">
                  {delta < 0 ? (
                    <><TrendingDown className="w-3 h-3 text-rose-500" /><span className="text-rose-400">{delta.toFixed(0)}%</span></>
                  ) : delta > 0 ? (
                    <><TrendingUp className="w-3 h-3 text-emerald-500" /><span className="text-emerald-400">+{delta.toFixed(0)}%</span></>
                  ) : (
                    <><Minus className="w-3 h-3 text-slate-500" /><span className="text-slate-500">0%</span></>
                  )}
                  <span className="text-slate-600 ml-auto">stressed</span>
                </div>
                <div className="w-full h-1 bg-white/8 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-300" style={{ width: `${stressed}%`, backgroundColor: color }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ─── Main Export ──────────────────────────────────────────────────────────────

export const ComparisonDashboard: React.FC<ComparisonDashboardProps> = ({ financialResults, selectedFinancialId }) => {
  if (financialResults.length === 0) return null;
  return (
    <div className="animate-in fade-in">
      <FinancialComparison financialResults={financialResults} selectedFinancialId={selectedFinancialId} />
    </div>
  );
};
