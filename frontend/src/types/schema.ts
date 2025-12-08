export type AgentPersona =
  | "planner"
  | "coder_be"
  | "coder_fe"
  | "coder_infra"
  | "qa"
  | "docs";

export type TaskStatus =
  | "pending"
  | "planning"
  | "plan_review"
  | "executing"
  | "testing"
  | "documenting"
  | "completed"
  | "failed"
  | "paused"
  | "review_required";

export interface ToolCall {
  id: string;
  tool_name: string;
  arguments: Record<string, any>;
  result?: string | null;
  success: boolean;
  error?: string | null;
  duration_ms?: number | null;
}

export interface AgentLog {
  id: string;
  agent_persona: AgentPersona;
  step_number: number;
  ui_title: string;
  ui_subtitle: string;
  technical_reasoning?: string; // Markdown supported
  tool_calls?: ToolCall[];
  confidence_score: number;
  requires_review: boolean;
  created_at: string; // ISO Date
  duration_ms?: number | null;
}

export interface TaskStep {
  order: number;
  description: string;
  agent_persona: AgentPersona;
  estimated_tokens?: number | null;
  dependencies: number[];
  files_affected: string[];
}

export interface TaskPlan {
  task_id: string;
  summary: string;
  steps: TaskStep[];
  estimated_complexity: number;
  affected_files: string[];
  risks: string[];
}

export interface Task {
  id: string;
  repo_id: string;
  user_request: string;
  title?: string | null;
  status: TaskStatus;
  current_agent?: string | null;
  current_step: number;
  task_plan?: TaskPlan | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  agent_logs?: AgentLog[]; // Joined in detail view
}

export interface ChangeSet {
  file_path: string;
  action: "create" | "modify" | "delete";
  diff: string;
  explanation: string;
  language?: string | null;
}
