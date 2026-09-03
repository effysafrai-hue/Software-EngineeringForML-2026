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
  memory_actions?: MemoryAction[];
}

/** What the assistant decided to keep or drop from long-term memory this turn. */
export interface MemoryAction {
  action: 'remembered' | 'forgotten';
  id: number;
  category: string;
  content: string;
}

export interface UserMemory {
  id: number;
  user_id: number;
  category: string;
  content: string;
  source: 'signup' | 'ai' | 'user';
  active: boolean;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryContext {
  context: string;
  active_count: number;
  by_category: Record<string, number>;
}

export interface SignupQuestion {
  key: string;
  question: string;
  type: 'choice' | 'multi_choice' | 'tags' | 'text';
  category: string;
  options?: { value: string; label: string }[];
  placeholder?: string | null;
}

/**
 * Answers to the sign-up questions. Every field is optional by design — the
 * questionnaire is a head start for the AI, not a requirement for an account.
 *
 * A type alias rather than an interface so the form can index it by question key
 * (`answers[q.key]`) while rendering the server-supplied question list.
 */
export type SignupPreferences = {
  task_order?: string;
  communication_style?: string;
  study_times?: string[];
  interests?: string[];
  goals?: string;
  daily_routine?: string;
};

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
