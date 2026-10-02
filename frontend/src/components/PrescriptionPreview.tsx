import type { Prescription } from '../types';

interface Props {
  prescription: Prescription | null;
}

const PrescriptionPreview = ({ prescription }: Props) => {
  if (!prescription) return null;

  const statusColor =
    prescription.status === 'APPROVED'
      ? 'bg-emerald-900 text-emerald-300'
      : prescription.status === 'REJECTED'
      ? 'bg-rose-900 text-rose-300'
      : 'bg-slate-800 text-slate-300';

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white">Prescription Preview</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor}`}>
          {prescription.status}
        </span>
      </div>

      <p className="mt-2 text-sm text-slate-300">
        <span className="text-slate-500">Diagnosis:</span> {prescription.diagnosis_summary || '-'}
      </p>

      {prescription.items.length > 0 && (
        <table className="mt-3 w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase text-slate-500">
              <th className="pb-1 pr-3">Medicine</th>
              <th className="pb-1 pr-3">Dosage</th>
              <th className="pb-1 pr-3">Frequency</th>
              <th className="pb-1 pr-3">Duration</th>
              <th className="pb-1">Route</th>
            </tr>
          </thead>
          <tbody>
            {prescription.items.map((item, idx) => (
              <tr key={idx} className="border-t border-slate-800 text-slate-200">
                <td className="py-1.5 pr-3 font-medium">{item.medicine}</td>
                <td className="py-1.5 pr-3">{item.dosage ?? '-'}</td>
                <td className="py-1.5 pr-3">{item.frequency ?? '-'}</td>
                <td className="py-1.5 pr-3">{item.duration ?? '-'}</td>
                <td className="py-1.5">{item.route ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {prescription.precautions.length > 0 && (
        <div className="mt-3">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Precautions</span>
          <ul className="mt-1 list-inside list-disc text-sm text-slate-300">
            {prescription.precautions.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-4 text-xs text-slate-500">
        ClinOps-AI is an academic prototype and clinical decision-support demonstration. AI-generated
        recommendations are not medical advice and must be independently reviewed and approved by a
        qualified doctor before use.
      </p>
    </div>
  );
};

export default PrescriptionPreview;
