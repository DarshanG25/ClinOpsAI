import type { ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

const AppLayout = ({ children }: Props) => (
  <div className="min-h-screen bg-slate-950 text-white">
    <header className="border-b border-slate-800 bg-slate-900/60 px-6 py-4">
      <div className="mx-auto flex max-w-5xl items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">ClinOps-AI</h1>
          <p className="text-xs text-slate-400">
            Multilingual AI-Assisted Prescription &amp; Clinical Recommendation System — academic prototype
          </p>
        </div>
        <span className="rounded-full border border-amber-700 bg-amber-950 px-3 py-1 text-xs font-medium text-amber-300">
          Not for real clinical use
        </span>
      </div>
    </header>
    <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
  </div>
);

export default AppLayout;
