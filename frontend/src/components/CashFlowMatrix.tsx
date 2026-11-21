import React, { useState } from 'react';
import { FinancialScenarioResult, CashFlowMatrixData } from '../contracts/types';
import { Lock, Unlock, Eye, GitCompare } from 'lucide-react';

interface CashFlowMatrixProps {
  result: FinancialScenarioResult | null;
  baselineResult: FinancialScenarioResult | null;
  showDiff: boolean;
}

interface TooltipData {
  x: number;
  y: number;
  category: string;
  month: string;
  value: number;
  delta?: number;
}

function getSpendColor(value: number, maxValue: number, isFixed: boolean): string {
  if (value === 0) return 'bg-white/3 text-slate-600';
  const intensity = value / maxValue;
  if (isFixed) {
    if (intensity > 0.8) return 'bg-cyan-500/20 text-cyan-300';
    if (intensity > 0.5) return 'bg-cyan-500/12 text-cyan-400';
    return 'bg-cyan-500/6 text-cyan-500';
  }
  if (intensity > 0.85) return 'bg-rose-500/30 text-rose-300';
  if (intensity > 0.65) return 'bg-rose-500/18 text-rose-400';
  if (intensity > 0.4)  return 'bg-amber-500/15 text-amber-400';
  return 'bg-white/5 text-slate-400';
}

function getDeltaColor(delta: number): string {
  if (delta > 0) return 'text-rose-400';
  if (delta < 0) return 'text-emerald-400';
  return 'text-slate-500';
}

const fmtK = (v: number) => {
  if (v === 0) return '—';
  if (Math.abs(v) >= 100000) return `${(v / 100000).toFixed(1)}L`;
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(0)}K`;
  return v.toString();
};

export const CashFlowMatrix: React.FC<CashFlowMatrixProps> = ({ result, baselineResult, showDiff }) => {
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [highlightedMonth, setHighlightedMonth] = useState<number | null>(null);

  if (!result) {
    return (
      <div className="glass-card p-10 flex items-center justify-center text-slate-500 text-sm">
        Select a scenario to view the cash flow matrix
      </div>
    );
  }

  const cashFlow = result.cash_flow;
  const baselineCashFlow: CashFlowMatrixData | null = baselineResult?.cash_flow ?? null;

  // Max per category for colour scaling
  const maxValues = cashFlow.categories.reduce<Record<string, number>>((acc, cat) => {
    acc[cat.name] = Math.max(...cat.values, 1);
    return acc;
  }, {});

  const isChanged = (catName: string, monthIdx: number): boolean => {
    if (!baselineCashFlow) return false;
    const baseCat = baselineCashFlow.categories.find(c => c.name === catName);
    const curCat = cashFlow.categories.find(c => c.name === catName);
    if (!baseCat || !curCat) return false;
    return baseCat.values[monthIdx] !== curCat.values[monthIdx];
  };

  const getDelta = (catName: string, monthIdx: number): number => {
    if (!baselineCashFlow) return 0;
    const baseCat = baselineCashFlow.categories.find(c => c.name === catName);
    const curCat = cashFlow.categories.find(c => c.name === catName);
    if (!baseCat || !curCat) return 0;
    return curCat.values[monthIdx] - baseCat.values[monthIdx];
  };

  const fixedCats = cashFlow.categories.filter(c => c.type === 'fixed');
  const flexCats  = cashFlow.categories.filter(c => c.type === 'flexible');

  const renderCell = (cat: CashFlowMatrixData['categories'][0], monthIdx: number, key: string) => {
    const val = cat.values[monthIdx];
    const changed = showDiff && isChanged(cat.name, monthIdx);
    const delta = showDiff ? getDelta(cat.name, monthIdx) : 0;
    const isHighlight = highlightedMonth === monthIdx;
    const dimmed = showDiff && !changed;

    const colorClass = getSpendColor(val, maxValues[cat.name], cat.type === 'fixed');

    return (
      <td
        key={key}
        className={`relative text-center text-[11px] font-mono tabular-nums py-1.5 px-1 cursor-pointer
                    transition-all duration-150 border-r border-white/5
                    ${colorClass}
                    ${isHighlight ? 'ring-1 ring-inset ring-cyan-500/50' : ''}
                    ${dimmed ? 'opacity-25' : ''}
                    ${changed ? 'ring-1 ring-inset ring-amber-500/60' : ''}
                    hover:opacity-100 hover:ring-1 hover:ring-inset hover:ring-white/30`}
        onMouseEnter={(e) => {
          const rect = (e.target as HTMLElement).getBoundingClientRect();
          setTooltip({ x: rect.left, y: rect.top - 60, category: cat.name, month: cashFlow.months[monthIdx], value: val, delta });
          setHighlightedMonth(monthIdx);
        }}
        onMouseLeave={() => { setTooltip(null); setHighlightedMonth(null); }}
      >
        {fmtK(val)}
        {changed && delta !== 0 && (
          <span className={`absolute top-0.5 right-0.5 text-[8px] font-bold leading-none ${getDeltaColor(delta)}`}>
            {delta > 0 ? '+' : ''}{fmtK(delta)}
          </span>
        )}
      </td>
    );
  };

  const renderCategoryGroup = (cats: CashFlowMatrixData['categories'], isFixed: boolean) => (
    <>
      {cats.map((cat) => (
        <tr key={cat.name} className="border-b border-white/5 hover:bg-white/3 group">
          <td className="py-2 pl-4 pr-3 text-xs font-medium text-slate-300 whitespace-nowrap sticky left-0 bg-[#0F1623] z-10 border-r border-white/8">
            <div className="flex items-center gap-1.5">
              {isFixed ? (
                <Lock className="w-3 h-3 text-slate-500 shrink-0" />
              ) : (
                <Unlock className="w-3 h-3 text-slate-600 shrink-0" />
              )}
              {cat.name}
            </div>
          </td>
          {cashFlow.months.map((_, mIdx) => renderCell(cat, mIdx, `${cat.name}-${mIdx}`))}
        </tr>
      ))}
    </>
  );

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/8">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-bold text-slate-200">12-Month Cash Flow Matrix</span>
          <span className="text-xs text-slate-500 font-mono ml-1">8 categories × 12 months</span>
        </div>
        {showDiff && (
          <div className="flex items-center gap-1.5 text-xs text-amber-400 border border-amber-500/30 rounded-lg px-2.5 py-1 bg-amber-500/10">
            <GitCompare className="w-3.5 h-3.5" />
            Diff vs Baseline
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex gap-3 px-4 py-2 text-[10px] border-b border-white/5 bg-white/2">
        <span className="flex items-center gap-1 text-slate-500"><Lock className="w-2.5 h-2.5 text-slate-600" /> Fixed</span>
        <span className="flex items-center gap-1 text-slate-500"><Unlock className="w-2.5 h-2.5 text-slate-600" /> Flexible</span>
        <span className="flex items-center gap-1 text-rose-500">■ High spend</span>
        <span className="flex items-center gap-1 text-amber-500">■ Mid spend</span>
        <span className="flex items-center gap-1 text-slate-600">■ Low spend</span>
        {showDiff && <span className="flex items-center gap-1 text-amber-400">◇ Changed</span>}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse min-w-[700px]">
          <thead>
            <tr className="border-b border-white/10 bg-white/3">
              <th className="py-2 pl-4 pr-3 text-left text-xs font-semibold text-slate-500 sticky left-0 bg-[#0F1623] z-10 w-28 border-r border-white/8">
                Category
              </th>
              {cashFlow.months.map((m, i) => (
                <th
                  key={m}
                  className={`text-center text-[10px] font-semibold py-2 px-1 text-slate-500 cursor-pointer
                              transition-colors hover:text-slate-200 border-r border-white/5
                              ${highlightedMonth === i ? 'text-cyan-400' : ''}`}
                  onClick={() => setHighlightedMonth(highlightedMonth === i ? null : i)}
                >
                  {m}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {/* Fixed section header */}
            <tr className="bg-cyan-500/5 border-b border-white/5">
              <td colSpan={13} className="py-1 pl-4 text-[10px] font-bold uppercase tracking-widest text-cyan-500/70">
                Fixed Costs
              </td>
            </tr>
            {renderCategoryGroup(fixedCats, true)}

            {/* Flexible section header */}
            <tr className="bg-amber-500/5 border-b border-white/5">
              <td colSpan={13} className="py-1 pl-4 text-[10px] font-bold uppercase tracking-widest text-amber-500/70">
                Flexible Costs
              </td>
            </tr>
            {renderCategoryGroup(flexCats, false)}
          </tbody>
        </table>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none bg-[#0F1623] border border-white/20 rounded-xl px-3 py-2 shadow-glass text-xs"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="font-bold text-slate-200">{tooltip.category} · {tooltip.month}</div>
          <div className="font-mono tabular-nums text-emerald-400">₹{tooltip.value.toLocaleString('en-IN')}</div>
          {showDiff && tooltip.delta !== undefined && tooltip.delta !== 0 && (
            <div className={`font-mono tabular-nums text-xs ${getDeltaColor(tooltip.delta)}`}>
              Δ {tooltip.delta > 0 ? '+' : ''}₹{tooltip.delta.toLocaleString('en-IN')} vs baseline
            </div>
          )}
        </div>
      )}
    </div>
  );
};
