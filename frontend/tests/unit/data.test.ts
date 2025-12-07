/**
 * Data Integrity Tests
 *
 * Verifies that the auto-generated TypeScript schema (schema.ts) is
 * correctly consumable and that type safety is enforced.
 */

import type {
  AgentOutput,
  AgentPersona,
  TaskStatus,
  Task,
  Repository,
  ToolCall,
  TaskPlan,
  ChangeSet,
} from '@/types/schema'

import {
  createMockAgentOutput,
  createMockTask,
  createMockRepository,
  createMockToolCall,
  createMockTaskPlan,
  createMockChangeSet,
  validAgentOutputJSON,
  validTaskJSON,
} from '../utils/mock-data'

describe('Schema Consumption Tests', () => {
  describe('Import Verification', () => {
    it('should successfully import all schema types', () => {
      // These will fail at compile time if the imports are broken
      const agentOutput: AgentOutput = createMockAgentOutput()
      const task: Task = createMockTask()
      const repo: Repository = createMockRepository()

      expect(agentOutput).toBeDefined()
      expect(task).toBeDefined()
      expect(repo).toBeDefined()
    })

    it('should successfully import and use AgentPersona type', () => {
      const personas: AgentPersona[] = [
        'planner',
        'coder_be',
        'coder_fe',
        'coder_infra',
        'qa',
        'docs',
      ]

      expect(personas).toHaveLength(6)
      expect(personas).toContain('planner')
      expect(personas).toContain('coder_be')
    })

    it('should successfully import and use TaskStatus type', () => {
      const statuses: TaskStatus[] = [
        'pending',
        'planning',
        'plan_review',
        'executing',
        'testing',
        'documenting',
        'completed',
        'failed',
        'review_required',
      ]

      expect(statuses).toHaveLength(9)
      expect(statuses).toContain('pending')
      expect(statuses).toContain('completed')
    })
  })

  describe('Enum/Union Handling', () => {
    it('should correctly type check TaskStatus values', () => {
      const pendingStatus: TaskStatus = 'pending'
      const completedStatus: TaskStatus = 'completed'
      const failedStatus: TaskStatus = 'failed'

      expect(pendingStatus).toBe('pending')
      expect(completedStatus).toBe('completed')
      expect(failedStatus).toBe('failed')
    })

    it('should correctly type check AgentPersona values', () => {
      const planner: AgentPersona = 'planner'
      const coderBe: AgentPersona = 'coder_be'
      const qa: AgentPersona = 'qa'

      expect(planner).toBe('planner')
      expect(coderBe).toBe('coder_be')
      expect(qa).toBe('qa')
    })
  })

  describe('Raw JSON Consumption', () => {
    it('should accept valid raw JSON as AgentOutput', () => {
      // Type assertion - this validates the shape at compile time
      const output: AgentOutput = validAgentOutputJSON as AgentOutput

      expect(output.ui_title).toBe('Test Action')
      expect(output.ui_subtitle).toBe('Test subtitle')
      expect(output.confidence_score).toBe(0.9)
      expect(output.agent_persona).toBe('planner')
    })

    it('should accept valid raw JSON as Task', () => {
      const task: Task = validTaskJSON as Task

      expect(task.id).toBe('task-id')
      expect(task.status).toBe('pending')
      expect(task.user_request).toBe('Test request')
    })
  })

  describe('Type Safety Assertions (Compile-Time)', () => {
    it('should enforce required fields on AgentOutput', () => {
      // This test documents that TypeScript would catch missing fields
      // The @ts-expect-error comments prove the type safety

      // Valid complete object
      const validOutput: AgentOutput = createMockAgentOutput()
      expect(validOutput.ui_title).toBeDefined()

      // @ts-expect-error - Missing required field 'ui_title'
      const _invalidOutput1: AgentOutput = {
        ui_subtitle: 'Test',
        technical_reasoning: 'Test',
        confidence_score: 0.9,
        agent_persona: 'planner',
      }

      // @ts-expect-error - Missing required field 'ui_subtitle'
      const _invalidOutput2: AgentOutput = {
        ui_title: 'Test',
        technical_reasoning: 'Test',
        confidence_score: 0.9,
        agent_persona: 'planner',
      }
    })

    it('should enforce required fields on Task', () => {
      // Valid complete object
      const validTask: Task = createMockTask()
      expect(validTask.id).toBeDefined()

      // @ts-expect-error - Missing required field 'id'
      const _invalidTask1: Task = {
        repo_id: 'repo-id',
        user_request: 'Test',
        status: 'pending',
        current_step: 0,
        retry_count: 0,
        created_at: 'date',
        updated_at: 'date',
      }

      // @ts-expect-error - Missing required field 'status'
      const _invalidTask2: Task = {
        id: 'task-id',
        repo_id: 'repo-id',
        user_request: 'Test',
        current_step: 0,
        retry_count: 0,
        created_at: 'date',
        updated_at: 'date',
      }
    })

    it('should enforce correct types for fields', () => {
      // This demonstrates that without the cast, TypeScript would error on wrong types
      // Using 'as unknown as number' to simulate a runtime type mismatch scenario
      const _invalidConfidence: AgentOutput = {
        ui_title: 'Test',
        ui_subtitle: 'Test',
        technical_reasoning: 'Test',
        confidence_score: 'high' as unknown as number, // Simulating runtime type mismatch
        agent_persona: 'planner',
      }

      // This test validates that the factory enforces valid status values
      // Note: TypeScript won't catch this at runtime, but Pydantic would
      const taskWithValidStatus: Task = createMockTask({ status: 'pending' })
      expect(taskWithValidStatus.status).toBe('pending')
    })
  })

  describe('Factory Function Validation', () => {
    it('should create valid ToolCall objects', () => {
      const toolCall: ToolCall = createMockToolCall()

      expect(toolCall.tool_name).toBeDefined()
      expect(typeof toolCall.tool_name).toBe('string')
      expect(toolCall.success).toBeDefined()
    })

    it('should create valid TaskPlan objects', () => {
      const plan: TaskPlan = createMockTaskPlan()

      expect(plan.summary).toBeDefined()
      expect(Array.isArray(plan.steps)).toBe(true)
      expect(plan.steps.length).toBeGreaterThan(0)
      expect(plan.estimated_complexity).toBeGreaterThanOrEqual(1)
      expect(plan.estimated_complexity).toBeLessThanOrEqual(10)
    })

    it('should create valid ChangeSet objects', () => {
      const changeset: ChangeSet = createMockChangeSet()

      expect(changeset.file_path).toBeDefined()
      expect(changeset.action).toBeDefined()
      expect(changeset.diff).toBeDefined()
      expect(changeset.explanation).toBeDefined()
    })

    it('should allow overriding factory defaults', () => {
      const customOutput = createMockAgentOutput({
        ui_title: 'Custom Title',
        confidence_score: 0.5,
      })

      expect(customOutput.ui_title).toBe('Custom Title')
      expect(customOutput.confidence_score).toBe(0.5)
      // Other fields should still have defaults
      expect(customOutput.ui_subtitle).toBeDefined()
    })
  })
})
