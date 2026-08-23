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
  user_id: number;
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
