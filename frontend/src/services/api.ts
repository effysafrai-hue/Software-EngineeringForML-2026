import {
  CalendarEvent,
  ChatMessage,
  ChatResponse,
  EventInput,
  TokenResponse,
  User,
  SharedCalendar,
  SharedMemory,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 204) {
    return {} as T;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorDetail =
      data.detail ||
      (Array.isArray(data) ? data[0]?.msg : null) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(response.status, errorDetail);
  }

  return data as T;
}

export const api = {
  // Auth
  signup: (payload: { email: string; password: string }) =>
    request<User>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  login: (payload: { email: string; password: string }) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getMe: (token: string) => request<User>('/auth/me', {}, token),

  // Personal Calendar Events
  listEvents: (token: string, startTime?: string, endTime?: string) => {
    const params = new URLSearchParams();
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return request<CalendarEvent[]>(`/events${queryString}`, {}, token);
  },

  createEvent: (token: string, event: EventInput) =>
    request<CalendarEvent>(
      '/events',
      {
        method: 'POST',
        body: JSON.stringify(event),
      },
      token
    ),

  updateEvent: (token: string, eventId: number, event: Partial<EventInput>) =>
    request<CalendarEvent>(
      `/events/${eventId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(event),
      },
      token
    ),

  deleteEvent: (token: string, eventId: number) =>
    request<void>(
      `/events/${eventId}`,
      {
        method: 'DELETE',
      },
      token
    ),

  // AI Chat (Personal)
  sendChat: (token: string, message: string) =>
    request<ChatResponse>(
      '/chat',
      {
        method: 'POST',
        body: JSON.stringify({ message }),
      },
      token
    ),

  getChatHistory: (token: string) =>
    request<ChatMessage[]>('/chat/history', {}, token),

  // Shared Calendars
  listSharedCalendars: (token: string) =>
    request<SharedCalendar[]>('/shared-calendars', {}, token),

  createSharedCalendar: (token: string, name: string) =>
    request<SharedCalendar>(
      '/shared-calendars',
      {
        method: 'POST',
        body: JSON.stringify({ name }),
      },
      token
    ),

  getSharedCalendarDetails: (token: string, calendarId: number) =>
    request<SharedCalendar>(`/shared-calendars/${calendarId}`, {}, token),

  addSharedCalendarMember: (token: string, calendarId: number, email: string, role = 'member') =>
    request<{ message: string }>(
      `/shared-calendars/${calendarId}/members`,
      {
        method: 'POST',
        body: JSON.stringify({ email, role }),
      },
      token
    ),

  listSharedCalendarEvents: (token: string, calendarId: number, startTime?: string, endTime?: string) => {
    const params = new URLSearchParams();
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return request<CalendarEvent[]>(`/shared-calendars/${calendarId}/events${queryString}`, {}, token);
  },

  createSharedCalendarEvent: (token: string, calendarId: number, event: EventInput) =>
    request<CalendarEvent>(
      `/shared-calendars/${calendarId}/events`,
      {
        method: 'POST',
        body: JSON.stringify(event),
      },
      token
    ),

  updateSharedCalendarEvent: (token: string, calendarId: number, eventId: number, event: Partial<EventInput>) =>
    request<CalendarEvent>(
      `/shared-calendars/${calendarId}/events/${eventId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(event),
      },
      token
    ),

  deleteSharedCalendarEvent: (token: string, calendarId: number, eventId: number) =>
    request<void>(
      `/shared-calendars/${calendarId}/events/${eventId}`,
      {
        method: 'DELETE',
      },
      token
    ),

  // Shared Chat & Memories
  sendSharedChat: (token: string, calendarId: number, message: string) =>
    request<ChatResponse>(
      `/shared-calendars/${calendarId}/chat`,
      {
        method: 'POST',
        body: JSON.stringify({ message }),
      },
      token
    ),

  getSharedChatHistory: (token: string, calendarId: number) =>
    request<ChatMessage[]>(`/shared-calendars/${calendarId}/chat/history`, {}, token),

  listSharedMemories: (token: string, calendarId: number) =>
    request<SharedMemory[]>(`/shared-calendars/${calendarId}/memories`, {}, token),

  createSharedMemory: (token: string, calendarId: number, content: string) =>
    request<SharedMemory>(
      `/shared-calendars/${calendarId}/memories`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
      },
      token
    ),
};
