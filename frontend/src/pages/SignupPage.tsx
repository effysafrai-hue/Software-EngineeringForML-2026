import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { PreferenceQuestions } from '../components/PreferenceQuestions';
import { SignupPreferences } from '../types';
import { Calendar, Lock, Mail, ArrowRight, ArrowLeft, Brain } from 'lucide-react';

interface SignupPageProps {
  onSwitchToLogin: () => void;
}

export const SignupPage: React.FC<SignupPageProps> = ({ onSwitchToLogin }) => {
  const { login } = useAuth();
  const [step, setStep] = useState<'account' | 'preferences'>('account');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  // The sign-up answers (requirement 2.2). Sent with the account so they are
  // long-term memory before the first message, not after the first few chats.
  const [preferences, setPreferences] = useState<SignupPreferences>({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const createAccount = async () => {
    setError('');
    setLoading(true);
    try {
      const hasAnswers = Object.keys(preferences).length > 0;
      await api.signup({ email, password, ...(hasAnswers ? { preferences } : {}) });
      const tokenData = await api.login({ email, password });
      const userData = await api.getMe(tokenData.access_token);
      login(tokenData.access_token, tokenData.refresh_token, userData);
    } catch (err: any) {
      console.error('Signup failed:', err);
      setError(err.message || 'Failed to create account. Please check password complexity.');
      // Back to the first step: a rejected email or password is fixed there, and
      // the answers already given are kept.
      setStep('account');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (step === 'account') {
      setError('');
      setStep('preferences');
      return;
    }
    createAccount();
  };

  return (
    <div className="min-h-screen w-screen bg-slate-950 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl backdrop-blur-xl">
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 mb-4">
            {step === 'account' ? <Calendar className="w-6 h-6" /> : <Brain className="w-6 h-6" />}
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            {step === 'account' ? 'Create Account' : 'Help your copilot know you'}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {step === 'account'
              ? 'Get started with your intelligent calendar copilot'
              : 'Optional — the assistant remembers these and plans around them. You can change them any time.'}
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3.5 bg-rose-950/50 border border-rose-800/60 rounded-xl text-xs text-rose-300 flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {step === 'account' ? (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="name@example.com"
                    className="w-full bg-slate-800/80 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="At least 8 chars with uppercase, number & symbol"
                    className="w-full bg-slate-800/80 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-500 active:scale-[0.99] text-white font-semibold rounded-xl text-sm shadow-lg shadow-indigo-600/30 transition flex items-center justify-center gap-2 mt-6"
              >
                <span>Continue</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </>
          ) : (
            <>
              <PreferenceQuestions answers={preferences} onChange={setPreferences} />

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-500 active:scale-[0.99] text-white font-semibold rounded-xl text-sm shadow-lg shadow-indigo-600/30 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-2 mt-6"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <span>{Object.keys(preferences).length > 0 ? 'Finish Sign Up' : 'Skip & Sign Up'}</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => setStep('account')}
                disabled={loading}
                className="w-full py-2 text-xs text-slate-400 hover:text-slate-200 transition flex items-center justify-center gap-1.5"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to account details</span>
              </button>
            </>
          )}
        </form>

        <div className="mt-8 pt-6 border-t border-slate-800 text-center">
          <p className="text-xs text-slate-400">
            Already have an account?{' '}
            <button
              type="button"
              onClick={onSwitchToLogin}
              className="text-indigo-400 hover:text-indigo-300 font-semibold hover:underline transition ml-1"
            >
              Log in
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};
