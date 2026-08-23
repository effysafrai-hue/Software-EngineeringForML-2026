import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Zap, Mail, Lock, AlertCircle, ArrowRight, Check } from 'lucide-react';

export const SignupPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { signup } = useAuth();
  const navigate = useNavigate();

  const isMinLength = password.length >= 8;
  const hasNumberOrSpecial = /[\d!@#$%^&*(),.?":{}|<>]/.test(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isMinLength || !hasNumberOrSpecial) {
      setError('Password does not meet minimum strength requirements.');
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await signup(email, password);
      navigate('/calendar', { replace: true });
    } catch (err: any) {
      setError(err.message || 'Signup failed. Please try a different email.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 text-slate-100">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-600 items-center justify-center shadow-xl shadow-indigo-500/25 mb-4">
          <Zap className="w-6 h-6 text-white" />
        </div>
        <h2 className="text-2xl font-extrabold tracking-tight text-white">Create Your Account</h2>
        <p className="mt-1 text-sm text-slate-400">Get started with your personal calendar</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-slate-900/90 py-8 px-6 sm:px-10 shadow-2xl rounded-2xl border border-slate-800 backdrop-blur-xl">
          {error && (
            <div className="mb-6 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start gap-2.5 text-xs text-rose-400">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Email Address
              </label>
              <div className="relative rounded-xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-950/90 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Password</label>
              <div className="relative rounded-xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-950/90 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                />
              </div>

              <div className="mt-2.5 space-y-1 text-[11px]">
                <div
                  className={`flex items-center gap-1.5 ${
                    isMinLength ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                >
                  <Check className="w-3 h-3" />
                  <span>At least 8 characters</span>
                </div>
                <div
                  className={`flex items-center gap-1.5 ${
                    hasNumberOrSpecial ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                >
                  <Check className="w-3 h-3" />
                  <span>Contains a number or symbol</span>
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !isMinLength || !hasNumberOrSpecial}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:scale-98 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-600/25 transition"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span>Create Account</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-xs text-slate-400">
            Already have an account?{' '}
            <Link
              to="/login"
              className="font-semibold text-indigo-400 hover:text-indigo-300 transition"
            >
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
