/**
 * LiveStatusBar Component
 *
 * Shows real-time feedback about what's happening with the task.
 * Displays current step, status, and any progress or errors.
 */

import React from 'react'
import {
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Pause,
  Zap,
  FileCode,
  TestTube,
  BookOpen,
  Wrench,
  Bot,
  Activity,
  Wifi,
  WifiOff,
  Terminal,
  Play
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Task, TaskPlan, TaskStep, AgentLog } from '@/types/schema'

interface LiveStatusBarProps {
  task: Task
  status: string
  step?: number
  agent: string
  logs: AgentLog[]
  isConnected: boolean
  onPause: () => Promise<void>
  onResume: () => Promise<void>
  isPausing: boolean
  isResuming: boolean
}

const statusConfig: Record<string, {
  icon: React.ReactNode
  label: string
  color: string
  bgColor: string
  animate?: boolean
}> = {
  pending: {
    icon: <Clock className="w-4 h-4" />,
    label: 'Waiting to start',
    color: 'text-slate-400',
    bgColor: 'bg-slate-800',
  },
  planning: {
    icon: <Loader2 className="w-4 h-4" />,
    label: 'Planning approach',
    color: 'text-blue-400',
    bgColor: 'bg-blue-950/50',
    animate: true,
  },
  plan_review: {
    icon: <Pause className="w-4 h-4" />,
    label: 'Awaiting your approval',
    color: 'text-amber-400',
    bgColor: 'bg-amber-950/50',
  },
  review_required: {
    icon: <Pause className="w-4 h-4" />,
    label: 'Awaiting your review',
    color: 'text-amber-400',
    bgColor: 'bg-amber-950/50',
  },
  executing: {
    icon: <Zap className="w-4 h-4" />,
    label: 'Executing',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-950/50',
    animate: true,
  },
  completed: {
    icon: <CheckCircle className="w-4 h-4" />,
    label: 'Completed',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-950/50',
  },
  failed: {
    icon: <XCircle className="w-4 h-4" />,
    label: 'Failed',
    color: 'text-red-400',
    bgColor: 'bg-red-950/50',
  },
}

const agentIcons: Record<string, React.ReactNode> = {
  planner: <Bot className="w-3.5 h-3.5" />,
  coder_be: <FileCode className="w-3.5 h-3.5" />,
  coder_fe: <FileCode className="w-3.5 h-3.5" />,
  coder_infra: <Wrench className="w-3.5 h-3.5" />,
  qa: <TestTube className="w-3.5 h-3.5" />,
  docs: <BookOpen className="w-3.5 h-3.5" />,
}

export function LiveStatusBar({
  task,
  status,
  step = 0,
  agent,
  logs,
  isConnected,
  onPause,
  onResume,
  isPausing,
  isResuming
}: LiveStatusBarProps) {

  // Backwards compatibility alias if component uses currentStep internally
  const currentStep = step;
  const taskPlan = task.task_plan as unknown as TaskPlan | null;

  const currentStatusConfig = statusConfig[status] || statusConfig.pending
  const totalSteps = taskPlan?.steps?.length || 0
  const currentStepData = taskPlan?.steps?.find(s => s.order === currentStep)
  const progress = totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0

  return (
    <div className={cn(
      "px-4 py-3 border-b border-slate-800 transition-all",
      currentStatusConfig.bgColor
    )}>
      {/* Main Status Row */}
      <div className="flex items-center gap-3">
        {/* Status Icon */}
        <div className={cn(
          "flex-shrink-0",
          currentStatusConfig.color,
          currentStatusConfig.animate && "animate-pulse"
        )}>
          {currentStatusConfig.animate ? <Loader2 className="w-5 h-5 animate-spin" /> : currentStatusConfig.icon}
        </div>

        {/* Right: Pause/Resume & Connection */}
        <div className="flex items-center gap-4">
          {/* Play/Pause Control */}
          {status === 'paused' ? (
            <button
              onClick={onResume}
              disabled={isResuming}
              className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-md transition-colors text-xs font-medium"
            >
              {isResuming ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
              RESUME MISSION
            </button>
          ) : (
            <button
              onClick={onPause}
              disabled={isPausing || status === 'completed' || status === 'failed'}
              className="flex items-center gap-2 px-3 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 rounded-md transition-colors text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPausing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Pause className="h-3 w-3" />}
              PAUSE
            </button>
          )}

          <div className="flex items-center gap-2 px-3 py-1 bg-slate-800 rounded-full border border-slate-700">
            <span className={cn("font-medium text-sm", currentStatusConfig.color)}>
              {currentStatusConfig.label}
            </span>

            {/* Step Counter */}
            {totalSteps > 0 && (
              <span className="text-xs text-slate-500 font-mono">
                Step {currentStep}/{totalSteps}
              </span>
            )}
          </div>

          {/* Current Step Description */}
          {currentStepData && status === 'executing' && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-slate-500">
                {agentIcons[currentStepData.agent_persona] || <Bot className="w-3.5 h-3.5" />}
              </span>
              <span className="text-xs text-slate-400 truncate">
                {currentStepData.description}
              </span>
            </div>
          )}

          {/* Error Message */}
          {task?.error_message && (
            <div className="mt-1 text-xs text-red-400 truncate">
              ⚠️ {task.error_message}
            </div>
          )}
        </div>

        {/* Progress Ring */}
        {totalSteps > 0 && (
          <div className="flex-shrink-0">
            <ProgressRing progress={progress} size={36} />
          </div>
        )}
      </div>

      {/* Progress Bar */}
      {totalSteps > 0 && task.status === 'executing' && (
        <div className="mt-3">
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between mt-1.5 text-[10px] text-slate-600 font-mono">
            {taskPlan?.steps?.slice(0, 5).map((step, i) => (
              <span
                key={step.order}
                className={cn(
                  "transition-colors",
                  step.order <= currentStep ? "text-emerald-500" : "text-slate-600",
                  step.order === currentStep && "text-cyan-400"
                )}
              >
                {i + 1}
              </span>
            ))}
            {totalSteps > 5 && <span>···{totalSteps}</span>}
          </div>
        </div>
      )}
    </div>
  )
}

function ProgressRing({ progress, size }: { progress: number; size: number }) {
  const strokeWidth = 3
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const strokeDashoffset = circumference - (progress / 100) * circumference

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          className="text-slate-700"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          className="text-emerald-400 transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[10px] font-mono text-slate-400">{progress}%</span>
      </div>
    </div>
  )
}

export default LiveStatusBar
