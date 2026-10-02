import { useEffect, useState } from 'react';
import type { Recommendation } from '../types';
import type { RecommendationEditItem } from '../services/api';

interface Props {
  recommendations: Recommendation[];
  onSaveEdits: (items: RecommendationEditItem[]) => Promise<void>;
  onApprove: (diagnosisSummary: string, precautions: string[]) => Promise<void>;
  onReject: (reason: string) => Promise<void>;
  saving?: boolean;
}

type EditableRow = RecommendationEditItem & { _key: string };

const toEditable = (recs: Recommendation[]): EditableRow[] =>
  recs.map((r) => ({
    _key: r.id,
    medicine: r.medicine,
    dosage: r.dosage ?? '',
    frequency: r.frequency ?? '',
    duration: r.duration ?? '',
    route: r.route ?? '',
    reason: r.reason ?? '',
  }));

const DoctorApprovalPanel = ({ recommendations, onSaveEdits, onApprove, onReject, saving }: Props) => {
  const [rows, setRows] = useState<EditableRow[]>(toEditable(recommendations));
  const [diagnosisSummary, setDiagnosisSummary] = useState('');
  const [precautionsText, setPrecautionsText] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [showReject, setShowReject] = useState(false);

  useEffect(() => {
    setRows(toEditable(recommendations));
  }, [recommendations]);

  const updateRow = (idx: number, field: keyof RecommendationEditItem, value: string) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  };

  const removeRow = (idx: number) => setRows((prev) => prev.filter((_, i) => i !== idx));

  const addRow = () =>
    setRows((prev) => [
      ...prev,
      { _key: `new-${Date.now()}`, medicine: '', dosage: '', frequency: '', duration: '', route: '', reason: '' },
    ]);

  const handleSave = async () => {
    const items = rows.filter((r) => r.medicine.trim().length > 0).map(({ _key, ...rest }) => rest);
    await onSaveEdits(items);
  };

  const handleApprove = async () => {
    await handleSave();
    const precautions = precautionsText.split('\n').map((p) => p.trim()).filter(Boolean);
    await onApprove(diagnosisSummary, precautions);
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="font-semibold text-white">Doctor Review &amp; Edit</h3>
      <p className="mt-1 text-xs text-slate-500">
        Edit any field below. Nothing reaches the patient until you approve it.
      </p>

      <div className="mt-4 space-y-3">
        {rows.map((row, idx) => (
          <div key={row._key} className="grid grid-cols-1 gap-2 rounded-lg border border-slate-800 p-3 sm:grid-cols-6">
            <input
              value={row.medicine}
              onChange={(e) => updateRow(idx, 'medicine', e.target.value)}
              placeholder="Medicine"
              className="sm:col-span-2 rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-white"
            />
            <input
              value={row.dosage}
              onChange={(e) => updateRow(idx, 'dosage', e.target.value)}
              placeholder="Dosage"
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-white"
            />
            <input
              value={row.frequency}
              onChange={(e) => updateRow(idx, 'frequency', e.target.value)}
              placeholder="Frequency"
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-white"
            />
            <input
              value={row.duration}
              onChange={(e) => updateRow(idx, 'duration', e.target.value)}
              placeholder="Duration"
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-white"
            />
            <div className="flex gap-2">
              <input
                value={row.route}
                onChange={(e) => updateRow(idx, 'route', e.target.value)}
                placeholder="Route"
                className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-white"
              />
              <button
                onClick={() => removeRow(idx)}
                className="rounded border border-slate-700 px-2 text-slate-400 hover:text-rose-400"
                title="Remove"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
        <button onClick={addRow} className="text-sm text-indigo-400 hover:text-indigo-300">
          + Add medicine
        </button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div>
          <label className="text-xs font-medium text-slate-400">Diagnosis / Summary</label>
          <textarea
            value={diagnosisSummary}
            onChange={(e) => setDiagnosisSummary(e.target.value)}
            placeholder="Leave blank to auto-summarize from extracted diagnoses/symptoms"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-white"
            rows={3}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-400">Precautions (one per line)</label>
          <textarea
            value={precautionsText}
            onChange={(e) => setPrecautionsText(e.target.value)}
            placeholder="Leave blank to use auto-extracted precautions"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-white"
            rows={3}
          />
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          Save edits
        </button>
        <button
          onClick={handleApprove}
          disabled={saving}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          ✓ Approve &amp; Generate Prescription
        </button>
        <button
          onClick={() => setShowReject((v) => !v)}
          disabled={saving}
          className="rounded-lg bg-rose-900/60 px-4 py-2 text-sm font-medium text-rose-200 hover:bg-rose-900 disabled:opacity-50"
        >
          ✕ Reject
        </button>
      </div>

      {showReject && (
        <div className="mt-3 flex gap-2">
          <input
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            placeholder="Reason for rejection"
            className="flex-1 rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-white"
          />
          <button
            onClick={() => onReject(rejectionReason)}
            disabled={saving}
            className="rounded-lg bg-rose-700 px-4 py-2 text-sm font-medium text-white hover:bg-rose-600 disabled:opacity-50"
          >
            Confirm Reject
          </button>
        </div>
      )}
    </div>
  );
};

export default DoctorApprovalPanel;
