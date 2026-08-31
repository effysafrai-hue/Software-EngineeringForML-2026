import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { SharedCalendar } from '../types';
import { Calendar, Users, Plus, UserPlus, Brain } from 'lucide-react';

interface CalendarSwitcherProps {
  selectedCalendarId: number | null; // null = Personal Calendar
  onSelectCalendar: (calendarId: number | null) => void;
}

export const CalendarSwitcher: React.FC<CalendarSwitcherProps> = ({
  selectedCalendarId,
  onSelectCalendar,
}) => {
  const { accessToken, user } = useAuth();
  const [sharedCalendars, setSharedCalendars] = useState<SharedCalendar[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [newCalendarName, setNewCalendarName] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteSuccess, setInviteSuccess] = useState('');

  const loadCalendars = () => {
    if (!accessToken) return;
    api.listSharedCalendars(accessToken)
      .then(setSharedCalendars)
      .catch((err) => console.error('Failed to load shared calendars:', err));
  };

  useEffect(() => {
    loadCalendars();
  }, [accessToken]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken || !newCalendarName.trim()) return;
    try {
      const created = await api.createSharedCalendar(accessToken, newCalendarName.trim());
      setNewCalendarName('');
      setShowCreateModal(false);
      loadCalendars();
      onSelectCalendar(created.id);
    } catch (err: any) {
      alert(err.message || 'Failed to create shared calendar');
    }
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken || !selectedCalendarId || !inviteEmail.trim()) return;
    try {
      await api.addSharedCalendarMember(accessToken, selectedCalendarId, inviteEmail.trim());
      setInviteSuccess(`Successfully invited ${inviteEmail}!`);
      setInviteEmail('');
      setTimeout(() => {
        setInviteSuccess('');
        setShowInviteModal(false);
      }, 1500);
    } catch (err: any) {
      if (err.status === 401) {
        alert('Your login session has expired. Please log out and log back in.');
      } else if (err.status === 404) {
        alert(`User with email "${inviteEmail}" was not found. Please ensure they have registered an account.`);
      } else if (err.status === 403) {
        alert('You do not have permission to invite members to this calendar.');
      } else {
        alert(err.message || 'Failed to invite member');
      }
    }
  };

  return (
    <div className="bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl p-3 mb-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => onSelectCalendar(null)}
            className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              selectedCalendarId === null
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            <span>My Personal Calendar</span>
          </button>

          {sharedCalendars.map((cal) => (
            <button
              key={cal.id}
              onClick={() => onSelectCalendar(cal.id)}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedCalendarId === cal.id
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              <Users className="w-3.5 h-3.5" />
              <span>{cal.name}</span>
            </button>
          ))}
        </div>

        <div className="flex items-center space-x-2">
          {selectedCalendarId !== null && (
            <button
              onClick={() => setShowInviteModal(true)}
              className="flex items-center space-x-1 px-2.5 py-1.5 bg-emerald-600/80 hover:bg-emerald-600 text-white rounded-lg text-xs font-medium transition"
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>Invite Member</span>
            </button>
          )}

          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center space-x-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Group</span>
          </button>
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl w-full max-w-sm">
            <h3 className="text-sm font-semibold text-white mb-3">Create Shared Group Calendar</h3>
            <form onSubmit={handleCreate}>
              <input
                type="text"
                value={newCalendarName}
                onChange={(e) => setNewCalendarName(e.target.value)}
                placeholder="e.g. Study Group, Project Team"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 mb-4"
                required
              />
              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 bg-slate-800 text-slate-300 hover:text-white rounded-lg text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl w-full max-w-sm">
            <h3 className="text-sm font-semibold text-white mb-3">Invite Member to Group</h3>
            {inviteSuccess ? (
              <p className="text-emerald-400 text-xs py-3">{inviteSuccess}</p>
            ) : (
              <form onSubmit={handleInvite}>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="colleague@example.com"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 mb-4"
                  required
                />
                <div className="flex justify-end space-x-2">
                  <button
                    type="button"
                    onClick={() => setShowInviteModal(false)}
                    className="px-3 py-1.5 bg-slate-800 text-slate-300 hover:text-white rounded-lg text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium"
                  >
                    Add Member
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
