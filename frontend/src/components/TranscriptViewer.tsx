import { useEffect, useState } from 'react';
import type { Transcript } from '../types';

interface Props {
  transcript: Transcript | null;
  loading?: boolean;
  savingRoles?: boolean;
  onSaveRoles?: (roles: Record<string, string>) => void;
}

const roleOptions = [
  'Doctor',
  'Patient',
  "Patient's Attendant/Relative",
  'Other/Unknown',
] as const;

const formatTimestamp = (seconds: number) => {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
  const remainder = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${minutes}:${remainder}`;
};

const TranscriptViewer = ({ transcript, loading, savingRoles, onSaveRoles }: Props) => {
  const [roles, setRoles] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!transcript) return;
    const nextRoles: Record<string, string> = {};
    for (const segment of transcript.segments) {
      if (segment.speaker_id && segment.speaker_role) {
        nextRoles[segment.speaker_id] = segment.speaker_role;
      }
    }
    setRoles(nextRoles);
  }, [transcript]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-slate-400 text-sm">
        <p className="mt-3 text-sm text-slate-400">
          Processing audio. The first recording may take several minutes while the speech model loads.
        </p>
      </div>
    );
  }
  if (!transcript) return null;

  const speakerIds = [...new Set(
    transcript.segments.flatMap((segment) => segment.speaker_id ? [segment.speaker_id] : []),
  )];
  const diarizationComplete = transcript.diarization_status === 'complete';

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white">Transcript</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            transcript.asr_mode === 'whisper'
              ? 'bg-emerald-900 text-emerald-300'
              : 'bg-amber-900 text-amber-300'
          }`}
        >
          {transcript.asr_mode === 'whisper' ? 'Whisper ASR' : 'DEMO mode (no model output)'}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">Language: {transcript.language}</p>
        {diarizationComplete ? (
          <>
            <p className="mt-3 text-xs text-emerald-300">Speaker diarization complete</p>
            <div className="mt-3 space-y-3">
              {transcript.segments.map((segment, index) => {
                const role = segment.speaker_id ? roles[segment.speaker_id] : null;
                return (
                  <div key={`${segment.start}-${segment.end}-${index}`} className="border-l-2 border-slate-700 pl-3">
                    <p className="text-xs font-medium text-slate-400">
                      [{formatTimestamp(segment.start)}-{formatTimestamp(segment.end)}] {role || 'Other/Unknown'}
                      {segment.speaker_id ? ` (${segment.speaker_id})` : ' (unassigned speaker)'}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-200">{segment.text}</p>
                  </div>
                );
              })}
            </div>

            {speakerIds.length > 0 && onSaveRoles && (
              <section className="mt-5 border-t border-slate-800 pt-4" aria-labelledby="speaker-roles-title">
                <h4 id="speaker-roles-title" className="text-sm font-semibold text-white">Review speaker roles</h4>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {speakerIds.map((speakerId) => (
                    <label key={speakerId} className="flex items-center justify-between gap-3 text-sm text-slate-300">
                      <span>{speakerId}</span>
                      <select
                        value={roles[speakerId] || 'Other/Unknown'}
                        onChange={(event) => setRoles((current) => ({ ...current, [speakerId]: event.target.value }))}
                        className="max-w-[65%] rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white"
                      >
                        {roleOptions.map((roleOption) => <option key={roleOption}>{roleOption}</option>)}
                      </select>
                    </label>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => onSaveRoles(roles)}
                  disabled={savingRoles}
                  className="mt-3 rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                >
                  {savingRoles ? 'Saving roles...' : 'Save speaker roles'}
                </button>
              </section>
            )}

            <details className="mt-5 border-t border-slate-800 pt-3">
              <summary className="cursor-pointer text-xs font-medium text-slate-400">Full original transcript</summary>
              <p className="mt-3 whitespace-pre-wrap text-sm text-slate-200">{transcript.text}</p>
            </details>
          </>
        ) : (
          <>
            {transcript.diarization_status && transcript.diarization_status !== 'not_run' && (
              <p className="mt-3 text-xs text-amber-300">
                Speaker diarization unavailable: {transcript.diarization_status.replace(/^unavailable: /, '')}
              </p>
            )}
            <p className="mt-3 whitespace-pre-wrap text-sm text-slate-200">{transcript.text}</p>
          </>
        )}
    </div>
  );
};

export default TranscriptViewer;
