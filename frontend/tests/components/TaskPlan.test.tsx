/**
 * Component Tests: TaskPlan
 *
 * Tests conditional rendering of the TaskPlan component,
 * particularly the Review Required badge based on task status.
 */

import React from 'react'
import { render, screen } from '@testing-library/react'
import { TaskPlan } from '@/components/TaskPlan'
import {
  createMockTask,
  createReviewRequiredTask,
  createExecutingTask,
  createFailedTask,
  createMockTaskPlan,
} from '../utils/mock-data'

describe('TaskPlan Component', () => {
  describe('Conditional Review Badge Rendering', () => {
    it('should show Review Required badge when status is REVIEW_REQUIRED', () => {
      const task = createReviewRequiredTask()

      render(<TaskPlan task={task} />)

      expect(screen.getByTestId('review-badge')).toBeInTheDocument()
      expect(screen.getByText('⚠️ Review Required')).toBeInTheDocument()
    })

    it('should NOT show Review Required badge when status is EXECUTING', () => {
      const task = createExecutingTask()

      render(<TaskPlan task={task} />)

      expect(screen.queryByTestId('review-badge')).not.toBeInTheDocument()
    })

    it('should NOT show Review Required badge when status is PENDING', () => {
      const task = createMockTask({ status: 'pending' })

      render(<TaskPlan task={task} />)

      expect(screen.queryByTestId('review-badge')).not.toBeInTheDocument()
    })

    it('should NOT show Review Required badge when status is COMPLETED', () => {
      const task = createMockTask({ status: 'completed' })

      render(<TaskPlan task={task} />)

      expect(screen.queryByTestId('review-badge')).not.toBeInTheDocument()
    })
  })

  describe('Status Badge Display', () => {
    it('should display correct status label for each status', () => {
      const statuses = [
        { status: 'pending', label: 'Pending' },
        { status: 'executing', label: 'Executing' },
        { status: 'completed', label: 'Completed' },
        { status: 'failed', label: 'Failed' },
      ] as const

      for (const { status, label } of statuses) {
        const { unmount } = render(
          <TaskPlan task={createMockTask({ status })} />
        )

        expect(screen.getByTestId('status-badge')).toHaveTextContent(label)
        unmount()
      }
    })
  })

  describe('Task Information Display', () => {
    it('should display task title', () => {
      const task = createMockTask({ title: 'Add Input Validation' })

      render(<TaskPlan task={task} />)

      expect(screen.getByText('Add Input Validation')).toBeInTheDocument()
    })

    it('should display user request', () => {
      const task = createMockTask({
        user_request: 'Add validation to the user registration endpoint',
      })

      render(<TaskPlan task={task} />)

      expect(screen.getByText('Add validation to the user registration endpoint')).toBeInTheDocument()
    })
  })

  describe('Plan Steps Display', () => {
    it('should display plan steps when provided', () => {
      const task = createMockTask()
      const plan = createMockTaskPlan()

      render(<TaskPlan task={task} plan={plan} />)

      expect(screen.getByText('Analyze endpoint')).toBeInTheDocument()
      expect(screen.getByText('Add validation')).toBeInTheDocument()
      expect(screen.getByText('Run tests')).toBeInTheDocument()
    })

    it('should show step count in header', () => {
      const task = createMockTask()
      const plan = createMockTaskPlan()

      render(<TaskPlan task={task} plan={plan} />)

      expect(screen.getByText('Plan (3 steps)')).toBeInTheDocument()
    })

    it('should not show plan section when plan is null', () => {
      const task = createMockTask()

      render(<TaskPlan task={task} plan={null} />)

      expect(screen.queryByText(/Plan \(/)).not.toBeInTheDocument()
    })
  })

  describe('Error Display', () => {
    it('should display error message when task has failed', () => {
      const task = createFailedTask()

      render(<TaskPlan task={task} />)

      expect(screen.getByText('Test execution failed: ImportError')).toBeInTheDocument()
    })

    it('should not display error section when no error', () => {
      const task = createMockTask({ error_message: null })

      render(<TaskPlan task={task} />)

      expect(screen.queryByText(/failed/i)).not.toBeInTheDocument()
    })
  })
})
