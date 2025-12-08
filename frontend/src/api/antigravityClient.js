/**
 * Antigravity API Client
 *
 * Custom fetch wrapper for communicating with the FastAPI backend.
 * Replaces the proprietary @base44/sdk.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Core API request function with error handling.
 */
async function apiRequest(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  // Handle non-JSON responses (e.g., 204 No Content)
  if (response.status === 204) {
    return null;
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `API Error: ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Task Endpoints
// =============================================================================

/**
 * Fetch a single task by ID.
 */
export const fetchTask = (taskId) => apiRequest(`/api/tasks/${taskId}`);

/**
 * Fetch all tasks (for Dashboard).
 */
export const fetchTasks = (repoId) => {
  const params = repoId ? `?repo_id=${repoId}` : '';
  return apiRequest(`/api/tasks/${params}`);
};

/**
 * DELETE a task (cascaded deletion).
 */
export const deleteTask = (taskId) =>
  apiRequest(`/api/tasks/${taskId}`, { method: 'DELETE' });

/**
 * PAUSE a task (Zero-Latency Halt).
 */
export const pauseTask = (taskId) =>
  apiRequest(`/api/tasks/${taskId}/pause`, { method: 'POST' });

/**
 * RESUME a paused task.
 */
export const resumeTask = (taskId) =>
  apiRequest(`/api/tasks/${taskId}/resume`, { method: 'POST' });

/**
 * APPROVE a task plan.
 */
export const approveTask = (taskId) =>
  apiRequest(`/api/tasks/${taskId}/approve`, { method: 'POST' });

/**
 * CREATE a new task.
 */
export const createTask = (repoId, userRequest) =>
  apiRequest('/api/tasks/', {
    method: 'POST',
    body: JSON.stringify({ repo_id: repoId, user_request: userRequest }),
  });

// =============================================================================
// Repository Endpoints
// =============================================================================

/**
 * Fetch all repositories.
 */
export const fetchRepositories = () => apiRequest('/api/repos/');

/**
 * Fetch file tree for a repository.
 */
export const fetchFileTree = (repoId) =>
  apiRequest(`/api/files/tree?repo_id=${repoId}`);
