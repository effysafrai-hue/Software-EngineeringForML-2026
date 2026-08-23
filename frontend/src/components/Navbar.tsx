import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Zap, LogOut, User as UserIcon } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <Link to="/calendar" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
              SE_ML_effy
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Calendar
              </span>
            </h1>
          </div>
        </Link>

        {user && (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 text-xs text-slate-300">
              <UserIcon className="w-3.5 h-3.5 text-indigo-400" />
              <span className="font-mono">{user.email}</span>
            </div>

            <button
              onClick={logout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-rose-400 hover:text-white bg-rose-500/10 hover:bg-rose-600 border border-rose-500/20 hover:border-transparent transition"
              title="Logout"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Logout</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
