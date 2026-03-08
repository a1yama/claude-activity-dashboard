export interface DatasetteResponse {
  ok: boolean;
  rows: unknown[][];
  columns: string[];
}

export interface DailyActivity {
  date: string;
  sessions: number;
  user_messages: number;
  assistant_messages: number;
  tool_uses: number;
}

export interface ProjectSummary {
  project_name: string;
  total_sessions: number;
  total_user_messages: number;
  total_tool_uses: number;
  first_used: string;
  last_used: string;
}

export interface HourlyDistribution {
  hour: number;
  message_count: number;
  user_messages: number;
}

export interface ToolUsage {
  tool_name: string;
  usage_count: number;
}

export interface SessionDetail {
  session_id: string;
  project_name: string;
  first_message_at: string;
  last_message_at: string;
  message_count: number;
  user_message_count: number;
  assistant_message_count: number;
  tool_use_count: number;
  claude_version: string | null;
}

export interface SessionMessage {
  uuid: string;
  type: string;
  subtype: string | null;
  timestamp_jst: string;
  content_preview: string | null;
  tool_count: number;
  tool_names: string;
  tool_details: string;
  is_meta: number;
}

export interface ToolDetail {
  name: string;
  input: string;
}

export interface RecentSession {
  session_id: string;
  project_name: string;
  started: string;
  ended: string;
  message_count: number;
  user_message_count: number;
  tool_use_count: number;
  claude_version: string | null;
}
