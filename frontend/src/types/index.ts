export interface User {
  id: number;
  email: string;
  created_at: string;
  preferences?: Record<string, any> | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface CalendarEvent {
  id: number;
  user_id?: number | null;
  shared_calendar_id?: number | null;
  title: string;
  description?: string | null;
  start_time: string;
  end_time: string;
  created_at: string;
  updated_at: string;
}

export interface EventInput {
  title: string;
  description?: string | null;
  start_time: string;
  end_time: string;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface ChatResponse {
  reply: string;
  action_taken?: string | null;
}

export interface SharedCalendarMember {
  id: number;
  user_id: number;
  email?: string | null;
  role: string;
  joined_at: string;
}

export interface SharedCalendar {
  id: number;
  name: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  members?: SharedCalendarMember[];
}

export interface SharedMemory {
  id: number;
  shared_calendar_id: number;
  content: string;
  created_by?: number | null;
  created_at: string;
}
