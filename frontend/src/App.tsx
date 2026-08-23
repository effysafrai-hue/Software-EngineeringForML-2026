import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Server,
  Database,
  Layers,
  Code2,
  Terminal,
  Zap,
} from 'lucide-react';

interface HealthResponse {
  status: string;
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const checkHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    const start = performance.now();
    try {
      const response = await fetch(`${apiUrl}/health`);
      const elapsed = Math.round(performance.now() - start);
      setLatency(elapsed);

      if (!response.ok) {
        throw new Error(`HTTP Error ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setHealth(data);
      setLastChecked(new Date());
    } catch (err: unknown) {
      const elapsed = Math.round(performance.now() - start);
      setLatency(elapsed);
      const message = err instanceof Error ? err.message : 'Failed to reach backend';
      setError(message);
      setHealth(null);
      setLastChecked(new Date());
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  const isHealthy = health?.status === 'ok';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Background Decorative Gradients */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        <div className="absolute top-1/3 -right-40 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 left-1/3 w-96 h-96 bg-cyan-600/15 rounded-full blur-3xl" />
      </div>

      {/* Navigation Header */}
      <header className="relative z-10 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                SE_ML_effy
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  v0.1.0-skeleton
                </span>
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <a
              href={`${apiUrl}/docs`}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-medium text-slate-400 hover:text-indigo-400 transition-colors flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 hover:border-indigo-500/30 bg-slate-900/40"
            >
              <Code2 className="w-3.5 h-3.5" />
              API Docs (Swagger)
            </a>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="relative z-10 flex-1 max-w-6xl mx-auto px-6 py-12 w-full">
        {/* Hero Section */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent mb-3">
            Full-Stack Project Scaffold
          </h2>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            FastAPI + SQLAlchemy + Alembic backend connected with Vite + React + TypeScript + Tailwind CSS and PostgreSQL 16.
          </p>
        </div>

        {/* Primary Health Status Card */}
        <div className="max-w-xl mx-auto mb-12">
          <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-2xl blur opacity-30 group-hover:opacity-50 transition duration-500" />
            
            <div className="relative rounded-2xl bg-slate-900/90 border border-slate-800 p-6 sm:p-8 backdrop-blur-xl shadow-2xl">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/50">
                    <Activity className="w-6 h-6 text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-base">Backend Health Probe</h3>
                    <p className="text-xs text-slate-400 font-mono">GET {apiUrl}/health</p>
                  </div>
                </div>

                <button
                  onClick={checkHealth}
                  disabled={loading}
                  className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-indigo-600/20"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  {loading ? 'Probing...' : 'Refresh'}
                </button>
              </div>

              {/* Status Display Area */}
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  {loading ? (
                    <div className="w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
                  ) : isHealthy ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <XCircle className="w-5 h-5 text-rose-400" />
                  )}

                  <div>
                    <div className="text-sm font-semibold text-white flex items-center gap-2">
                      <span>Status:</span>
                      {loading ? (
                        <span className="text-slate-400">Connecting...</span>
                      ) : isHealthy ? (
                        <span className="text-emerald-400 uppercase tracking-wider font-mono text-xs px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                          {health?.status}
                        </span>
                      ) : (
                        <span className="text-rose-400 uppercase tracking-wider font-mono text-xs px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20">
                          Offline / Error
                        </span>
                      )}
                    </div>
                    {error && <p className="text-xs text-rose-400 mt-1 font-mono">{error}</p>}
                  </div>
                </div>

                {latency !== null && (
                  <div className="text-right">
                    <span className="text-xs font-mono text-slate-400 block">Latency</span>
                    <span className={`text-xs font-mono font-semibold ${latency < 100 ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {latency} ms
                    </span>
                  </div>
                )}
              </div>

              {/* Raw JSON Payload */}
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-slate-400">Raw Backend Response:</span>
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/60 font-mono text-xs text-indigo-300">
                  {loading ? (
                    <span className="text-slate-500 italic">Awaiting response...</span>
                  ) : health ? (
                    <code>{JSON.stringify(health, null, 2)}</code>
                  ) : (
                    <code className="text-rose-400">null</code>
                  )}
                </div>
              </div>

              {lastChecked && (
                <p className="text-[11px] text-slate-500 text-center mt-4">
                  Last verified at {lastChecked.toLocaleTimeString()}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Stack Overview Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur">
            <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4">
              <Server className="w-5 h-5" />
            </div>
            <h4 className="font-semibold text-white text-sm mb-1">FastAPI Backend</h4>
            <p className="text-xs text-slate-400 mb-3">
              Python 3.12 with Uvicorn hot reloading and CORS middleware enabled.
            </p>
            <div className="text-[11px] font-mono text-indigo-400 bg-indigo-950/40 border border-indigo-900/40 rounded px-2 py-1 inline-block">
              :8000/health
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4">
              <Layers className="w-5 h-5" />
            </div>
            <h4 className="font-semibold text-white text-sm mb-1">React + Vite + Tailwind</h4>
            <p className="text-xs text-slate-400 mb-3">
              TypeScript SPA with fast HMR and Tailwind CSS utility styling.
            </p>
            <div className="text-[11px] font-mono text-cyan-400 bg-cyan-950/40 border border-cyan-900/40 rounded px-2 py-1 inline-block">
              :5173
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4">
              <Database className="w-5 h-5" />
            </div>
            <h4 className="font-semibold text-white text-sm mb-1">PostgreSQL 16</h4>
            <p className="text-xs text-slate-400 mb-3">
              Configured via DATABASE_URL with empty Alembic migration support.
            </p>
            <div className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-900/40 rounded px-2 py-1 inline-block">
              :5432 (volume saved)
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-slate-800/80 bg-slate-900/40 py-6 text-center text-xs text-slate-500">
        <div className="flex items-center justify-center gap-2">
          <Terminal className="w-3.5 h-3.5 text-indigo-400" />
          <span>Ready to execute: <code className="text-slate-300">docker compose up --build</code></span>
        </div>
      </footer>
    </div>
  );
}
