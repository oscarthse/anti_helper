/**
 * TaskPlan Component
 *
 * Displays a task's plan with conditional rendering based on status.
 * Shows review badge when status is 'review_required'.
 */

import React from 'react'
import type { Task, TaskStatus, TaskPlan as TaskPlanType } from '@/types/schema'

interface TaskPlanProps {
  task: Task
  plan?: TaskPlanType | null
  className?: string
}

const statusColors: Partial<Record<TaskStatus, string>> = {
  pending: 'bg-gray-100 text-gray-800',
  planning: 'bg-blue-100 text-blue-800',
  executing: 'bg-yellow-100 text-yellow-800',
  testing: 'bg-purple-100 text-purple-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  review_required: 'bg-orange-100 text-orange-800',
}

const statusLabels: Partial<Record<TaskStatus, string>> = {
  pending: 'Pending',
  planning: 'Planning',
  plan_review: 'Plan Review',
  executing: 'Executing',
  testing: 'Testing',
  documenting: 'Documenting',
  completed: 'Completed',
  failed: 'Failed',
  review_required: 'Review Required',
}

export function TaskPlan({ task, plan, className = '' }: TaskPlanProps) {
  const statusColor = statusColors[task.status] || 'bg-gray-100 text-gray-800'
  const statusLabel = statusLabels[task.status] || task.status

  return (
    <div className={`rounded-lg border bg-card p-4 ${className}`}>
      {/* Header with status */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">
          {task.title || 'Task Plan'}
        </h2>

        <div className="flex items-center gap-2">
          {/* Review Required Badge - Conditional Rendering */}
          {task.status === 'review_required' && (
            <span
              className="px-3 py-1 rounded-full text-sm font-medium bg-orange-100 text-orange-800 border border-orange-300"
              data-testid="review-badge"
            >
              ⚠️ Review Required
            </span>
          )}

          {/* Status Badge */}
          <span
            className={`px-2 py-1 rounded text-xs font-medium ${statusColor}`}
            data-testid="status-badge"
          >
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Task request */}
      <div className="mb-4">
        <h3 className="text-sm font-medium text-muted-foreground mb-1">Request</h3>
        <p className="text-sm">{task.user_request}</p>
      </div>

      {/* Plan steps */}
      {plan && plan.steps && plan.steps.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            Plan ({plan.steps.length} steps)
          </h3>
          <div className="space-y-2">
            {plan.steps.map((step, index) => (
              <div
                key={index}
                className={`flex items-start gap-3 p-2 rounded ${index + 1 === task.current_step ? 'bg-blue-50' : ''
                  }`}
              >
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-medium">
                  {step.order}
                </span>
                <div className="flex-1">
                  <p className="text-sm font-medium">{step.description}</p>
                  <p className="text-xs text-muted-foreground">
                    {step.agent_persona}
                    {step.files_affected && step.files_affected.length > 0 && (
                      <span> • {step.files_affected.length} file(s)</span>
                    )}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error message */}
      {task.error_message && (
        <div className="mt-4 p-3 rounded bg-red-50 border border-red-200">
          <p className="text-sm text-red-800">{task.error_message}</p>
        </div>
      )}
    </div>
  )
}

export default TaskPlan
