import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { SignupPreferences, SignupQuestion } from '../types';

interface PreferenceQuestionsProps {
  answers: SignupPreferences;
  onChange: (answers: SignupPreferences) => void;
}

/**
 * The long-term-memory questionnaire (requirement 2.2).
 *
 * The questions, their options and which memory category each one feeds come
 * from `GET /memory/questions` rather than being duplicated here: the server
 * turns each answer into the sentence the AI reads, so a hard-coded option value
 * that drifted from the server's mapping would silently store nothing.
 *
 * Shared by sign-up and the memory screen, so re-answering later uses the same
 * form as answering the first time.
 */
export const PreferenceQuestions: React.FC<PreferenceQuestionsProps> = ({ answers, onChange }) => {
  const [questions, setQuestions] = useState<SignupQuestion[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .getSignupQuestions()
      .then(setQuestions)
      .catch(() => setError('Could not load the questions. You can still continue without them.'));
  }, []);

  const setAnswer = (key: string, value: unknown) => {
    const next: Record<string, unknown> = { ...answers };
    // An emptied answer is removed rather than sent as "", so an untouched or
    // cleared question stores nothing at all.
    if (value === '' || value === undefined || (Array.isArray(value) && value.length === 0)) {
      delete next[key];
    } else {
      next[key] = value;
    }
    onChange(next as SignupPreferences);
  };

  const toggleInList = (key: string, value: string) => {
    const current = ((answers as Record<string, unknown>)[key] as string[]) || [];
    setAnswer(key, current.includes(value) ? current.filter((v) => v !== value) : [...current, value]);
  };

  if (error) {
    return <p className="text-[11px] text-amber-400">{error}</p>;
  }

  return (
    <div className="space-y-4">
      {questions.map((q) => {
        const value = (answers as Record<string, unknown>)[q.key];

        return (
          <div key={q.key}>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">{q.question}</label>

            {q.type === 'choice' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {(q.options || []).map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setAnswer(q.key, value === opt.value ? '' : opt.value)}
                    className={`text-left text-xs px-3 py-2 rounded-xl border transition ${
                      value === opt.value
                        ? 'bg-indigo-600/20 border-indigo-500 text-indigo-200'
                        : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:border-slate-600'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}

            {q.type === 'multi_choice' && (
              <div className="flex flex-wrap gap-1.5">
                {(q.options || []).map((opt) => {
                  const selected = (((value as string[]) || []).includes(opt.value));
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => toggleInList(q.key, opt.value)}
                      className={`text-xs px-3 py-1.5 rounded-full border transition ${
                        selected
                          ? 'bg-indigo-600/20 border-indigo-500 text-indigo-200'
                          : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:border-slate-600'
                      }`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            )}

            {q.type === 'tags' && (
              <input
                type="text"
                defaultValue={((value as string[]) || []).join(', ')}
                onBlur={(e) =>
                  setAnswer(
                    q.key,
                    e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                      .slice(0, 10)
                  )
                }
                placeholder={q.placeholder || 'Comma separated'}
                className="w-full bg-slate-800/80 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
              />
            )}

            {q.type === 'text' && (
              <input
                type="text"
                value={(value as string) || ''}
                onChange={(e) => setAnswer(q.key, e.target.value.slice(0, 300))}
                placeholder={q.placeholder || ''}
                className="w-full bg-slate-800/80 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
              />
            )}
          </div>
        );
      })}
    </div>
  );
};
