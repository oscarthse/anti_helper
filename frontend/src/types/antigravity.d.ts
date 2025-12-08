/**
 * Antigravity Type Definitions
 *
 * TypeScript interfaces that mirror the backend Pydantic models.
 * These ensure type safety throughout the frontend integration.
 */

// =============================================================================
// Task Types
// =============================================================================

export type TaskStatus =
  | 'pending'
  | 'planning'
  | 'plan_review'
  | 'executing'
  | 'testing'
  | 'documenting'
  | 'completed'
  | 'failed'
  | 'review_required'
  | 'paused';

export type AgentPersona =
  | 'planner'
  | 'coder_be'
  | 'coder_fe'
  | 'coder_infra'
  | 'qa'
  | 'docs'
  | 'system';

export interface TaskStep {
  order: number;
  step_id: string;
  description: string;
  agent_persona: AgentPersona;
  files_affected: string[];
  depends_on: string[];
}

export interface TaskPlan {
  summary: string;
  steps: TaskStep[];
  affected_files: string[];
  estimated_complexity: number;
  risks: string[];
}

export interface Task {
  id: string;
  repo_id: string;
  parent_task_id?: string | null;
  user_request: string;
  title?: string | null;
  status: TaskStatus;
  current_agent?: string | null;
  current_step: number;
  total_steps?: number;
  task_plan?: TaskPlan | null;
  error_message?: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

// =============================================================================
// Agent Log Types (SSE Payload)
// =============================================================================

export interface ToolCall {
  id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result?: string | null;
  success: boolean;
  error?: string | null;
  duration_ms?: number | null;
}

export interface AgentLog {
  id: string;
  task_id: string;
  agent_persona: AgentPersona;
  step_number: number;
  ui_title: string;
  ui_subtitle: string;
  technical_reasoning?: string;
  tool_calls?: ToolCall[];
  confidence_score: number;
  requires_review: boolean;
  created_at: string;
  duration_ms?: number | null;
}

// =============================================================================
// File Event Types (SSE Payload)
// =============================================================================

export type FileAction = 'create' | 'update' | 'delete';

export interface VerifiedFileEvent {
  event_type: 'file_verified';
  task_id: string;
  step_index: number;
  file_path: string;
  file_action: FileAction;
  byte_size: number;
  quality_checks: string[];
  quality_warnings: string[];
  timestamp: string;
}

// =============================================================================
// Repository Types
// =============================================================================

export interface Repository {
  id: string;
  name: string;
  path: string;
  description?: string | null;
  project_type?: string | null;
  framework?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileNode[];
}
