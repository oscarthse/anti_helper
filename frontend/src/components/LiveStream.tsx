/**
 * LiveStream Component
 *
 * Displays real-time agent activity stream from the backend.
 * Handles loading, error, and empty states gracefully.
 */

'use client'

import React, { useState, useEffect } from 'react'
import type { AgentLog } from '@/types/schema'
import { AgentCard } from './AgentCard'

interface LiveStreamProps {
  taskId?: string
  className?: string
  onError?: (error: Error) => void
}

type StreamState = 'loading' | 'connected' | 'error' | 'empty'

export function LiveStream({ taskId, className = '', onError }: LiveStreamProps) {
  const [state, setState] = useState<StreamState>('loading')
  const [logs, setLogs] = useState<AgentLog[]>([])
  const [errorMessage, setErrorMessage] = useState<string>('')

  useEffect(() => {
    if (!taskId) {
      setState('empty')
      return
    }

    const connectToStream = async () => {
      try {
        setState('loading')

        // Import API dynamically (will be mocked in tests)
        const { subscribeToTaskStream } = await import('@/lib/api')

        await subscribeToTaskStream(taskId, {
          onLog: (log: AgentLog) => {
            setLogs(prev => [...prev, log])
            setState('connected')
          },
          onError: (error: Error) => {
            setState('error')
            setErrorMessage(error.message || 'API Connection Failed')
            onError?.(error)
          },
          onComplete: () => {
            if (logs.length === 0) {
              setState('empty')
            }
          },
        })
      } catch (error) {
        setState('error')
        setErrorMessage((error as Error).message || 'API Connection Failed')
        onError?.(error as Error)
      }
    }

    connectToStream()
  }, [taskId, onError])

  // Loading state
  if (state === 'loading') {
    return (
      <div
        className={`flex items-center justify-center p-8 ${className}`}
        role="status"
        aria-label="Loading"
      >
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        <span className="sr-only">Loading agent stream...</span>
      </div>
    )
  }

  // Error state
  if (state === 'error') {
    return (
      <div
        className={`rounded-lg border border-red-200 bg-red-50 p-4 ${className}`}
        role="alert"
        aria-label="Error"
      >
        <div className="flex items-center gap-2 text-red-800">
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <span className="font-medium">API Connection Failed</span>
        </div>
        <p className="mt-2 text-sm text-red-700">{errorMessage}</p>
      </div>
    )
  }

  // Empty state
  if (state === 'empty' || logs.length === 0) {
    return (
      <div
        className={`rounded-lg border border-dashed p-8 text-center ${className}`}
        role="status"
      >
        <p className="text-muted-foreground">No tasks in queue</p>
        <p className="text-sm text-muted-foreground mt-1">
          Agent activity will appear here when tasks are running.
        </p>
      </div>
    )
  }

  // Connected with logs
  return (
    <div className={`space-y-4 ${className}`}>
      {logs.map((log) => (
        <AgentCard
          key={log.id}
          output={{
            ui_title: log.ui_title,
            ui_subtitle: log.ui_subtitle,
            technical_reasoning: log.technical_reasoning,
            tool_calls: (log.tool_calls || []) as any,
            confidence_score: log.confidence_score,
            agent_persona: log.agent_persona as any,
          }}
        />
      ))}
    </div>
  )
}

export default LiveStream
