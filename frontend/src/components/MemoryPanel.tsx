import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { SignupPreferences, UserMemory } from '../types';
import { PreferenceQuestions } from './PreferenceQuestions';
import { Brain, Plus, RotateCcw, Trash2, X } from 'lucide-react';

interface MemoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  communication_style: 'How I want to be spoken to',
  task_order: 'Task order',
  constraint: 'Current constraints',
  wants: 'Goals & wants',
  preference: 'Preferences',
  routine: 'My normal day',
  other: 'Other context',
};

const SOURCE_LABELS: Record<string, string> = {
  signup: 'from sign-up',
  ai: 'learned by the AI',
  user: 'added by you',
};

/**
 * What the assistant remembers about you, and the controls to change it.
 *
 * The AI writes this table through its own tools; this panel is the other end of
 * it, so a wrong conclusion can be corrected instead of quietly steering every
 * future schedule. Discarded rows stay listed under "discarded" because the AI
 * dropping something is worth seeing — and worth being able to undo.
 */
export const MemoryPanel: React.FC<MemoryPanelProps> = ({ isOpen, onClose }) => {
  const { accessToken } = useAuth();
  const [memories, setMemories] = useState<UserMemory[]>([]);
  const [preferences, setPreferences] = useState<SignupPreferences>({});
  const [newContent, setNewContent] = useState('');
  const [newCategory, setNewCategory] = useState('preference');
  const [showQuestions, setShowQuestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError('');
    try {
      const [all, prefs] = await Promise.all([
        api.listMemories(accessToken, true),
        api.getMemoryPreferences(accessToken),
      ]);
      setMemories(all);
      setPreferences(prefs.preferences || {});
    } catch (err: any) {
      setError(err.message || 'Could not load your memory.');
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    if (isOpen) load();
  }, [isOpen, load]);

  if (!isOpen) return null;

  const active = memories.filter((m) => m.active);
  const discarded = memories.filter((m) => !m.active);

  const grouped = active.reduce<Record<string, UserMemory[]>>((acc, mem) => {
    (acc[mem.category] = acc[mem.category] || []).push(mem);
    return acc;
  }, {});

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken || !newContent.trim()) return;
    setError('');
    try {
      await api.createMemory(accessToken, { content: newContent.trim(), category: newCategory });
      setNewContent('');
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not save that.');
    }
  };

  const handleForget = async (id: number) => {
    if (!accessToken) return;
    await api.deleteMemory(accessToken, id);
    await load();
  };

  const handleRestore = async (id: number) => {
    if (!accessToken) return;
    await api.updateMemory(accessToken, id, { active: true });
    await load();
  };

  const handleSavePreferences = async () => {
    if (!accessToken) return;
    setError('');
    try {
      await api.updateMemoryPreferences(accessToken, preferences);
      setShowQuestions(false);
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not save your preferences.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-2xl max-h-[85vh] flex flex-col bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
        <div className="px-5 py-3.5 bg-slate-800/80 border-b border-slate-700 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-indigo-600/30 text-indigo-400">
              <Brain className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">What your copilot remembers</h2>
              <p className="text-[10px] text-slate-400">
                {active.length} active {active.length === 1 ? 'memory' : 'memories'} · used on every message
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {error && (
            <div className="p-3 bg-rose-950/50 border border-rose-800/60 rounded-xl text-xs text-rose-300">
              {error}
            </div>
          )}

          {loading && <p className="text-xs text-slate-400">Loading…</p>}

          {!loading && active.length === 0 && (
            <p className="text-xs text-slate-400">
              Nothing remembered yet. Tell the assistant something about how you work — or add it below.
            </p>
          )}

          {Object.entries(grouped).map(([category, items]) => (
            <div key={category}>
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-indigo-400 mb-1.5">
                {CATEGORY_LABELS[category] || category}
              </h3>
              <div className="space-y-1.5">
                {items.map((mem) => (
                  <div
                    key={mem.id}
                    className="flex items-start justify-between gap-3 px-3 py-2 rounded-xl bg-slate-800/60 border border-slate-700/60"
                  >
                    <div className="min-w-0">
                      <p className="text-xs text-slate-200">{mem.content}</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">
                        {SOURCE_LABELS[mem.source] || mem.source}
                        {mem.expires_at
                          ? ` · until ${new Date(mem.expires_at).toLocaleDateString()}`
                          : ''}
                      </p>
                    </div>
                    <button
                      onClick={() => handleForget(mem.id)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/40 transition shrink-0"
                      title="Forget this"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {discarded.length > 0 && (
            <div>
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                Discarded ({discarded.length})
              </h3>
              <div className="space-y-1.5">
                {discarded.map((mem) => (
                  <div
                    key={mem.id}
                    className="flex items-center justify-between gap-3 px-3 py-1.5 rounded-xl bg-slate-950/60 border border-slate-800"
                  >
                    <p className="text-[11px] text-slate-500 line-through truncate">{mem.content}</p>
                    <button
                      onClick={() => handleRestore(mem.id)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-400 hover:bg-indigo-950/40 transition shrink-0"
                      title="Remember this again"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-4 border-t border-slate-800">
            {showQuestions ? (
              <div className="space-y-4">
                <PreferenceQuestions answers={preferences} onChange={setPreferences} />
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSavePreferences}
                    className="px-3 py-1.5 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition"
                  >
                    Save preferences
                  </button>
                  <button
                    onClick={() => setShowQuestions(false)}
                    className="px-3 py-1.5 rounded-xl text-xs text-slate-400 hover:text-slate-200 transition"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowQuestions(true)}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold transition"
              >
                Re-answer the sign-up questions →
              </button>
            )}
          </div>
        </div>

        <form onSubmit={handleAdd} className="p-3 bg-slate-900/90 border-t border-slate-800 flex items-center gap-2 shrink-0">
          <select
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-xl px-2 py-2 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={newContent}
            onChange={(e) => setNewContent(e.target.value.slice(0, 400))}
            placeholder="Something the assistant should always keep in mind…"
            className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
          />
          <button
            type="submit"
            disabled={!newContent.trim()}
            className="p-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl transition"
            title="Remember this"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
};
