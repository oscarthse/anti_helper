/**
 * Mission Control - Home Page
 *
 * The command center for Antigravity Dev.
 * Displays repositories, active tasks, and command input.
 */

import { fetchRepositories, fetchTasks } from '@/lib/api'
import { RepoCard } from '@/components/RepoCard'
import { TaskRow } from '@/components/TaskRow'
import { CommandInput } from '@/components/CommandInput'
import { FolderGit2, ListTodo, AlertCircle } from 'lucide-react'
import type { Repository, Task } from '@/types/schema'

export const dynamic = 'force-dynamic'

// Mock data for development (remove when backend is running)
const mockRepos: Repository[] = [
  {
    id: '1',
    name: 'antigravity-dev',
    path: '/Users/dev/antigravity',
    project_type: 'Python',
    framework: 'FastAPI',
    description: 'Main platform repository',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
]

const mockTasks: Task[] = [
  {
    id: '1',
    repo_id: '1',
    user_request: 'Add user authentication with OAuth2',
    status: 'executing',
    current_agent: 'coder_be',
    current_step: 2,
    retry_count: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: '2',
    repo_id: '1',
    user_request: 'Fix the database connection pooling issue',
    status: 'completed',
    current_agent: null,
    current_step: 3,
    retry_count: 0,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
    completed_at: new Date(Date.now() - 86400000).toISOString(),
  },
]

export default async function MissionControlPage() {
  let repos: Repository[] = mockRepos
  let tasks: Task[] = mockTasks
  let error: string | null = null

  // Try to fetch real data
  try {
    const [repoData, taskData] = await Promise.all([
      fetchRepositories().catch(() => null),
      fetchTasks().catch(() => null),
    ])
    if (repoData) repos = repoData
    if (taskData) tasks = taskData
  } catch {
    error = 'Backend not available. Showing mock data.'
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] overflow-auto p-6">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">
          Mission Control
        </h1>
        <p className="text-slate-400">
          Command center for your AI development agents
        </p>
      </div>

      {/* Connection Warning */}
      {error && (
        <div className="mb-6 flex items-center gap-2 px-4 py-3 rounded-lg bg-amber-950/30 border border-amber-900/50 text-amber-400 text-sm">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Command Input - Prominent Position */}
      <section className="mb-10">
        <CommandInput repos={repos} />
      </section>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Repository Intel */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <FolderGit2 className="h-5 w-5 text-slate-500" />
            <h2 className="text-sm font-medium text-slate-300 uppercase tracking-wider">
              Repository Intel
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-3">
            {repos.length > 0 ? (
              repos.map((repo) => (
                <RepoCard key={repo.id} repo={repo} />
              ))
            ) : (
              <div className="p-6 rounded-lg border border-dashed border-slate-800 text-center">
                <p className="text-slate-500">No repositories registered</p>
                <p className="text-xs text-slate-600 mt-1">
                  Use the CLI to register a repository
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Active Missions */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <ListTodo className="h-5 w-5 text-slate-500" />
            <h2 className="text-sm font-medium text-slate-300 uppercase tracking-wider">
              Active Missions
            </h2>
          </div>
          <div className="space-y-2">
            {tasks.length > 0 ? (
              tasks.map((task) => (
                <TaskRow key={task.id} task={task} />
              ))
            ) : (
              <div className="p-6 rounded-lg border border-dashed border-slate-800 text-center">
                <p className="text-slate-500">No active missions</p>
                <p className="text-xs text-slate-600 mt-1">
                  Create a new task to get started
                </p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
