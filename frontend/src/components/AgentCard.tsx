/**
 * AgentCard Component
 *
 * Displays an agent's output with the Explainability Contract:
 * - ui_title: User-friendly action title
 * - ui_subtitle: Plain English explanation
 * - confidence_score: Visual confidence indicator
 */

import React from 'react'
import type { AgentOutput, AgentPersona } from '@/types/schema'

const personaIcons: Record<AgentPersona, string> = {
  planner: '📋',
  coder_be: '💻',
  coder_fe: '🎨',
  coder_infra: '🔧',
  qa: '🧪',
  docs: '📝',
}

const personaLabels: Record<AgentPersona, string> = {
  planner: 'Planner',
  coder_be: 'Backend Engineer',
  coder_fe: 'Frontend Engineer',
  coder_infra: 'Infrastructure',
  qa: 'QA Engineer',
  docs: 'Documentation',
}

interface AgentCardProps {
  output: AgentOutput
  className?: string
}

export function AgentCard({ output, className = '' }: AgentCardProps) {
  const icon = personaIcons[output.agent_persona] || '🤖'
  const label = personaLabels[output.agent_persona] || 'Agent'

  const confidenceColor =
    output.confidence_score >= 0.8 ? 'bg-green-100 text-green-800' :
      output.confidence_score >= 0.6 ? 'bg-yellow-100 text-yellow-800' :
        'bg-red-100 text-red-800'

  return (
    <div
      className={`rounded-lg border bg-card p-4 shadow-sm ${className}`}
      role="article"
      aria-label={`Agent action: ${output.ui_title}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xl" role="img" aria-label={label}>
            {icon}
          </span>
          <span className="text-sm font-medium text-muted-foreground">
            {label}
          </span>
        </div>

        <span
          className={`px-2 py-1 rounded text-xs font-medium ${confidenceColor}`}
          title={`Confidence: ${Math.round(output.confidence_score * 100)}%`}
        >
          {Math.round(output.confidence_score * 100)}%
        </span>
      </div>

      {/* Title - The Explainability Contract */}
      <h3 className="text-lg font-semibold mb-1" data-testid="agent-title">
        {output.ui_title}
      </h3>

      {/* Subtitle - Plain English explanation */}
      <p className="text-muted-foreground" data-testid="agent-subtitle">
        {output.ui_subtitle}
      </p>

      {/* Tool calls indicator */}
      {output.tool_calls && output.tool_calls.length > 0 && (
        <div className="mt-3 pt-3 border-t">
          <span className="text-xs text-muted-foreground">
            {output.tool_calls.length} tool{output.tool_calls.length > 1 ? 's' : ''} executed
          </span>
        </div>
      )}
    </div>
  )
}

export default AgentCard
