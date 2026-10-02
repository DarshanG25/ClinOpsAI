import type { ClinicalData, Recommendation } from '../types';

interface Props {
  clinicalData: ClinicalData | null;
  recommendations: Recommendation[];
  loading?: boolean;
}

const EntityChips = ({ label, items }: { label: string; items: { text: string }[] }) => {
  if (items.length === 0) return null;
  return (
    <div className="mb-2">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {items.map((item, idx) => (
          <span key={idx} className="rounded-full bg-slate-800 px-2.5 py-1 text-xs text-slate-200">
            {item.text}
          </span>
        ))}
      </div>
    </div>
  );
};

const RecommendationPanel = ({ clinicalData, recommendations, loading }: Props) => {
  if (loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-slate-400 text-sm">
        Extracting clinical data and generating recommendations…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {clinicalData && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <h3 className="font-semibold text-white">Extracted Clinical Data</h3>
          <div className="mt-3">
            <EntityChips label="Symptoms" items={clinicalData.symptoms} />
            <EntityChips label="Diagnoses" items={clinicalData.diagnoses} />
            <EntityChips label="Medications" items={clinicalData.medications} />
            <EntityChips label="Precautions" items={clinicalData.precautions} />
          </div>
          {clinicalData.symptoms.length === 0 &&
            clinicalData.diagnoses.length === 0 &&
            clinicalData.medications.length === 0 &&
            clinicalData.precautions.length === 0 && (
              <p className="text-sm text-slate-500">No clinical entities detected in this transcript.</p>
            )}
        </div>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <h3 className="font-semibold text-white">AI Candidate Recommendations</h3>
        <p className="mt-1 text-xs text-slate-500">
          "Score" = Recommendation Relevance Score (0–1), not a medical probability. Doctor review required.
        </p>
        {recommendations.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No candidates generated yet.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase text-slate-500">
                  <th className="pb-2 pr-3">Medicine</th>
                  <th className="pb-2 pr-3">Dosage</th>
                  <th className="pb-2 pr-3">Frequency</th>
                  <th className="pb-2 pr-3">Duration</th>
                  <th className="pb-2 pr-3">Score</th>
                  <th className="pb-2">Reason</th>
                </tr>
              </thead>
              <tbody>
                {recommendations.map((rec) => (
                  <tr key={rec.id} className="border-t border-slate-800 text-slate-200">
                    <td className="py-2 pr-3 font-medium">{rec.medicine}</td>
                    <td className="py-2 pr-3">{rec.dosage ?? '-'}</td>
                    <td className="py-2 pr-3">{rec.frequency ?? '-'}</td>
                    <td className="py-2 pr-3">{rec.duration ?? '-'}</td>
                    <td className="py-2 pr-3">
                      <span className="rounded bg-indigo-900 px-1.5 py-0.5 text-xs text-indigo-300">
                        {rec.score.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2 text-xs text-slate-400">{rec.reason ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default RecommendationPanel;
