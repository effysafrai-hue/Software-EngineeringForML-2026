import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { AppNotification } from '../types';
import { Bell, Check, CheckCheck, Clock, Calendar as CalendarIcon, Sparkles } from 'lucide-react';
import { format } from 'date-fns';

export const NotificationBell: React.FC = () => {
  const { accessToken } = useAuth();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [hasNew, setHasNew] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const loadNotifications = () => {
    if (!accessToken) return;
    api.listNotifications(accessToken)
      .then((data) => {
        setNotifications(data);
      })
      .catch((err) => console.error('Failed to load notifications:', err));
  };

  useEffect(() => {
    loadNotifications();
  }, [accessToken]);

  // Real-time WebSocket connection
  useEffect(() => {
    if (!accessToken) return;

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const wsUrl = apiUrl.replace(/^http/, 'ws') + `/ws/notifications?token=${accessToken}`;

    let ws: WebSocket | null = null;
    let pingInterval: any = null;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        pingInterval = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'notification') {
            const newNotif: AppNotification = {
              id: payload.id || Date.now(),
              user_id: payload.user_id || 0,
              event_id: payload.event_id,
              message: payload.message,
              read: false,
              created_at: new Date().toISOString(),
              event_title: payload.event_title,
            };
            setNotifications((prev) => [newNotif, ...prev]);
            setHasNew(true);
          }
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };

      ws.onerror = (err) => {
        console.warn('WebSocket connection warning (fallback to HTTP):', err);
      };
    } catch (e) {
      console.warn('WebSocket init failed:', e);
    }

    return () => {
      if (pingInterval) clearInterval(pingInterval);
      if (ws) ws.close();
    };
  }, [accessToken]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleToggle = () => {
    setIsOpen(!isOpen);
    setHasNew(false);
  };

  const handleMarkRead = async (notifId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!accessToken) return;
    try {
      await api.markNotificationRead(accessToken, notifId);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notifId ? { ...n, read: true } : n))
      );
    } catch (err) {
      console.error('Failed to mark read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    if (!accessToken) return;
    try {
      await api.markAllNotificationsRead(accessToken);
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    } catch (err) {
      console.error('Failed to mark all read:', err);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={handleToggle}
        className="relative p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white transition active:scale-95"
        title="Notifications"
      >
        <Bell className={`w-4 h-4 ${hasNew ? 'animate-bounce text-amber-400' : ''}`} />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white shadow-lg shadow-indigo-500/50">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl z-50 overflow-hidden backdrop-blur-xl animate-in fade-in zoom-in-95 duration-100">
          <div className="p-3.5 bg-slate-800/80 border-b border-slate-700/80 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Bell className="w-4 h-4 text-indigo-400" />
              <h3 className="text-xs font-bold text-white">Event Reminders</h3>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.5 bg-indigo-500/20 text-indigo-300 rounded text-[10px] font-medium border border-indigo-500/30">
                  {unreadCount} new
                </span>
              )}
            </div>

            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center space-x-1 transition"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>Mark all read</span>
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-slate-800/60">
            {notifications.length === 0 ? (
              <div className="p-6 text-center text-slate-400">
                <Sparkles className="w-6 h-6 mx-auto text-slate-600 mb-2" />
                <p className="text-xs font-medium">No upcoming notifications</p>
                <p className="text-[10px] text-slate-500 mt-0.5">
                  You'll be alerted 30 minutes before your scheduled events!
                </p>
              </div>
            ) : (
              notifications.map((notif) => (
                <div
                  key={notif.id}
                  className={`p-3 transition flex items-start justify-between gap-3 ${
                    notif.read ? 'bg-slate-900/40 text-slate-400' : 'bg-slate-800/40 text-slate-200'
                  }`}
                >
                  <div className="flex items-start space-x-2.5 flex-1 min-w-0">
                    <div
                      className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${
                        notif.read ? 'bg-slate-800 text-slate-500' : 'bg-indigo-600/20 text-indigo-400'
                      }`}
                    >
                      <Clock className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs leading-snug ${notif.read ? 'font-normal' : 'font-semibold text-white'}`}>
                        {notif.message}
                      </p>
                      <span className="text-[10px] text-slate-500 mt-1 block">
                        {format(new Date(notif.created_at), 'MMM d, h:mm a')}
                      </span>
                    </div>
                  </div>

                  {!notif.read && (
                    <button
                      onClick={(e) => handleMarkRead(notif.id, e)}
                      className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition shrink-0"
                      title="Mark as read"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
