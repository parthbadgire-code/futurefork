import React, { useCallback, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, Database, FileText, Loader2, Upload } from 'lucide-react';
import { api } from '../api/client';
import { ColumnMapping, ColumnRole, DatasetType, InspectResponse } from '../contracts/types';
import { SAMPLE_DATASETS } from '../mocks/fixtures';

interface UploadIngestorProps {
  onDatasetReady: (datasetId: string, name: string, datasetType: DatasetType) => void;
}

const COLUMN_ROLES: ColumnRole[] = [
  'date_col', 'amount_col', 'debit_col', 'credit_col', 'type_col', 'category_col', 'description_col',
];

const ROLE_LABELS: Record<ColumnRole | 'ignore', string> = {
  date_col: '📅 Date',
  amount_col: '₹ Signed / single amount',
  debit_col: '↘ Debit (money out)',
  credit_col: '↗ Credit (money in)',
  type_col: '⇄ Type (inflow / outflow)',
  category_col: '🏷 Category',
  description_col: '📝 Description',
  ignore: '✕ Ignore',
};

const DATASET_TYPE_LABELS: Record<DatasetType, string> = {
  personal: 'Personal',
  institute: 'Institute',
  startup: 'Startup',
};

export const UploadIngestor: React.FC<UploadIngestorProps> = ({ onDatasetReady }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [inspectResult, setInspectResult] = useState<InspectResponse | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping | null>(null);
  const [datasetType, setDatasetType] = useState<DatasetType>('personal');
  const [openingBalance, setOpeningBalance] = useState('');
  const [datasetName, setDatasetName] = useState('');
  const [isInspecting, setIsInspecting] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFile = async (file: File) => {
    setError(null);
    setIsInspecting(true);
    setInspectResult(null);
    try {
      const result = await api.inspectDataset(file);
      setInspectResult(result);
      setMapping(result.proposed_mapping);
      setDatasetType(result.dataset_type);
      setDatasetName(file.name.replace(/\.csv$/i, '').replace(/[_-]+/g, ' '));
      setOpeningBalance('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to inspect file');
    } finally {
      setIsInspecting(false);
    }
  };

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) await processFile(file);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const roleOf = (col: string): ColumnRole | 'ignore' =>
    (mapping && COLUMN_ROLES.find((r) => mapping[r] === col)) || 'ignore';

  const setRole = (col: string, role: ColumnRole | 'ignore') => {
    if (!mapping) return;
    const next: ColumnMapping = { ...mapping };
    COLUMN_ROLES.forEach((r) => {
      if (next[r] === col) (next[r] as string | null) = r === 'date_col' ? '' : null;
    });
    if (role !== 'ignore') (next[role] as string | null) = col;
    setMapping(next);
  };

  const hasAmounts = !!mapping && (!!mapping.amount_col || !!mapping.debit_col || !!mapping.credit_col);

  const handleCommit = async () => {
    if (!inspectResult || !mapping) return;
    const balance = openingBalance.trim() ? parseFloat(openingBalance.replace(/[,₹\s]/g, '')) : undefined;
    if (balance !== undefined && isNaN(balance)) {
      setError('Opening balance must be a number, e.g. 285000.');
      return;
    }
    setIsCommitting(true);
    setError(null);
    try {
      const result = await api.commitDataset({
        upload_id: inspectResult.upload_id,
        confirmed_mapping: mapping,
        dataset_name: datasetName || undefined,
        starting_balance: balance,
        dataset_type: datasetType,
      });
      onDatasetReady(result.dataset_id, result.name, result.dataset_type);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to build the baseline');
    } finally {
      setIsCommitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Sample datasets */}
      <div className="glass-card p-5">
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-2">
          <Database className="w-3.5 h-3.5" />
          Quick Start: Use a Sample Dataset
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {SAMPLE_DATASETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => onDatasetReady(preset.id, preset.name, preset.dataset_type)}
              className="p-3 rounded-xl text-left border border-white/10 bg-white/5 hover:bg-emerald-500/10
                         hover:border-emerald-500/40 transition-all duration-200"
            >
              <div className="text-xs font-semibold text-slate-200">{preset.label}</div>
              <div className="text-[11px] text-slate-500 mt-1 leading-snug">{preset.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`glass-card p-10 flex flex-col items-center justify-center gap-4 cursor-pointer
                    border-2 border-dashed transition-all duration-200 rounded-2xl
                    ${isDragging ? 'border-emerald-500/60 bg-emerald-500/10 shadow-glow' : 'border-white/15 hover:border-emerald-500/40 hover:bg-white/8'}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={async (e) => { const f = e.target.files?.[0]; if (f) await processFile(f); }}
        />
        {isInspecting ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-10 h-10 text-emerald-400 animate-spin" />
            <span className="text-sm text-slate-400">Inspecting file…</span>
          </div>
        ) : (
          <>
            <div className={`w-16 h-16 rounded-2xl flex items-center justify-center ${isDragging ? 'bg-emerald-500/20' : 'bg-white/5'}`}>
              <Upload className={`w-8 h-8 ${isDragging ? 'text-emerald-400' : 'text-slate-500'}`} />
            </div>
            <div className="text-center space-y-1">
              <p className="text-sm font-semibold text-slate-300">Drop your CSV here</p>
              <p className="text-xs text-slate-500">or click to browse: bank / UPI statements, ERP ledgers, P&L exports</p>
            </div>
          </>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {inspectResult && mapping && (
        <div className="space-y-5 animate-in fade-in">
          <div className="glass-card p-4 flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <FileText className="w-4 h-4 text-slate-500" />
            <span>{inspectResult.filename}</span>
            <span className="text-slate-600">|</span>
            <span>{inspectResult.headers.length} columns</span>
            <span className="text-slate-600">|</span>
            <span>
              Mapping proposed by {inspectResult.mapping_source === 'llm' ? 'AI' : 'rules'} (
              {Math.round(inspectResult.mapping_confidence * 100)}% confidence)
            </span>
          </div>

          {/* Column mapping */}
          <div className="glass-card p-5 space-y-3">
            <h4 className="text-sm font-bold text-slate-200">Map Columns</h4>
            <p className="text-xs text-slate-500">
              Use either one signed amount column (optionally with a type column), or separate debit and credit columns.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {inspectResult.headers.map((col) => (
                <div key={col} className="space-y-1">
                  <div className="text-[11px] text-slate-500 truncate font-mono">{col}</div>
                  <div className="relative">
                    <select
                      value={roleOf(col)}
                      onChange={(e) => setRole(col, e.target.value as ColumnRole | 'ignore')}
                      className="w-full dark-input text-xs py-2 pr-7 appearance-none cursor-pointer"
                    >
                      {[...COLUMN_ROLES, 'ignore' as const].map((role) => (
                        <option key={role} value={role} className="bg-[#0F1623]">{ROLE_LABELS[role]}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500 pointer-events-none" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Preview */}
          <div className="glass-card p-5 space-y-3 overflow-x-auto">
            <h4 className="text-sm font-bold text-slate-200">Preview</h4>
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="border-b border-white/10">
                  {inspectResult.headers.map((col) => (
                    <th key={col} className="pb-2 pr-4 text-slate-500 font-medium whitespace-nowrap">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {inspectResult.preview_rows.map((row, i) => (
                  <tr key={i} className="border-b border-white/5">
                    {inspectResult.headers.map((col) => (
                      <td key={col} className="py-2 pr-4 text-slate-300 font-mono tabular-nums whitespace-nowrap">{row[col] || '—'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Parameters */}
          <div className="glass-card p-5 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1">
              <label className="text-xs text-slate-400 font-medium">Dataset name</label>
              <input value={datasetName} onChange={(e) => setDatasetName(e.target.value)} className="dark-input w-full" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-400 font-medium">Opening balance (₹, optional)</label>
              <input
                value={openingBalance}
                onChange={(e) => setOpeningBalance(e.target.value)}
                className="dark-input w-full font-mono tabular-nums"
                placeholder="e.g. 285000"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-slate-400 font-medium">Dataset type</label>
              <select value={datasetType} onChange={(e) => setDatasetType(e.target.value as DatasetType)} className="dark-input w-full">
                {(Object.keys(DATASET_TYPE_LABELS) as DatasetType[]).map((t) => (
                  <option key={t} value={t} className="bg-[#0F1623]">{DATASET_TYPE_LABELS[t]}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={handleCommit}
            disabled={isCommitting || !mapping.date_col || !hasAmounts}
            className="w-full py-4 rounded-2xl font-bold text-sm flex items-center justify-center gap-2
                       bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400
                       text-white shadow-glow transition-all duration-200
                       disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none"
          >
            {isCommitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Building baseline…</> : <><CheckCircle2 className="w-4 h-4" /> Build Baseline (Node 0)</>}
          </button>
        </div>
      )}
    </div>
  );
};
