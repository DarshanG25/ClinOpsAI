import { useRef, useState } from 'react';

interface Props {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

/**
 * Audio upload/record panel. In-browser recording uses MediaRecorder where
 * available; otherwise the user can pick a WAV/MP3/M4A file to upload.
 */
const ConversationInput = ({ onFileSelected, disabled }: Props) => {
  const [recording, setRecording] = useState(false);
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
  };

  const startRecording = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Microphone recording is not supported in this browser. Please upload a WAV/MP3/M4A file instead.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => chunksRef.current.push(e.data);
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/wav' });
        const file = new File([blob], `recording-${Date.now()}.wav`, { type: 'audio/wav' });
        onFileSelected(file);
        stream.getTracks().forEach((t) => t.stop());
      };
      mr.start();
      setRecorder(mr);
      setRecording(true);
    } catch (err) {
      setError('Could not access the microphone. Please check browser permissions, or upload a file instead.');
    }
  };

  const stopRecording = () => {
    recorder?.stop();
    setRecording(false);
    setRecorder(null);
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="font-semibold text-white">Consultation Audio</h3>
      <p className="mt-1 text-sm text-slate-400">
        Record the consultation in-browser, or upload a WAV/MP3/M4A file.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!recording ? (
          <button
            onClick={startRecording}
            disabled={disabled}
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50"
          >
            ● Start Recording
          </button>
        ) : (
          <button
            onClick={stopRecording}
            className="rounded-lg bg-slate-600 px-4 py-2 text-sm font-medium text-white hover:bg-slate-500 animate-pulse"
          >
            ■ Stop Recording
          </button>
        )}

        <span className="text-slate-500 text-sm">or</span>

        <label
          htmlFor="audio-file-input"
          aria-disabled={disabled}
          className={`rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
        >
          Upload audio file
        </label>
        <input
          id="audio-file-input"
          type="file"
          disabled={disabled}
          onChange={handleFilePick}
          className="sr-only"
        />
      </div>

      {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}
    </div>
  );
};

export default ConversationInput;
