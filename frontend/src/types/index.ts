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

export interface AppNotification {
  id: number;
  user_id: number;
  event_id?: number | null;
  message: string;
  read: boolean;
  created_at: string;
  event_title?: string | null;
}

export interface Post {
  id: number;
  title: string;
  body: string;
  media_urls: string[];
  anonymous: boolean;
  created_at: string;
  author_id?: number | null;
  author_email?: string | null;
  comment_count: number;
}

export interface Comment {
  id: number;
  post_id: number;
  body: string;
  media_urls: string[];
  anonymous: boolean;
  created_at: string;
  author_id?: number | null;
  author_email?: string | null;
}

export interface PostDetail extends Post {
  comments: Comment[];
}

export interface FileUploadResponse {
  url: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  category: string;
}
