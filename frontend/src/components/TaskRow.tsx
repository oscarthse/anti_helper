/**
 * TaskRow Component
 *
 * Displays a task in a row format with status badge.
 * Clicking navigates to the War Room.
 */

'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Clock, AlertCircle, CheckCircle2, Loader2, PlayCircle, ChevronRight, ChevronDown } from 'lucide-react'
import type { Task, TaskStatus } from '@/types/schema'
import { fetchTasks } from '@/lib/api'
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
  paused: {
    label: 'PAUSED',
    icon: PlayCircle,
    className: 'bg-slate-700 text-slate-300 border-slate-600',
    description: 'Mission paused by user'
  },
}

export function TaskRow({ task, className }: TaskRowProps) {
  // Safe lookup, handle uppercase/lowercase, default to pending if missing
  const normalizedStatus = (task.status?.toLowerCase() || 'pending') as TaskStatus
  const status = statusConfig[normalizedStatus] || statusConfig.pending
  const StatusIcon = status.icon

  const [isExpanded, setIsExpanded] = useState(false)
  const [subtasks, setSubtasks] = useState<Task[]>([])
  const [isLoadingSubtasks, setIsLoadingSubtasks] = useState(false)

  const toggleExpand = async (e: React.MouseEvent) => {
    e.preventDefault() // Prevent navigation to WarRoom when clicking chevron

    if (isExpanded) {
      setIsExpanded(false)
      return
    }

    setIsExpanded(true)
    // Fetch if empty
    if (subtasks.length === 0) {
      setIsLoadingSubtasks(true)
      try {
        const children = await fetchTasks(undefined, task.id)
        setSubtasks(children)
      } catch (err) {
        console.error("Failed to fetch subtasks", err)
      } finally {
        setIsLoadingSubtasks(false)
      }
    }
  }

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
    <div className="flex flex-col space-y-2">
      <div className={cn(
        "group relative flex items-center gap-4 p-4 bg-slate-900/50 hover:bg-slate-900 rounded-lg border border-slate-800 transition-all hover:border-slate-700",
        className
      )}>
        {/* Accordion Toggle */}
        <button
          onClick={toggleExpand}
          className="p-1 rounded hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors"
        >
          {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>

        {/* Main Link Area */}
        <Link href={`/task/${task.id}`} className="flex-1 flex items-center gap-4 min-w-0">
          <div className={cn(
            "flex items-center justify-center h-10 w-10 rounded-full border bg-opacity-10 shrink-0",
            status.className.replace('bg-', 'bg-opacity-10 bg-'), // Ensure background opacity
          )}>
            <StatusIcon className="h-5 w-5" />
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium text-slate-200 truncate group-hover:text-blue-400 transition-colors">
              {task.title || task.user_request}
            </h3>
            <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
              <span>ID: {task.id.slice(0, 8)}</span>
              <span>•</span>
              <span>{formatDate(task.updated_at)}</span>
              {task.current_agent && (
                <>
                  <span>•</span>
                  <span className="text-blue-400/80">Agent: {task.current_agent}</span>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4 shrink-0">
            <div className={cn(
              "px-2.5 py-1 rounded-full text-xs font-medium border bg-opacity-10",
              status.className.replace('bg-', 'bg-opacity-10 bg-'),
            )}>
              {status.label}
            </div>
          </div>
        </Link>
      </div>

      {/* Subtasks View */}
      {isExpanded && (
        <div className="pl-12 space-y-2 relative">
          {/* Guide line */}
          <div className="absolute left-6 top-0 bottom-0 w-px bg-slate-800" />

          {isLoadingSubtasks && (
            <div className="flex items-center gap-2 text-xs text-slate-500 py-2">
              <Loader2 className="h-3 w-3 animate-spin" />
              Loadings steps...
            </div>
          )}

          {!isLoadingSubtasks && subtasks.length === 0 && (
            <div className="text-xs text-slate-600 italic py-2">No subtasks found.</div>
          )}

          {!isLoadingSubtasks && subtasks.map(sub => (
            <TaskRow key={sub.id} task={sub} className="bg-slate-900/30 border-slate-800/50" />
          ))}
        </div>
      )}
    </div>
  )
}

export default TaskRow
