import React, { useState, useEffect } from 'react';
import { CalendarEvent, EventInput } from '../types';
import { X, Trash2, Calendar, Clock, AlertCircle } from 'lucide-react';

interface EventModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (event: EventInput, eventId?: number) => Promise<void>;
  onDelete?: (eventId: number) => Promise<void>;
  initialEvent?: CalendarEvent | null;
  defaultDate?: Date;
}

function toLocalDatetimeString(dateInput: Date | string): string {
  const d = typeof dateInput === 'string' ? new Date(dateInput) : dateInput;
  const pad = (n: number) => n.toString().padStart(2, '0');
  const year = d.getFullYear();
  const month = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  const hours = pad(d.getHours());
  const minutes = pad(d.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export const EventModal: React.FC<EventModalProps> = ({
  isOpen,
  onClose,
  onSave,
  onDelete,
  initialEvent,
  defaultDate,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (initialEvent) {
      setTitle(initialEvent.title);
      setDescription(initialEvent.description || '');
      setStartTime(toLocalDatetimeString(initialEvent.start_time));
      setEndTime(toLocalDatetimeString(initialEvent.end_time));
    } else {
      const baseDate = defaultDate || new Date();
      const start = new Date(baseDate);
      start.setMinutes(0, 0, 0);
      const end = new Date(start);
      end.setHours(start.getHours() + 1);

      setTitle('');
      setDescription('');
      setStartTime(toLocalDatetimeString(start));
      setEndTime(toLocalDatetimeString(end));
    }
    setError(null);
  }, [initialEvent, defaultDate, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const start = new Date(startTime);
    const end = new Date(endTime);

    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      setError('Please provide valid start and end dates.');
      return;
    }

    if (end <= start) {
      setError('End time must be strictly after start time.');
      return;
    }

    setIsSaving(true);
    try {
      await onSave(
        {
          title,
          description: description.trim() || null,
          start_time: start.toISOString(),
          end_time: end.toISOString(),
        },
        initialEvent?.id
      );
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save event.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!initialEvent || !onDelete) return;
    if (!window.confirm('Are you sure you want to delete this event?')) return;

    setIsDeleting(true);
    try {
      await onDelete(initialEvent.id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to delete event.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Calendar className="w-4 h-4" />
            </div>
            <h3 className="font-semibold text-white text-base">
              {initialEvent ? 'Edit Event' : 'Create New Event'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start gap-2.5 text-xs text-rose-400">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Title</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Meeting / Task Title"
              className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Description (optional)
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add details or notes..."
              className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition resize-none"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-indigo-400" />
                Start Time
              </label>
              <input
                type="datetime-local"
                required
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-purple-400" />
                End Time
              </label>
              <input
                type="datetime-local"
                required
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 flex items-center justify-between gap-3">
            {initialEvent && onDelete ? (
              <button
                type="button"
                onClick={handleDelete}
                disabled={isDeleting || isSaving}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-rose-400 hover:text-white bg-rose-500/10 hover:bg-rose-600 border border-rose-500/20 transition disabled:opacity-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{isDeleting ? 'Deleting...' : 'Delete'}</span>
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isSaving || isDeleting}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving || isDeleting}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:scale-98 disabled:opacity-50 transition shadow-md shadow-indigo-600/25"
              >
                {isSaving ? 'Saving...' : initialEvent ? 'Save Changes' : 'Create Event'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
