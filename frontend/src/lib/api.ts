/**
 * API Client
 *
 * Handles communication with the Antigravity Dev backend API.
 * Includes streaming support for real-time agent updates.
 */

import type { Task, Repository, AgentLog, VerifiedFileEvent } from '@/types/schema'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// =============================================================================
// Error Types
// =============================================================================

export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message)
    this.name = 'APIError'
  }
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Fetch a list of tasks
 */
export async function fetchTasks(repoId?: string, parentTaskId?: string): Promise<Task[]> {
  const url = new URL(`${API_BASE_URL}/api/tasks/`)
  if (repoId) {
    url.searchParams.set('repo_id', repoId)
  }
  if (parentTaskId) {
    url.searchParams.set('parent_task_id', parentTaskId)
  }

  const response = await fetch(url.toString(), { cache: 'no-store' })

  if (!response.ok) {
    throw new APIError(
      'Failed to fetch tasks',
      response.status,
    )
  }

  return response.json()
}

/**
 * Fetch a single task by ID
 */
export async function fetchTask(taskId: string): Promise<Task> {
  const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}`, { cache: 'no-store' })

  if (!response.ok) {
    throw new APIError(
      `Task ${taskId} not found`,
      response.status,
    )
  }

  return response.json()
}

/**
 * Create a new task
 */
export async function createTask(repoId: string, userRequest: string): Promise<Task> {
  const response = await fetch(`${API_BASE_URL}/api/tasks/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      repo_id: repoId,
      user_request: userRequest,
    }),
    cache: 'no-store',
  })

  if (!response.ok) {
    const error = await response.json()
    throw new APIError(
      error.detail || 'Failed to create task',
      response.status,
    )
  }

  return response.json()
}

/**
 * Fetch file tree for a repository
 */
export async function fetchFileTree(repoId: string): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/api/files/tree?repo_id=${repoId}`, { cache: 'no-store' })

  if (!response.ok) {
    throw new APIError(
      'Failed to fetch file tree',
      response.status,
    )
  }

  return response.json()
}

/**
 * Approve a task plan and continue execution
 */
export async function approveTaskPlan(taskId: string): Promise<void> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/approve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    })
  } catch (error) {
    // Network-level error - API might be down or CORS issue
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new APIError(
        `Cannot connect to API server at ${API_BASE_URL}. Is the backend running?`,
        0,
        'NETWORK_ERROR'
      )
    }
    throw error
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new APIError(
      error.detail || 'Failed to approve task plan',
      response.status,
    )
  }
}

/**
 * Reject a task plan with feedback
 */
export async function rejectTaskPlan(taskId: string, feedback: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/reject`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ feedback }),
    cache: 'no-store',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new APIError(
      error.detail || 'Failed to reject task plan',
      response.status,
    )
  }
}

/**
 * Pause task execution
 */
export async function pauseTask(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/pause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store'
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new APIError(error.detail || 'Failed to pause task', response.status)
  }
}

/**
 * Resume task execution
 */
export async function resumeTask(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store'
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new APIError(error.detail || 'Failed to resume task', response.status)
  }
}

/**
 * Delete a mission
 */
export async function deleteTask(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}`, {
    method: 'DELETE',
    cache: 'no-store'
  })

  if (!response.ok) {
    // 204 No Content is OK
    throw new APIError('Failed to delete task', response.status)
  }
}

/**
 * Fetch repositories
 */
export async function fetchRepositories(): Promise<Repository[]> {
  const response = await fetch(`${API_BASE_URL}/api/repos/`, { cache: 'no-store' })

  if (!response.ok) {
    throw new APIError(
      'Failed to fetch repositories',
      response.status,
    )
  }

  return response.json()
}

// =============================================================================
// Streaming API
// =============================================================================

interface StreamCallbacks {
  onLog: (log: AgentLog) => void
  onFileVerified?: (event: VerifiedFileEvent) => void  // Verified file events
  onError: (error: Error) => void
  onComplete: () => void
}

/**
 * Subscribe to task updates via Server-Sent Events
 */
export async function subscribeToTaskStream(
  taskId: string,
  callbacks: StreamCallbacks,
): Promise<() => void> {
  const url = `${API_BASE_URL}/api/stream/task/${taskId}`

  const eventSource = new EventSource(url)

  eventSource.onopen = () => {
    // Connected successfully
  }

  eventSource.addEventListener('agent_log', (event) => {
    try {
      const log = JSON.parse(event.data) as AgentLog
      callbacks.onLog(log)
    } catch (error) {
      callbacks.onError(new Error('Failed to parse log data'))
    }
  })

  eventSource.addEventListener('complete', () => {
    callbacks.onComplete()
    eventSource.close()
  })

  // Handle verified file events (from backend VerifiedFileAction)
  eventSource.addEventListener('file_verified', (event) => {
    try {
      const fileEvent = JSON.parse(event.data) as VerifiedFileEvent
      callbacks.onFileVerified?.(fileEvent)
    } catch (error) {
      console.error('Failed to parse file_verified event:', error)
    }
  })

  eventSource.addEventListener('error', () => {
    callbacks.onError(new APIError('API Connection Failed', 500))
    eventSource.close()
  })

  eventSource.onerror = () => {
    callbacks.onError(new APIError('API Connection Failed', 500))
    eventSource.close()
  }

  // Return cleanup function
  return () => eventSource.close()
}
