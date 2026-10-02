interface Props {
  value: string;
  onChange: (lang: string) => void;
  className?: string;
}

const LANGUAGES: { code: string; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi' },
  { code: 'mr', label: 'Marathi' },
];

const LanguageSelector = ({ value, onChange, className }: Props) => (
  <select
    value={value}
    onChange={(e) => onChange(e.target.value)}
    className={
      className ??
      'rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white'
    }
  >
    {LANGUAGES.map((l) => (
      <option key={l.code} value={l.code}>
        {l.label}
      </option>
    ))}
  </select>
);

export default LanguageSelector;
