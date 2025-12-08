/**
 * TaskRow Component
 *
 * Displays a task in a row format with status badge.
 * Clicking navigates to the War Room.
 */

'use client'

import Link from 'next/link'
import { Clock, AlertCircle, CheckCircle2, Loader2, PlayCircle } from 'lucide-react'
import type { Task, TaskStatus } from '@/types/schema'
import { cn } from '@/lib/utils'

interface TaskRowProps {
  task: Task
  className?: string
}

const statusConfig: Record<TaskStatus, {
  label: string
  icon: React.ComponentType<{ className?: string }>
  className: string
  description: string
}> = {
  pending: {
    label: 'PENDING',
    icon: Clock,
    className: 'bg-slate-800 text-slate-300 border-slate-700',
    description: 'Waiting in queue'
  },
  planning: {
    label: 'PLANNING',
    icon: Loader2,
    className: 'bg-blue-950 text-blue-400 border-blue-800',
    description: 'Planner Agent analyzing request'
  },
  plan_review: {
    label: 'REVIEW',
    icon: AlertCircle,
    className: 'bg-amber-950 text-amber-400 border-amber-800',
    description: 'Awaiting human review'
  },
  executing: {
    label: 'EXECUTING',
    icon: PlayCircle,
    className: 'bg-amber-950 text-amber-400 border-amber-800 animate-pulse',
    description: 'Coder Agent writing code'
  },
  testing: {
    label: 'TESTING',
    icon: Loader2,
    className: 'bg-purple-950 text-purple-400 border-purple-800',
    description: 'QA Agent running tests'
  },
  documenting: {
    label: 'DOCS',
    icon: Loader2,
    className: 'bg-cyan-950 text-cyan-400 border-cyan-800',
    description: 'Docs Agent updating documentation'
  },
  completed: {
    label: 'COMPLETE',
    icon: CheckCircle2,
    className: 'bg-emerald-950 text-emerald-400 border-emerald-800',
    description: 'Task finished successfully'
  },
  failed: {
    label: 'FAILED',
    icon: AlertCircle,
    className: 'bg-red-950 text-red-400 border-red-800',
    description: 'Task encountered an error'
  },
  review_required: {
    label: 'REVIEW',
    icon: AlertCircle,
    className: 'bg-amber-950 text-amber-400 border-amber-800',
    description: 'Code review needed'
  },
}

export function TaskRow({ task, className }: TaskRowProps) {
  const status = statusConfig[task.status]
  const StatusIcon = status.icon

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <Link
      href={`/task/${task.id}`}
      className={cn(
        "group flex items-center gap-4 p-4 rounded-lg border border-slate-800",
        "bg-slate-900/30 hover:bg-slate-800/50 hover:border-slate-700",
        "transition-all cursor-pointer",
        className
      )}
    >
      {/* Status Badge */}
      <div className={cn(
        "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono border",
        status.className
      )}>
        <StatusIcon className={cn(
          "h-3.5 w-3.5",
          task.status === 'executing' && "animate-spin"
        )} />
        <span>{status.label}</span>
      </div>

      {/* Task Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-100 truncate group-hover:text-white transition-colors">
          {task.user_request}
        </p>
        <p className="text-xs text-slate-500 mt-0.5">
          {status.description}
        </p>
      </div>

      {/* Current Agent */}
      {task.current_agent && (
        <div className="hidden sm:flex items-center px-2 py-1 rounded bg-slate-800 border border-slate-700">
          <span className="text-xs font-mono text-slate-400">
            {task.current_agent.toUpperCase()}
          </span>
        </div>
      )}

      {/* Timestamp */}
      <div className="text-xs text-slate-500 font-mono">
        {formatDate(task.created_at)}
      </div>
    </Link>
  )
}

export default TaskRow
