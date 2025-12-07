/**
 * Mock Data Utilities
 *
 * Generates consistent mock data objects based on the schema.ts interfaces.
 * Used across all frontend tests for data integrity validation.
 */

import type {
  AgentOutput,
  AgentPersona,
  TaskStatus,
  Task,
  Repository,
  AgentLog,
  ToolCall,
  TaskPlan,
  TaskStep,
  ChangeSet,
  ExecutionRun,
} from '@/types/schema'

// =============================================================================
// Mock Data Factories
// =============================================================================

/**
 * Create a valid mock ToolCall
 */
export function createMockToolCall(overrides: Partial<ToolCall> = {}): ToolCall {
  return {
    tool_name: 'scan_repo_structure',
    arguments: { path: '/app' },
    result: '{"files": 10}',
    success: true,
    duration_ms: 150,
    ...overrides,
  }
}

/**
 * Create a valid mock AgentOutput
 */
export function createMockAgentOutput(overrides: Partial<AgentOutput> = {}): AgentOutput {
  return {
    ui_title: '📋 Analyzing Repository',
    ui_subtitle: "I'm scanning your codebase to understand the project structure.",
    technical_reasoning: 'Performing initial reconnaissance of repo structure.',
    tool_calls: [createMockToolCall()],
    confidence_score: 0.85,
    agent_persona: 'planner' as AgentPersona,
    timestamp: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Create a valid mock TaskStep
 */
export function createMockTaskStep(overrides: Partial<TaskStep> = {}): TaskStep {
  return {
    order: 1,
    description: 'Analyze existing codebase',
    agent_persona: 'planner' as AgentPersona,
    dependencies: [],
    files_affected: ['src/main.py'],
    ...overrides,
  }
}

/**
 * Create a valid mock TaskPlan
 */
export function createMockTaskPlan(overrides: Partial<TaskPlan> = {}): TaskPlan {
  return {
    summary: 'Add input validation to user registration endpoint',
    steps: [
      createMockTaskStep({ order: 1, description: 'Analyze endpoint' }),
      createMockTaskStep({ order: 2, description: 'Add validation', agent_persona: 'coder_be' as AgentPersona }),
      createMockTaskStep({ order: 3, description: 'Run tests', agent_persona: 'qa' as AgentPersona }),
    ],
    estimated_complexity: 4,
    affected_files: ['src/api/users.py', 'src/schemas/user.py'],
    risks: ['May affect existing integrations'],
    ...overrides,
  }
}

/**
 * Create a valid mock ChangeSet
 */
export function createMockChangeSet(overrides: Partial<ChangeSet> = {}): ChangeSet {
  return {
    file_path: 'src/api/users.py',
    action: 'modify',
    diff: '@@ -10,3 +10,5 @@\n+from pydantic import validator',
    explanation: 'Added Pydantic validator import for schema validation.',
    language: 'python',
    ...overrides,
  }
}

/**
 * Create a valid mock ExecutionRun
 */
export function createMockExecutionRun(overrides: Partial<ExecutionRun> = {}): ExecutionRun {
  return {
    command: 'pytest tests/',
    working_directory: '/app',
    stdout: '15 passed, 0 failed',
    stderr: '',
    exit_code: 0,
    duration_ms: 5230,
    ...overrides,
  }
}

/**
 * Create a valid mock Repository
 */
export function createMockRepository(overrides: Partial<Repository> = {}): Repository {
  return {
    id: 'repo-123-uuid',
    name: 'test-repo',
    path: '/app/test-repo',
    description: 'A test repository for validation',
    project_type: 'python',
    framework: 'fastapi',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Create a valid mock Task
 */
export function createMockTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-456-uuid',
    repo_id: 'repo-123-uuid',
    user_request: 'Add input validation to the user registration endpoint',
    title: 'Add Validation',
    status: 'pending' as TaskStatus,
    current_agent: null,
    current_step: 0,
    task_plan: null,
    error_message: null,
    retry_count: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    completed_at: null,
    ...overrides,
  }
}

/**
 * Create a valid mock AgentLog
 */
export function createMockAgentLog(overrides: Partial<AgentLog> = {}): AgentLog {
  return {
    id: 'log-789-uuid',
    task_id: 'task-456-uuid',
    agent_persona: 'planner',
    step_number: 1,
    ui_title: '📋 Creating Plan',
    ui_subtitle: "I've analyzed your request and created a plan.",
    technical_reasoning: 'Parsed user intent and decomposed into steps.',
    tool_calls: [{ tool_name: 'scan_repo_structure', success: true }],
    confidence_score: 0.9,
    requires_review: false,
    reviewed_at: null,
    reviewed_by: null,
    created_at: new Date().toISOString(),
    duration_ms: 1500,
    ...overrides,
  }
}

// =============================================================================
// Specialized Mock Scenarios
// =============================================================================

/**
 * Create a task in REVIEW_REQUIRED state
 */
export function createReviewRequiredTask(): Task {
  return createMockTask({
    status: 'review_required' as TaskStatus,
    current_agent: 'coder_be',
    current_step: 2,
  })
}

/**
 * Create a task in EXECUTING state
 */
export function createExecutingTask(): Task {
  return createMockTask({
    status: 'executing' as TaskStatus,
    current_agent: 'coder_be',
    current_step: 1,
  })
}

/**
 * Create a failed task
 */
export function createFailedTask(): Task {
  return createMockTask({
    status: 'failed' as TaskStatus,
    error_message: 'Test execution failed: ImportError',
    retry_count: 2,
  })
}

/**
 * Create a low-confidence agent output (requires review)
 */
export function createLowConfidenceOutput(): AgentOutput {
  return createMockAgentOutput({
    ui_title: '⚠️ Uncertain Changes',
    ui_subtitle: 'I made changes but I am not fully confident in this approach.',
    confidence_score: 0.5,
  })
}

// =============================================================================
// Raw JSON Mocks (for schema validation tests)
// =============================================================================

/**
 * Valid raw JSON that should satisfy AgentOutput interface
 */
export const validAgentOutputJSON = {
  ui_title: 'Test Action',
  ui_subtitle: 'Test subtitle',
  technical_reasoning: 'Test reasoning',
  tool_calls: [],
  confidence_score: 0.9,
  agent_persona: 'planner',
}

/**
 * Valid raw JSON that should satisfy Task interface
 */
export const validTaskJSON = {
  id: 'task-id',
  repo_id: 'repo-id',
  user_request: 'Test request',
  title: 'Test',
  status: 'pending',
  current_agent: null,
  current_step: 0,
  task_plan: null,
  error_message: null,
  retry_count: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  completed_at: null,
}
