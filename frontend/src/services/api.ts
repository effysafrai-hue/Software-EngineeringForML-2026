import {
  CalendarEvent,
  ChatMessage,
  ChatResponse,
  EventInput,
  TokenResponse,
  User,
  SharedCalendar,
  SharedMemory,
  AppNotification,
  Post,
  Comment,
  PostDetail,
  FileUploadResponse,
  UserMemory,
  MemoryContext,
  SignupQuestion,
  SignupPreferences,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * The reader's IANA zone, e.g. "Asia/Jerusalem".
 *
 * Event times cross the wire as UTC instants and are rendered locally, which
 * needs no help. The AI is the exception: it has to be told which wall clock
 * "6pm" refers to, or it writes 18:00 UTC and the calendar shows 21:00.
 * Undefined on an ancient browser, in which case the server falls back to the
 * zone this user last reported.
 */
function browserTimezone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
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
  signup: (payload: { email: string; password: string; preferences?: SignupPreferences }) =>
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
  // The browser's IANA zone goes with every message: "6pm" means 6pm here, and
  // the server needs to know which wall clock that is before it writes an event.
  sendChat: (token: string, message: string) =>
    request<ChatResponse>(
      '/chat',
      {
        method: 'POST',
        body: JSON.stringify({ message, timezone: browserTimezone() }),
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
        body: JSON.stringify({ message, timezone: browserTimezone() }),
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

  // Long-Term Memory (per user)
  // The questionnaire is fetched rather than hard-coded so the form and the
  // sentences the AI reads cannot drift apart; it needs no token, since the
  // sign-up page renders it before an account exists.
  getSignupQuestions: () => request<SignupQuestion[]>('/memory/questions'),

  listMemories: (token: string, includeInactive = false) =>
    request<UserMemory[]>(`/memory${includeInactive ? '?include_inactive=true' : ''}`, {}, token),

  getMemoryContext: (token: string) => request<MemoryContext>('/memory/context', {}, token),

  createMemory: (
    token: string,
    payload: { content: string; category?: string; expires_in_days?: number }
  ) =>
    request<UserMemory>(
      '/memory',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      token
    ),

  updateMemory: (
    token: string,
    memoryId: number,
    payload: { content?: string; category?: string; active?: boolean }
  ) =>
    request<UserMemory>(
      `/memory/${memoryId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(payload),
      },
      token
    ),

  deleteMemory: (token: string, memoryId: number) =>
    request<void>(`/memory/${memoryId}`, { method: 'DELETE' }, token),

  getMemoryPreferences: (token: string) =>
    request<{ preferences: SignupPreferences; seeded_memories: UserMemory[] }>(
      '/memory/preferences',
      {},
      token
    ),

  updateMemoryPreferences: (token: string, preferences: SignupPreferences) =>
    request<{ preferences: SignupPreferences; seeded_memories: UserMemory[] }>(
      '/memory/preferences',
      {
        method: 'PUT',
        body: JSON.stringify(preferences),
      },
      token
    ),

  // Notifications
  listNotifications: (token: string, unreadOnly = false) => {
    const params = unreadOnly ? '?unread_only=true' : '';
    return request<AppNotification[]>(`/notifications${params}`, {}, token);
  },

  markNotificationRead: (token: string, notifId: number) =>
    request<{ message: string }>(
      `/notifications/${notifId}/read`,
      { method: 'PATCH' },
      token
    ),

  markAllNotificationsRead: (token: string) =>
    request<{ message: string }>(
      '/notifications/read-all',
      { method: 'PATCH' },
      token
    ),

  // Forum & Media Uploads
  uploadMedia: async (token: string, file: File): Promise<FileUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE_URL}/uploads`, {
      method: 'POST',
      headers,
      body: formData,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new ApiError(res.status, errData.detail || 'Upload failed');
    }
    return res.json();
  },

  getPosts: (token: string, search?: string) => {
    const params = search ? `?search=${encodeURIComponent(search)}` : '';
    return request<Post[]>(`/posts${params}`, {}, token);
  },

  createPost: (
    token: string,
    data: { title: string; body: string; media_urls: string[]; anonymous: boolean }
  ) =>
    request<Post>(
      '/posts',
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
      token
    ),

  getPostDetail: (token: string, postId: number) =>
    request<PostDetail>(`/posts/${postId}`, {}, token),

  deletePost: (token: string, postId: number) =>
    request<void>(
      `/posts/${postId}`,
      { method: 'DELETE' },
      token
    ),

  addComment: (
    token: string,
    postId: number,
    data: { body: string; media_urls: string[]; anonymous: boolean }
  ) =>
    request<Comment>(
      `/posts/${postId}/comments`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
      token
    ),

  deleteComment: (token: string, commentId: number) =>
    request<void>(
      `/comments/${commentId}`,
      { method: 'DELETE' },
      token
    ),
};
