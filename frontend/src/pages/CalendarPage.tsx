import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { CalendarEvent, EventInput } from '../types';
import { EventModal } from '../components/EventModal';
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
import { ChevronLeft, ChevronRight, Plus, Calendar as CalendarIcon, Clock } from 'lucide-react';

export const CalendarPage: React.FC = () => {
  const { accessToken } = useAuth();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<'month' | 'week'>('month');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());

  const { rangeStart, rangeEnd } = useMemo(() => {
    if (view === 'month') {
      const monthStart = startOfMonth(currentDate);
      const monthEnd = endOfMonth(currentDate);
      return {
        rangeStart: startOfWeek(monthStart),
        rangeEnd: endOfWeek(monthEnd),
      };
    } else {
      return {
        rangeStart: startOfWeek(currentDate),
        rangeEnd: endOfWeek(currentDate),
      };
    }
  }, [currentDate, view]);

  const loadEvents = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await api.listEvents(
        accessToken,
        rangeStart.toISOString(),
        rangeEnd.toISOString()
      );
      setEvents(data);
    } catch (err) {
      console.error('Failed to load events:', err);
    } finally {
      setLoading(false);
    }
  }, [accessToken, rangeStart, rangeEnd]);

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

  const handleToday = () => {
    setCurrentDate(new Date());
  };

  const handleOpenCreateModal = (date?: Date) => {
    setSelectedEvent(null);
    setSelectedDate(date || new Date());
    setModalOpen(true);
  };

  const handleOpenEditModal = (event: CalendarEvent, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedEvent(event);
    setModalOpen(true);
  };

  const handleSaveEvent = async (eventData: EventInput, eventId?: number) => {
    if (!accessToken) return;
    if (eventId) {
      await api.updateEvent(accessToken, eventId, eventData);
    } else {
      await api.createEvent(accessToken, eventData);
    }
    await loadEvents();
  };

  const handleDeleteEvent = async (eventId: number) => {
    if (!accessToken) return;
    await api.deleteEvent(accessToken, eventId);
    await loadEvents();
  };

  const daysInView = useMemo(() => {
    return eachDayOfInterval({ start: rangeStart, end: rangeEnd });
  }, [rangeStart, rangeEnd]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
      {/* Calendar Controls & Navigation Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-xl bg-slate-900 border border-slate-800 p-1">
            <button
              onClick={handlePrev}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Previous"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={handleToday}
              className="px-3 py-1 text-xs font-semibold text-slate-300 hover:text-white transition"
            >
              Today
            </button>
            <button
              onClick={handleNext}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Next"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <h2 className="text-xl font-bold text-white tracking-tight">
            {format(currentDate, view === 'month' ? 'MMMM yyyy' : "'Week of' MMM d, yyyy")}
          </h2>

          {loading && (
            <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          )}
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
          <div className="flex items-center rounded-xl bg-slate-900 border border-slate-800 p-1">
            <button
              onClick={() => setView('month')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
                view === 'month'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Month
            </button>
            <button
              onClick={() => setView('week')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
                view === 'week'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Week
            </button>
          </div>

          <button
            onClick={() => handleOpenCreateModal(new Date())}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:scale-98 shadow-md shadow-indigo-600/25 transition"
          >
            <Plus className="w-4 h-4" />
            <span>New Event</span>
          </button>
        </div>
      </div>

      {/* Calendar Grid Container */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden backdrop-blur">
        <div className="grid grid-cols-7 border-b border-slate-800 bg-slate-950/60 text-center text-xs font-semibold text-slate-400 py-3">
          <span>Sun</span>
          <span>Mon</span>
          <span>Tue</span>
          <span>Wed</span>
          <span>Thu</span>
          <span>Fri</span>
          <span>Sat</span>
        </div>

        <div className="grid grid-cols-7 divide-x divide-y divide-slate-800/80">
          {daysInView.map((day) => {
            const dayEvents = events.filter((ev) => isSameDay(new Date(ev.start_time), day));
            const isCurrentMonth = isSameMonth(day, currentDate);
            const isCurrentDay = isToday(day);

            return (
              <div
                key={day.toISOString()}
                onClick={() => handleOpenCreateModal(day)}
                className={`min-h-[110px] sm:min-h-[130px] p-2 sm:p-2.5 transition group cursor-pointer hover:bg-slate-800/30 flex flex-col justify-between ${
                  !isCurrentMonth ? 'bg-slate-950/40 text-slate-600' : 'text-slate-300'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                      isCurrentDay
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
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
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition"
                    title="Add Event"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                </div>

                <div className="space-y-1 overflow-y-auto max-h-[80px] scrollbar-none flex-1">
                  {dayEvents.map((ev) => (
                    <div
                      key={ev.id}
                      onClick={(e) => handleOpenEditModal(ev, e)}
                      className="group/item text-[11px] p-1.5 rounded-lg bg-indigo-950/60 hover:bg-indigo-900 border border-indigo-800/50 hover:border-indigo-500/50 text-indigo-200 transition truncate flex items-center justify-between gap-1 shadow-sm"
                      title={`${ev.title} (${format(new Date(ev.start_time), 'h:mm a')})`}
                    >
                      <span className="truncate font-medium">{ev.title}</span>
                      <span className="text-[10px] font-mono text-indigo-400 shrink-0">
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
