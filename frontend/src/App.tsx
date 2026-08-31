import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { CalendarPage } from './pages/CalendarPage';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';

const MainApp: React.FC = () => {
  const { accessToken, loading } = useAuth();
  const [isSignup, setIsSignup] = useState(false);

  if (loading) {
    return (
      <div className="h-screen w-screen bg-slate-950 flex items-center justify-center text-slate-400">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mr-3" />
        <span className="text-sm font-medium">Loading your calendar...</span>
      </div>
    );
  }

  if (!accessToken) {
    return isSignup ? (
      <SignupPage onSwitchToLogin={() => setIsSignup(false)} />
    ) : (
      <LoginPage onSwitchToSignup={() => setIsSignup(true)} />
    );
  }

  return <CalendarPage />;
};

export function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}

export default App;
