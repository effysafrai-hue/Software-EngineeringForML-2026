import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { CalendarEvent, EventInput } from '../types';
import { EventModal } from '../components/EventModal';
import { ChatPanel } from '../components/ChatPanel';
import { CalendarSwitcher } from '../components/CalendarSwitcher';
import { NotificationBell } from '../components/NotificationBell';
import { MemoryPanel } from '../components/MemoryPanel';
import { ForumPage } from './ForumPage';
import {
  format,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
  addMonths,
  subMonths,
  addWeeks,
  subWeeks,
  isToday,
} from 'date-fns';
import { ChevronLeft, ChevronRight, Plus, LogOut, Calendar as CalendarIcon, MessageSquare, Sparkles, Brain } from 'lucide-react';

export const CalendarPage: React.FC = () => {
  const { accessToken, user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<'calendar' | 'forum'>('calendar');
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<'month' | 'week'>('month');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [selectedCalendarId, setSelectedCalendarId] = useState<number | null>(null);
  const [memoryOpen, setMemoryOpen] = useState(false);
  // Bumped whenever the assistant changes its memory, so an open panel reloads
  // instead of showing what it knew before the last message.
  const [memoryVersion, setMemoryVersion] = useState(0);

  const rangeStart = view === 'month' ? startOfWeek(startOfMonth(currentDate)) : startOfWeek(currentDate);
  const rangeEnd = view === 'month' ? endOfWeek(endOfMonth(currentDate)) : endOfWeek(currentDate);

  const loadEvents = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      let data: CalendarEvent[];
      if (selectedCalendarId) {
        data = await api.listSharedCalendarEvents(
          accessToken,
          selectedCalendarId,
          rangeStart.toISOString(),
          rangeEnd.toISOString()
        );
      } else {
        data = await api.listEvents(
          accessToken,
          rangeStart.toISOString(),
          rangeEnd.toISOString()
        );
      }
      setEvents(data);
    } catch (err) {
      console.error('Failed to load events:', err);
    } finally {
      setLoading(false);
    }
  }, [accessToken, rangeStart, rangeEnd, selectedCalendarId]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const handlePrev = () => {
    if (view === 'month') setCurrentDate((d) => subMonths(d, 1));
    else setCurrentDate((d) => subWeeks(d, 1));
  };

  const handleNext = () => {
    if (view === 'month') setCurrentDate((d) => addMonths(d, 1));
    else setCurrentDate((d) => addWeeks(d, 1));
  };

  const handleToday = () => setCurrentDate(new Date());

  const handleOpenCreateModal = (date: Date) => {
    setSelectedEvent(null);
    setSelectedDate(date);
    setModalOpen(true);
  };

  const handleOpenEditModal = (event: CalendarEvent, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedEvent(event);
    setModalOpen(true);
  };

  const handleSaveEvent = async (eventInput: EventInput) => {
    if (!accessToken) return;
    if (selectedEvent) {
      if (selectedCalendarId) {
        await api.updateSharedCalendarEvent(accessToken, selectedCalendarId, selectedEvent.id, eventInput);
      } else {
        await api.updateEvent(accessToken, selectedEvent.id, eventInput);
      }
    } else {
      if (selectedCalendarId) {
        await api.createSharedCalendarEvent(accessToken, selectedCalendarId, eventInput);
      } else {
        await api.createEvent(accessToken, eventInput);
      }
    }
    await loadEvents();
  };

  const handleDeleteEvent = async (eventId: number) => {
    if (!accessToken) return;
    if (selectedCalendarId) {
      await api.deleteSharedCalendarEvent(accessToken, selectedCalendarId, eventId);
    } else {
      await api.deleteEvent(accessToken, eventId);
    }
    await loadEvents();
  };

  const daysInView = useMemo(() => {
    return eachDayOfInterval({ start: rangeStart, end: rangeEnd });
  }, [rangeStart, rangeEnd]);

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden font-sans select-none">
      {/* Top Fixed Navbar */}
      <header className="h-14 shrink-0 px-5 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between backdrop-blur-md z-20">
        <div className="flex items-center space-x-4">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 text-white">
            <CalendarIcon className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-tight flex items-center space-x-1.5">
              <span>SE_ML_effy</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded">
                Campus Hub
              </span>
            </h1>
          </div>

          {/* Navigation Tab Switcher */}
          <div className="hidden sm:flex items-center space-x-1 bg-slate-950/80 border border-slate-800 rounded-xl p-0.5 ml-4">
            <button
              onClick={() => setActiveTab('calendar')}
              className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg transition ${
                activeTab === 'calendar' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <CalendarIcon className="w-3.5 h-3.5" />
              <span>Calendar & AI</span>
            </button>
            <button
              onClick={() => setActiveTab('forum')}
              className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg transition ${
                activeTab === 'forum' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Campus Forum</span>
            </button>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setMemoryOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-indigo-950/40 hover:text-indigo-300 border border-slate-700 text-slate-400 text-xs font-semibold transition"
            title="What the assistant remembers about you"
          >
            <Brain className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Memory</span>
          </button>

          <NotificationBell />

          <div className="h-4 w-px bg-slate-800 hidden sm:block" />

          {user && (
            <span className="text-xs text-slate-400 hidden sm:inline-block">
              {user.email}
            </span>
          )}

          <button
            onClick={logout}
            className="p-2 rounded-xl bg-slate-800 hover:bg-rose-950/40 hover:text-rose-400 hover:border-rose-800/50 border border-slate-700 text-slate-400 transition"
            title="Logout"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Main Viewport */}
      {activeTab === 'forum' ? (
        <ForumPage />
      ) : (
        <main className="flex-1 min-h-0 p-4 sm:p-5 flex flex-col overflow-hidden">
          <div className="shrink-0">
            <CalendarSwitcher
              selectedCalendarId={selectedCalendarId}
              onSelectCalendar={(id) => setSelectedCalendarId(id)}
            />
          </div>

          <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-3 gap-5 overflow-hidden">
            <div className="lg:col-span-2 flex flex-col min-h-0 h-full overflow-hidden">
              <div className="shrink-0 flex items-center justify-between gap-2 mb-3">
                <div className="flex items-center space-x-2">
                  <div className="flex items-center rounded-xl bg-slate-900 border border-slate-800 p-0.5">
                    <button
                      onClick={handlePrev}
                      className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                      title="Previous"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      onClick={handleToday}
                      className="px-2.5 py-1 text-xs font-semibold text-slate-300 hover:text-white transition"
                    >
                      Today
                    </button>
                    <button
                      onClick={handleNext}
                      className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                      title="Next"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>

                  <h2 className="text-sm sm:text-base font-bold text-white tracking-tight ml-1">
                    {format(currentDate, view === 'month' ? 'MMMM yyyy' : "'Week of' MMM d, yyyy")}
                  </h2>

                  {loading && (
                    <div className="w-3.5 h-3.5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin ml-2" />
                  )}
                </div>

                <div className="flex items-center space-x-2">
                  <div className="flex items-center rounded-xl bg-slate-900 border border-slate-800 p-0.5">
                    <button
                      onClick={() => setView('month')}
                      className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition ${
                        view === 'month' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Month
                    </button>
                    <button
                      onClick={() => setView('week')}
                      className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition ${
                        view === 'week' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Week
                    </button>
                  </div>

                  <button
                    onClick={() => handleOpenCreateModal(new Date())}
                    className="flex items-center space-x-1 px-3 py-1.5 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-md shadow-indigo-600/30 active:scale-95 transition"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Event</span>
                  </button>
                </div>
              </div>

              {/* Static Calendar Matrix Grid */}
              <div className="flex-1 min-h-0 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
                <div className="shrink-0 grid grid-cols-7 border-b border-slate-800 bg-slate-950/70 text-center text-[11px] font-semibold text-slate-400 py-2">
                  <span>Sun</span>
                  <span>Mon</span>
                  <span>Tue</span>
                  <span>Wed</span>
                  <span>Thu</span>
                  <span>Fri</span>
                  <span>Sat</span>
                </div>

                <div className="flex-1 min-h-0 grid grid-cols-7 divide-x divide-y divide-slate-800/80 overflow-y-auto">
                  {daysInView.map((day) => {
                    const dayEvents = events.filter((ev) => isSameDay(new Date(ev.start_time), day));
                    const isCurrentMonth = isSameMonth(day, currentDate);
                    const isCurrentDay = isToday(day);

                    return (
                      <div
                        key={day.toISOString()}
                        onClick={() => handleOpenCreateModal(day)}
                        className={`min-h-[75px] sm:min-h-[85px] p-1.5 transition group cursor-pointer hover:bg-slate-800/30 flex flex-col justify-between ${
                          !isCurrentMonth ? 'bg-slate-950/40 text-slate-600' : 'text-slate-300'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-0.5">
                          <span
                            className={`text-[11px] font-semibold px-1.5 py-0.2 rounded-full ${
                              isCurrentDay
                                ? 'bg-indigo-600 text-white shadow-sm'
                                : isCurrentMonth
                                ? 'text-slate-300 group-hover:text-white'
                                : 'text-slate-600'
                            }`}
                          >
                            {format(day, 'd')}
                          </span>

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenCreateModal(day);
                            }}
                            className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition"
                            title="Add Event"
                          >
                            <Plus className="w-3 h-3" />
                          </button>
                        </div>

                        <div className="space-y-0.5 overflow-y-auto max-h-[55px] scrollbar-none flex-1">
                          {dayEvents.map((ev) => (
                            <div
                              key={ev.id}
                              onClick={(e) => handleOpenEditModal(ev, e)}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-950/70 hover:bg-indigo-900 border border-indigo-800/40 hover:border-indigo-500/50 text-indigo-200 transition truncate flex items-center justify-between gap-1 shadow-sm"
                              title={`${ev.title} (${format(new Date(ev.start_time), 'h:mm a')})`}
                            >
                              <span className="truncate font-medium">{ev.title}</span>
                              <span className="text-[9px] font-mono text-indigo-400 shrink-0">
                                {format(new Date(ev.start_time), 'h:mm a')}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="lg:col-span-1 min-h-0 h-full flex flex-col overflow-hidden">
              <ChatPanel
                onEventChange={loadEvents}
                onMemoryChange={() => setMemoryVersion((v) => v + 1)}
                sharedCalendarId={selectedCalendarId}
              />
            </div>
          </div>
        </main>
      )}

      <MemoryPanel key={memoryVersion} isOpen={memoryOpen} onClose={() => setMemoryOpen(false)} />

      {/* Modal Dialog */}
      <EventModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSaveEvent}
        onDelete={handleDeleteEvent}
        initialEvent={selectedEvent}
        defaultDate={selectedDate}
      />
    </div>
  );
};
