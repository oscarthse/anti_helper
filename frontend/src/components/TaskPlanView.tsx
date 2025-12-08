/**
 * TaskPlanView Component
 *
 * Displays the task plan with step highlighting.
 * Completed steps appear green/dimmed.
 */

import { Check, Circle, PlayCircle } from 'lucide-react'
import type { TaskPlan, TaskStep } from '@/types/schema'
import { cn } from '@/lib/utils'
import { ArchitectureDiagram } from './ArchitectureDiagram'

interface TaskPlanViewProps {
  plan: TaskPlan
  currentStep?: number
  completedSteps?: number[]
}

const agentLabels: Record<string, { label: string; color: string }> = {
  planner: { label: 'Planner', color: 'text-blue-400' },
  coder_be: { label: 'Backend', color: 'text-amber-400' },
  coder_fe: { label: 'Frontend', color: 'text-purple-400' },
  coder_infra: { label: 'Infra', color: 'text-cyan-400' },
  qa: { label: 'QA', color: 'text-pink-400' },
  docs: { label: 'Docs', color: 'text-green-400' },
}

export function TaskPlanView({ plan, currentStep = 0, completedSteps = [] }: TaskPlanViewProps) {
  return (
    <div className="space-y-4">
      {/* Plan Summary Header */}
      <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800">
        <p className="text-sm text-slate-300">{plan.summary}</p>
        <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
          <span>Complexity: {plan.estimated_complexity}/10</span>
          <span>•</span>
          <span>{plan.steps?.length || 0} steps</span>
        </div>
      </div>

      {/* Architecture Diagram */}
      <ArchitectureDiagram plan={plan} />

      {/* Steps */}
      <div className="space-y-1">
        <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
          <span className="w-5 h-px bg-slate-700" />
          Execution Steps
          <span className="flex-1 h-px bg-slate-700" />
        </h4>
        {plan.steps?.map((step, index) => {
          const isCompleted = completedSteps.includes(step.order)
          const isCurrent = step.order === currentStep
          const isPending = !isCompleted && !isCurrent

          return (
            <StepItem
              key={step.order}
              step={step}
              index={index}
              isCompleted={isCompleted}
              isCurrent={isCurrent}
              isPending={isPending}
            />
          )
        })}
      </div>

      {/* Affected Files */}
      {plan.affected_files && plan.affected_files.length > 0 && (
        <div className="pt-3 border-t border-slate-800">
          <p className="text-xs text-slate-500 mb-2">Affected Files</p>
          <div className="space-y-1">
            {plan.affected_files.map((file, i) => (
              <div
                key={i}
                className="text-xs font-mono text-slate-400 truncate"
              >
                {file}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risks */}
      {plan.risks && plan.risks.length > 0 && (
        <div className="pt-3 border-t border-slate-800">
          <p className="text-xs text-amber-500 mb-2">⚠️ Potential Risks</p>
          <ul className="space-y-1">
            {plan.risks.map((risk, i) => (
              <li key={i} className="text-xs text-slate-400">
                • {risk}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function StepItem({
  step,
  index,
  isCompleted,
  isCurrent,
  isPending
}: {
  step: TaskStep
  index: number
  isCompleted: boolean
  isCurrent: boolean
  isPending: boolean
}) {
  const agent = agentLabels[step.agent_persona] || { label: step.agent_persona, color: 'text-slate-400' }

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-2 rounded-lg transition-all",
        isCurrent && "bg-slate-800/50 border border-slate-700",
        isCompleted && "opacity-60",
        isPending && "opacity-40"
      )}
    >
      {/* Step Icon */}
      <div className="mt-0.5 flex-shrink-0">
        {isCompleted ? (
          <Check className="h-4 w-4 text-emerald-400" />
        ) : isCurrent ? (
          <PlayCircle className="h-4 w-4 text-amber-400 animate-pulse" />
        ) : (
          <Circle className="h-4 w-4 text-slate-600" />
        )}
      </div>

      {/* Step Content */}
      <div className="flex-1 min-w-0">
        <p className={cn(
          "text-sm",
          isCurrent ? "text-slate-100" : "text-slate-400"
        )}>
          {step.description}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className={cn("text-xs font-mono", agent.color)}>
            {agent.label}
          </span>
          {step.files_affected && step.files_affected.length > 0 && (
            <span className="text-xs text-slate-600">
              {step.files_affected.length} files
            </span>
          )}
        </div>
      </div>

      {/* Step Number */}
      <span className="text-xs font-mono text-slate-600">
        {String(index + 1).padStart(2, '0')}
      </span>
    </div>
  )
}

export default TaskPlanView
