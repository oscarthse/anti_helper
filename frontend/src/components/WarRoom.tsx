/**
 * WarRoom Component
 *
 * 3-column cockpit layout for task execution.
 * Handles SSE streaming and real-time updates.
 */

'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import type { Task, AgentLog, TaskPlan, VerifiedFileEvent } from '@/types/schema'
import { subscribeToTaskStream, approveTaskPlan, pauseTask, resumeTask, deleteTask } from '@/lib/api'
import { TaskPlanView } from './TaskPlanView'
import { AgentCard } from './AgentCard'
import { DiffViewer } from './DiffViewer'
import { TerminalOutput } from './TerminalOutput'
import { LiveStatusBar } from './LiveStatusBar'
import { FileTree } from './FileTree'
import { AlertCircle, Wifi, WifiOff, CheckCircle, XCircle, Loader2, Trash2 } from 'lucide-react'
import { useProjectState } from '@/hooks/useProjectState'
import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'

interface WarRoomProps {
  task: Task
}

export function WarRoom({ task }: WarRoomProps) {
  const router = useRouter()
  // Glass Cockpit State (Websocket Truth)
  // We use this for Active Status to ensure "Pause" is reflected instantly
  const projectState = useProjectState(task.id)

  // Find current root task state from WS
  const liveTaskNode = projectState.tasks.find(t => t.id === task.id)

  const [logs, setLogs] = useState<AgentLog[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isReconnecting, setIsReconnecting] = useState(false)
  const [currentStep, setCurrentStep] = useState(task.current_step || 0)
  const [fileTreeRefreshTrigger, setFileTreeRefreshTrigger] = useState(0)
  const [verifiedSteps, setVerifiedSteps] = useState<Set<number>>(new Set())  // Track steps with verified files

  // Prefer WebSocket status, fallback to props
  const [taskStatus, setTaskStatus] = useState(liveTaskNode?.status?.toLowerCase() || task.status?.toLowerCase() || 'pending')

  // Sync local status when WebSocket updates
  useEffect(() => {
    if (liveTaskNode) {
      setTaskStatus(liveTaskNode.status.toLowerCase())
    }
  }, [liveTaskNode])

  const [isApproving, setIsApproving] = useState(false)
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // Pause/Resume State
  const [isPausing, setIsPausing] = useState(false)
  const [isResuming, setIsResuming] = useState(false)

  const streamRef = useRef<HTMLDivElement>(null)
  const cleanupRef = useRef<(() => void) | null>(null)

  // Sync taskStatus when task prop changes (e.g., after approval)
  useEffect(() => {
    const newStatus = task.status?.toLowerCase() || 'pending'
    setTaskStatus(newStatus)
  }, [task.status])

  // Handle plan approval
  const handleApprove = useCallback(async () => {
    setIsApproving(true)
    setApprovalError(null)
    try {
      await approveTaskPlan(task.id)
      setTaskStatus('executing')
    } catch (error) {
      console.error('Failed to approve:', error)
      setApprovalError(error instanceof Error ? error.message : 'Failed to approve')
    } finally {
      setIsApproving(false)
    }
  }, [task.id])

  // Handle Pause
  const handlePause = useCallback(async () => {
    setIsPausing(true)
    try {
      await pauseTask(task.id)
      setTaskStatus('paused')
    } catch (error) {
      console.error('Failed to pause:', error)
    } finally {
      setIsPausing(false)
    }
  }, [task.id])

  // Handle Resume
  const handleResume = useCallback(async () => {
    setIsResuming(true)
    try {
      await resumeTask(task.id)
      setTaskStatus('pending') // Optimistic update, stream will correct it
    } catch (error) {
      console.error('Failed to resume:', error)
    } finally {
      setIsResuming(false)
    }
  }, [task.id])

  // Handle Delete
  const handleDelete = useCallback(async () => {
    if (!confirm("Are you sure you want to delete this mission? This cannot be undone.")) return;

    setIsDeleting(true)
    try {
      await deleteTask(task.id)
      // Force hard reload to ensure Dashboard (Server Component) list is fresh.
      // Next.js client-side router cache might otherwise show the stale task.
      window.location.href = '/'
    } catch (error) {
      console.error("Failed to delete", error)
      setIsDeleting(false)
    }
  }, [task.id, router])


  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight
    }
  }, [logs])

  // Connect to SSE stream
  useEffect(() => {
    let retryCount = 0
    const maxRetries = 5

    const connect = async () => {
      try {
        setIsReconnecting(retryCount > 0)

        cleanupRef.current = await subscribeToTaskStream(task.id, {
          onLog: (log) => {
            setLogs(prev => {
              // Deduplicate by log ID
              if (log.id && prev.some(l => l.id === log.id)) {
                return prev
              }
              return [...prev, log]
            })
            setIsConnected(true)
            setIsReconnecting(false)
            retryCount = 0

            // Update current step based on log
            if (log.step_number > currentStep) {
              setCurrentStep(log.step_number)
            }

            // Refresh FileTree when coder agents complete (they create/modify files)
            if (log.agent_persona?.startsWith('coder')) {
              setFileTreeRefreshTrigger(prev => prev + 1)
            }
          },
          // VERIFIED FILE EVENTS: These are guaranteed to exist on disk
          onFileVerified: (event) => {
            // Track this step as having verified files
            setVerifiedSteps(prev => {
              const next = new Set(Array.from(prev))
              next.add(event.step_index)
              return next
            })

            // Update current step if this is a newer step
            if (event.step_index > currentStep) {
              setCurrentStep(event.step_index)
            }

            // Always refresh file tree when files are verified
            setFileTreeRefreshTrigger(prev => prev + 1)

            console.log('[WarRoom] Verified file:', event.file_path, 'step:', event.step_index)
          },
          onError: (error) => {
            console.error('SSE Error:', error)
            setIsConnected(false)

            // Auto-retry with exponential backoff
            if (retryCount < maxRetries) {
              retryCount++
              const delay = Math.min(1000 * Math.pow(2, retryCount), 30000)
              setTimeout(connect, delay)
            }
          },
          onComplete: () => {
            setIsConnected(false)
          },
        })

        setIsConnected(true)
      } catch (error) {
        console.error('Failed to connect:', error)
        setIsConnected(false)
      }
    }

    connect()

    return () => {
      if (cleanupRef.current) {
        cleanupRef.current()
      }
    }
  }, [task.id, currentStep])

  // Parse task plan
  const taskPlan: TaskPlan | null = task.task_plan
    ? (task.task_plan as unknown as TaskPlan)
    : null

  // Get latest changeset for diff viewer
  const latestChangeSet = logs
    .filter(log => log.agent_persona.startsWith('coder'))
    .flatMap(log => log.tool_calls || [])
    .filter(tc => tc && typeof tc === 'object' && 'result' in tc)
    .pop()

  // Get terminal output from QA logs
  const terminalOutput = logs
    .filter(log => log.agent_persona === 'qa')
    .map(log => log.technical_reasoning)
    .join('\n')

  return (
    <div className="flex-1 flex overflow-hidden relative">
      {/* Plan Review Banner - Non-blocking notification at top */}
      {(taskStatus === 'plan_review' || taskStatus === 'review_required') && (
        <div className="absolute top-0 left-0 right-0 z-20 bg-gradient-to-b from-amber-950/95 to-amber-950/80 backdrop-blur-sm border-b border-amber-700 shadow-lg">
          <div className="p-4">
            <div className="flex items-start gap-4">
              {/* Icon */}
              <div className="h-10 w-10 rounded-full bg-amber-900/50 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="h-5 w-5 text-amber-400" />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-4 mb-2">
                  <div>
                    <h3 className="text-lg font-semibold text-amber-400">
                      Plan Requires Approval
                    </h3>
                    <p className="text-xs text-amber-200/60">
                      Review the Strategy panel below, then approve or reject
                    </p>
                  </div>

                  {/* Buttons */}
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      onClick={handleApprove}
                      disabled={isApproving}
                      className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors text-sm"
                    >
                      {isApproving ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Approving...
                        </>
                      ) : (
                        <>
                          <CheckCircle className="h-4 w-4" />
                          Approve
                        </>
                      )}
                    </button>
                    <button
                      disabled={isApproving}
                      className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 text-slate-200 font-medium rounded-lg transition-colors text-sm"
                    >
                      <XCircle className="h-4 w-4" />
                      Reject
                    </button>
                  </div>
                </div>

                {/* Plan Summary & Steps Preview */}
                {taskPlan && (
                  <div className="mt-2 p-3 bg-slate-900/50 rounded-lg border border-amber-800/50">
                    <p className="text-sm text-slate-300 mb-3">{taskPlan.summary}</p>

                    {/* Step List */}
                    {taskPlan.steps && taskPlan.steps.length > 0 && (
                      <div className="space-y-1.5 mb-3 max-h-48 overflow-y-auto pr-2">
                        <p className="text-xs text-amber-300/80 font-medium mb-2">Execution Plan:</p>
                        {taskPlan.steps.map((step, index) => (
                          <div
                            key={step.order || index}
                            className="flex items-start gap-2 text-xs"
                          >
                            <span className="font-mono text-amber-400/60 flex-shrink-0 w-5">
                              {String(index + 1).padStart(2, '0')}
                            </span>
                            <span className="text-slate-400 flex-1">{step.description}</span>
                            <span className="text-slate-600 flex-shrink-0 font-mono text-[10px]">
                              {step.agent_persona?.replace('coder_', '').toUpperCase() || 'AGENT'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center gap-3 text-xs text-amber-200/60 border-t border-slate-800 pt-2">
                      <span>📋 {taskPlan.steps?.length || 0} steps</span>
                      <span>•</span>
                      <span>⚡ Complexity: {taskPlan.estimated_complexity}/10</span>
                      {taskPlan.affected_files && taskPlan.affected_files.length > 0 && (
                        <>
                          <span>•</span>
                          <span>📁 {taskPlan.affected_files.length} files</span>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {approvalError && (
                  <div className="mt-2 p-2 rounded-lg bg-red-950/50 border border-red-800 text-red-400 text-sm">
                    {approvalError}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Column 1: Strategy (Task Plan) */}
      <div className={cn(
        "w-72 flex-shrink-0 border-r border-slate-800 overflow-auto bg-slate-950/50",
        (taskStatus === 'plan_review' || taskStatus === 'review_required') && "pt-40"
      )}>
        <div className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-slate-300 uppercase tracking-wider">
              Strategy
            </h2>
          </div>

          {taskPlan ? (
            <TaskPlanView
              plan={taskPlan}
              currentStep={currentStep}
              completedSteps={logs.map(l => l.step_number)}
            />
          ) : (
            <div className="text-sm text-slate-500 p-4 border border-dashed border-slate-800 rounded-lg text-center">
              Awaiting plan generation...
            </div>
          )}
        </div>
      </div>

      {/* Column 2: Activity (Live Stream) */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-slate-800">
        {/* Live Status Bar */}
        <LiveStatusBar
          task={task}
          status={taskStatus}
          step={currentStep}
          agent={logs[logs.length - 1]?.agent_persona || 'system'}
          logs={logs}
          isConnected={isConnected}
          onPause={handlePause}
          onResume={handleResume}
          isPausing={isPausing}
          isResuming={isResuming}
        />
        {/* Stream Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
          <div className="flex items-center gap-4">
            <h2 className="text-sm font-medium text-slate-300 uppercase tracking-wider">
              Activity Feed
            </h2>
          </div>

          <div className="flex items-center gap-3">
            {/* Delete Button */}
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              title="Delete Mission"
              className="text-slate-600 hover:text-red-400 transition-colors p-1"
            >
              {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            </button>

            {/* Connection Status */}
            <div className={cn(
              "flex items-center gap-1.5 px-2 py-1 rounded text-xs",
              isConnected
                ? "text-emerald-400"
                : isReconnecting
                  ? "text-amber-400"
                  : "text-red-400"
            )}>
              {isConnected ? (
                <>
                  <Wifi className="h-3.5 w-3.5" />
                  Live
                </>
              ) : isReconnecting ? (
                <>
                  <AlertCircle className="h-3.5 w-3.5 animate-pulse" />
                  Reconnecting...
                </>
              ) : (
                <>
                  <WifiOff className="h-3.5 w-3.5" />
                  Disconnected
                </>
              )}
            </div>
          </div>
        </div>

        {/* Stream Content with fade effect */}
        <div
          ref={streamRef}
          className="flex-1 overflow-auto p-4 space-y-4 relative"
          style={{
            maskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 100%)',
            WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 100%)',
          }}
        >
          {logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-slate-500">
              <div className="text-center">
                <div className="animate-pulse mb-2">
                  <div className="h-2 w-24 bg-slate-800 rounded mx-auto" />
                </div>
                <p className="text-sm">Waiting for agent activity...</p>
              </div>
            </div>
          ) : (
            [...logs]
              .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
              .map((log, index, sortedLogs) => (
                <div
                  key={log.id || index}
                  className="animate-in slide-in-from-bottom-2 duration-300"
                >
                  <AgentCard
                    log={log}
                    isLatest={index === sortedLogs.length - 1}
                  />
                </div>
              ))
          )}
        </div>
      </div>

      {/* Column 3: Artifacts (Diff & Terminal) */}
      <div className="w-96 flex-shrink-0 flex flex-col overflow-hidden bg-slate-950/30 border-l border-slate-800">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="text-sm font-medium text-slate-300 uppercase tracking-wider">
            Artifacts
          </h2>
        </div>

        <div className="flex-1 flex flex-col overflow-auto">

          {/* File Tree (Protocol: Truth) */}
          <div className="h-1/3 min-h-[200px] border-b border-slate-800 overflow-auto bg-slate-950/20">
            <FileTree repoId={task.repo_id} className="p-2" refreshTrigger={fileTreeRefreshTrigger} />
          </div>

          {/* Diff Viewer */}
          <div className="flex-1 min-h-0 border-b border-slate-800">
            <DiffViewer changeSet={latestChangeSet as Record<string, unknown> | undefined} />
          </div>

          {/* Terminal Output */}
          <div className="h-48 flex-shrink-0 bg-black">
            <TerminalOutput output={terminalOutput} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default WarRoom
