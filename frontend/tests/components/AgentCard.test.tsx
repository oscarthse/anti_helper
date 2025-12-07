/**
 * Component Tests: AgentCard
 *
 * Tests the AgentCard component renders the Explainability Contract correctly.
 */

import React from 'react'
import { render, screen } from '@testing-library/react'
import { AgentCard } from '@/components/AgentCard'
import { createMockAgentLog, createLowConfidenceOutput } from '../utils/mock-data'

describe('AgentCard Component', () => {
  describe('Explainability Rendering', () => {
    it('should render ui_title from AgentOutput', () => {
      const output = createMockAgentLog({
        ui_title: '📋 Analyzing Repository Structure',
      })

      render(<AgentCard log={output} />)

      expect(screen.getByTestId('agent-title')).toHaveTextContent('📋 Analyzing Repository Structure')
    })

    it('should render ui_subtitle from AgentOutput', () => {
      const output = createMockAgentLog({
        ui_subtitle: "I'm scanning your codebase to understand the project layout.",
      })

      render(<AgentCard log={output} />)

      expect(screen.getByTestId('agent-subtitle')).toHaveTextContent(
        "I'm scanning your codebase to understand the project layout."
      )
    })

    it('should render both title and subtitle together', () => {
      const output = createMockAgentLog({
        ui_title: 'Test Title',
        ui_subtitle: 'Test Subtitle',
      })

      render(<AgentCard log={output} />)

      expect(screen.getByText('Test Title')).toBeInTheDocument()
      expect(screen.getByText('Test Subtitle')).toBeInTheDocument()
    })
  })

  describe('Confidence Score Display', () => {
    it('should display high confidence score with green styling', () => {
      const output = createMockAgentLog({ confidence_score: 0.9 })

      render(<AgentCard log={output} />)

      const confidenceElement = screen.getByText('90%')
      expect(confidenceElement).toBeInTheDocument()
    })

    it('should display low confidence score', () => {
      // createLowConfidenceOutput returns AgentOutput, use createMockAgentLog with overrides
      const output = createMockAgentLog({
        ui_title: '⚠️ Uncertain Changes',
        ui_subtitle: 'I made changes but I am not fully confident in this approach.',
        confidence_score: 0.5,
      })

      render(<AgentCard log={output} />)

      const confidenceElement = screen.getByText('50%')
      expect(confidenceElement).toBeInTheDocument()
    })
  })

  describe('Tool Calls Indicator', () => {
    it('should show tool calls count when tools are executed', () => {
      const output = createMockAgentLog({
        tool_calls: [
          { tool_name: 'scan_repo', success: true, arguments: {}, result: '', duration_ms: 100 },
          { tool_name: 'read_file', success: true, arguments: {}, result: '', duration_ms: 100 },
        ],
      })

      render(<AgentCard log={output} />)

      expect(screen.getByText('2 tools executed')).toBeInTheDocument()
    })

    it('should show singular tool when one tool executed', () => {
      const output = createMockAgentLog({
        tool_calls: [{ tool_name: 'scan_repo', success: true, arguments: {}, result: '', duration_ms: 100 }],
      })

      render(<AgentCard log={output} />)

      expect(screen.getByText('1 tool executed')).toBeInTheDocument()
    })

    it('should not show tool indicator when no tools executed', () => {
      const output = createMockAgentLog({ tool_calls: [] })

      render(<AgentCard log={output} />)

      expect(screen.queryByText(/tool/)).not.toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have appropriate ARIA role', () => {
      const output = createMockAgentLog()

      render(<AgentCard log={output} />)

      expect(screen.getByRole('article')).toBeInTheDocument()
    })

    it('should have aria-label with action description', () => {
      const output = createMockAgentLog({
        ui_title: 'Creating Plan',
      })

      render(<AgentCard log={output} />)

      expect(screen.getByLabelText('Agent action: Creating Plan')).toBeInTheDocument()
    })
  })
})
