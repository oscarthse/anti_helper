/**
 * War Room - Task Detail Page
 *
 * The 3-column cockpit view for watching tasks execute.
 * Server component entry point that fetches initial data.
 */

import { fetchTask } from '@/lib/api'
import { WarRoom } from '@/components/WarRoom'
import { AlertCircle } from 'lucide-react'

interface WarRoomPageProps {
  params: Promise<{ id: string }>
}

// Mock task for development
const mockTask = {
  id: 'mock-1',
  repo_id: '1',
  user_request: 'Add user authentication with OAuth2 and JWT tokens',
  title: 'OAuth2 Authentication',
  status: 'executing' as const,
  current_agent: 'coder_be',
  current_step: 2,
  task_plan: {
    summary: 'Implement OAuth2 authentication flow',
    steps: [
      { order: 1, description: 'Create auth models', agent_persona: 'coder_be' },
      { order: 2, description: 'Implement OAuth2 endpoints', agent_persona: 'coder_be' },
      { order: 3, description: 'Add JWT token handling', agent_persona: 'coder_be' },
      { order: 4, description: 'Run tests', agent_persona: 'qa' },
      { order: 5, description: 'Update documentation', agent_persona: 'docs' },
    ],
  },
  retry_count: 0,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

export default async function WarRoomPage({ params }: WarRoomPageProps) {
  const { id } = await params
  let task = mockTask
  let error: string | null = null

  // Try to fetch real task
  try {
    const realTask = await fetchTask(id).catch(() => null)
    if (realTask) {
      task = realTask as typeof mockTask
    } else {
      error = 'Task not found. Showing demo view.'
    }
  } catch (e) {
    error = 'Backend not available. Showing demo view.'
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Task Header */}
      <header className="flex-shrink-0 px-6 py-4 border-b border-slate-800 bg-slate-950/80">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold text-slate-100 truncate">
              {task.user_request}
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Task ID: <span className="font-mono">{task.id.substring(0, 8)}...</span>
            </p>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-3">
            {error && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-950/50 border border-amber-900/50 text-amber-400 text-xs">
                <AlertCircle className="h-3.5 w-3.5" />
                Demo Mode
              </div>
            )}
            <StatusBadge status={task.status} />
          </div>
        </div>
      </header>

      {/* War Room Content */}
      <WarRoom task={task} />
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string }> = {
    pending: { label: 'PENDING', className: 'bg-slate-800 text-slate-300 border-slate-700' },
    planning: { label: 'PLANNING', className: 'bg-blue-950 text-blue-400 border-blue-800' },
    plan_review: { label: 'REVIEW', className: 'bg-amber-950 text-amber-400 border-amber-800' },
    executing: { label: 'EXECUTING', className: 'bg-amber-950 text-amber-400 border-amber-800' },
    testing: { label: 'TESTING', className: 'bg-purple-950 text-purple-400 border-purple-800' },
    documenting: { label: 'DOCS', className: 'bg-cyan-950 text-cyan-400 border-cyan-800' },
    completed: { label: 'COMPLETE', className: 'bg-emerald-950 text-emerald-400 border-emerald-800' },
    failed: { label: 'FAILED', className: 'bg-red-950 text-red-400 border-red-800' },
  }

  const { label, className } = config[status] || config.pending

  return (
    <div className={`px-3 py-1.5 rounded-lg text-xs font-mono border ${className}`}>
      {label}
    </div>
  )
}
