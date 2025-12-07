/**
 * API Client
 *
 * Handles communication with the Antigravity Dev backend API.
 * Includes streaming support for real-time agent updates.
 */

import type { Task, Repository, AgentLog } from '@/types/schema'

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
export async function fetchTasks(repoId?: string): Promise<Task[]> {
  const url = new URL(`${API_BASE_URL}/api/tasks/`)
  if (repoId) {
    url.searchParams.set('repo_id', repoId)
  }

  const response = await fetch(url.toString())

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
  const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}`)

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
 * Fetch repositories
 */
export async function fetchRepositories(): Promise<Repository[]> {
  const response = await fetch(`${API_BASE_URL}/api/repos/`)

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
