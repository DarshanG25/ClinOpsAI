import { useState } from 'react';
import { prescriptionPdfUrl } from '../services/api';

interface Props {
  consultationId: string;
  enabled: boolean;
}

const PdfDownloadButton = ({ consultationId, enabled }: Props) => {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    setError(null);
    setDownloading(true);
    try {
      const res = await fetch(prescriptionPdfUrl(consultationId));
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `prescription_${consultationId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not download the PDF. Make sure the prescription has been approved.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div>
      <button
        onClick={handleDownload}
        disabled={!enabled || downloading}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
      >
        {downloading ? 'Generating PDF…' : '⬇ Download Prescription PDF'}
      </button>
      {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}
    </div>
  );
};

export default PdfDownloadButton;
