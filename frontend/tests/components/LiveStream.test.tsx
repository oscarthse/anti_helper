/**
 * Component Tests: LiveStream
 *
 * Tests loading, error, and empty states for the LiveStream component.
 * Includes API mocking for streaming failure scenarios.
 */

import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { LiveStream } from '@/components/LiveStream'
import { createMockAgentLog } from '../utils/mock-data'

// Mock the API module
jest.mock('@/lib/api', () => ({
  subscribeToTaskStream: jest.fn(),
  APIError: class APIError extends Error {
    constructor(message: string, public status: number) {
      super(message)
      this.name = 'APIError'
    }
  },
}))

// Get the mocked module
const mockApi = jest.requireMock('@/lib/api')

describe('LiveStream Component', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('Loading State', () => {
    it('should show loading spinner initially', () => {
      // Mock a pending stream
      mockApi.subscribeToTaskStream.mockImplementation(() => new Promise(() => { }))

      render(<LiveStream taskId="test-task-id" />)

      expect(screen.getByRole('status')).toBeInTheDocument()
      expect(screen.getByLabelText('Loading')).toBeInTheDocument()
    })

    it('should have accessible loading text', () => {
      mockApi.subscribeToTaskStream.mockImplementation(() => new Promise(() => { }))

      render(<LiveStream taskId="test-task-id" />)

      expect(screen.getByText('Loading agent stream...')).toBeInTheDocument()
    })
  })

  describe('Error State', () => {
    it('should show error message when API connection fails', async () => {
      mockApi.subscribeToTaskStream.mockRejectedValue(
        new Error('API Connection Failed')
      )

      render(<LiveStream taskId="test-task-id" />)

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument()
      })

      // Use getAllByText since error message appears in both title and description
      const errorElements = screen.getAllByText('API Connection Failed')
      expect(errorElements.length).toBeGreaterThan(0)
    })

    it('should show error for 500 server errors', async () => {
      mockApi.subscribeToTaskStream.mockRejectedValue(
        new mockApi.APIError('Internal Server Error', 500)
      )

      render(<LiveStream taskId="test-task-id" />)

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument()
      })
    })

    it('should call onError callback when error occurs', async () => {
      const onError = jest.fn()
      mockApi.subscribeToTaskStream.mockRejectedValue(new Error('Connection failed'))

      render(<LiveStream taskId="test-task-id" onError={onError} />)

      await waitFor(() => {
        expect(onError).toHaveBeenCalled()
      })

      expect(onError).toHaveBeenCalledWith(expect.any(Error))
    })
  })

  describe('Empty State', () => {
    it('should show empty message when no taskId provided', () => {
      render(<LiveStream />)

      expect(screen.getByText('No tasks in queue')).toBeInTheDocument()
    })

    it('should show helpful subtitle in empty state', () => {
      render(<LiveStream />)

      expect(screen.getByText('Agent activity will appear here when tasks are running.')).toBeInTheDocument()
    })
  })

  describe('Connected State', () => {
    it('should render agent logs when stream provides data', async () => {
      // Mock successful stream that emits a log
      mockApi.subscribeToTaskStream.mockImplementation(
        async (taskId: string, callbacks: { onLog: (log: unknown) => void }) => {
          setTimeout(() => {
            callbacks.onLog(createMockAgentLog({
              ui_title: 'Test Agent Action',
              ui_subtitle: 'Testing the stream',
            }))
          }, 10)
          return () => { }
        }
      )

      render(<LiveStream taskId="test-task-id" />)

      await waitFor(() => {
        expect(screen.getByText('Test Agent Action')).toBeInTheDocument()
      }, { timeout: 1000 })

      expect(screen.getByText('Testing the stream')).toBeInTheDocument()
    })
  })

  describe('Integration with API Client', () => {
    it('should attempt to subscribe when taskId is provided', async () => {
      mockApi.subscribeToTaskStream.mockResolvedValue(() => { })

      render(<LiveStream taskId="my-specific-task-id" />)

      // Wait for the async effect to run
      await waitFor(() => {
        expect(mockApi.subscribeToTaskStream).toHaveBeenCalled()
      })
    })
  })
})
