import type { ClinicalSummary } from '../types';

interface Props {
  summary: ClinicalSummary | null;
  status: string | null;
  error: string | null;
  generating?: boolean;
  onGenerate?: () => void;
}

const sectionTitles: Record<string, string> = {
  chief_complaint: 'Chief complaint',
  symptoms: 'Key symptoms',
  duration_onset: 'Duration and onset',
  severity_frequency: 'Severity and frequency',
  associated_symptoms: 'Associated symptoms',
  medical_history: 'Relevant history',
  allergies: 'Allergies',
  medications: 'Medications',
  previous_treatment: 'Previous treatment',
  measurements: 'Patient-reported measurements',
  investigations: 'Investigations and results',
  assessment: 'Doctor assessment',
  observations: 'Doctor observations',
  treatment: 'Treatment decisions',
  precautions_advice: 'Treatment / advice',
  tests_recommended: 'Tests / labs recommended',
  follow_up: 'Follow-up',
  patient_concerns: 'Patient concerns',
};

const formatTimestamp = (seconds: number | null | undefined) => {
  if (seconds == null) return 'time unavailable';
  const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
  const remainder = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${minutes}:${remainder}`;
};

export default function ClinicalSummaryPanel({
  summary, status, error, generating, onGenerate,
}: Props) {
  const segments = summary?.relevant_segments ?? [];
  const categoryList = [...new Set(segments.flatMap((segment) => segment.categories))];

  return (
    <section className="rounded-xl border border-indigo-800 bg-slate-900 p-5" aria-labelledby="clinical-summary-title">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 id="clinical-summary-title" className="font-semibold text-white">Clinical Summary</h3>
        <span className="rounded-full bg-amber-950 px-2 py-1 text-xs font-medium text-amber-300">
          AI-generated clinical summary — requires doctor verification.
        </span>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Explainable, extractive prototype. Source transcript remains unchanged.
      </p>

      {error && <p className="mt-4 text-sm text-amber-300">{error}</p>}
      {!error && !summary && status === 'failed' && (
        <p className="mt-4 text-sm text-amber-300">
          Clinical summary could not be generated. The full transcript is preserved.
        </p>
      )}
      {!summary && status === 'missing' && (
        <p className="mt-4 text-sm text-slate-400">
          No clinical summary is stored for this consultation yet.
        </p>
      )}
      {!summary && (status === 'missing' || status === 'failed') && onGenerate && (
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="mt-3 rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          {generating ? 'Generating summary…' : 'Generate clinical summary'}
        </button>
      )}
      {summary?.status === 'no_relevant_content' && (
        <p className="mt-4 text-sm text-slate-400">No clinically relevant segments were identified by the current rules.</p>
      )}

      {summary?.summary_text && (
        <div className="mt-4 whitespace-pre-wrap rounded-lg bg-slate-950 p-4 text-sm leading-6 text-slate-200">
          {summary.summary_text}
        </div>
      )}

      {summary && (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {categoryList.map((category) => {
              const entries = segments.filter((segment) => segment.categories.includes(category));
              return (
                <section key={category} className="rounded-lg border border-slate-800 p-3">
                  <h4 className="text-xs font-semibold text-indigo-300">
                    {sectionTitles[category] ?? category.replace(/_/g, ' ')}
                  </h4>
                  <ul className="mt-2 space-y-2">
                    {entries.map((segment) => (
                      <li key={segment.segment_id} className="text-sm text-slate-200">
                        <span className="mr-2 text-xs text-slate-500">
                          [{formatTimestamp(segment.start)}–{formatTimestamp(segment.end)}]
                        </span>
                        <span className="text-slate-400">{segment.speaker}: </span>
                        {segment.text}
                        <span className="ml-2 text-xs text-slate-500">
                          ({Math.round(segment.relevance_score * 100)}%)
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
          <details className="mt-4 border-t border-slate-800 pt-3">
            <summary className="cursor-pointer text-xs font-medium text-slate-400">
              Relevant conversation ({segments.length} segments)
            </summary>
            <ol className="mt-3 space-y-3">
              {segments.map((segment) => (
                <li key={segment.segment_id} className="border-l-2 border-indigo-700 pl-3">
                  <p className="text-xs text-slate-500">
                    [{formatTimestamp(segment.start)}–{formatTimestamp(segment.end)}] {segment.speaker}
                    {' · '}{segment.category.replace(/_/g, ' ')} · relevance {segment.relevance_score.toFixed(2)}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-200">{segment.text}</p>
                </li>
              ))}
            </ol>
          </details>
        </>
      )}
    </section>
  );
}
