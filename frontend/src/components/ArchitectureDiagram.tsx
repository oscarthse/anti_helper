/**
 * ArchitectureDiagram Component
 *
 * Generates a visual SVG diagram of the proposed file structure
 * based on the task plan.
 */

import React from 'react'
import { FileCode, FolderOpen, GitBranch, Box } from 'lucide-react'
import type { TaskPlan, TaskStep } from '@/types/schema'

interface ArchitectureDiagramProps {
  plan: TaskPlan
}

interface FileNode {
  name: string
  path: string
  type: 'file' | 'folder'
  children?: FileNode[]
  stepIndex?: number
  agent?: string
}

const agentColors: Record<string, string> = {
  coder_be: '#f59e0b',    // amber
  coder_fe: '#a855f7',    // purple
  coder_infra: '#06b6d4', // cyan
  qa: '#ec4899',          // pink
  docs: '#22c55e',        // green
  planner: '#3b82f6',     // blue
}

export function ArchitectureDiagram({ plan }: ArchitectureDiagramProps) {
  // Build file tree from plan
  const fileTree = buildFileTree(plan)
  const connections = generateConnections(plan.steps || [])

  if (!fileTree.children?.length && !plan.affected_files?.length) {
    return (
      <div className="flex items-center justify-center p-6 text-slate-500 text-sm">
        <Box className="w-4 h-4 mr-2" />
        No file structure available yet
      </div>
    )
  }

  return (
    <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 rounded-xl border border-slate-800 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
        <GitBranch className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-medium text-slate-200">Proposed Structure</span>
        <span className="ml-auto text-xs text-slate-500">
          {countFiles(fileTree)} files affected
        </span>
      </div>

      {/* Diagram */}
      <div className="p-4 overflow-x-auto">
        <div className="min-w-[300px]">
          <FileTreeNode node={fileTree} depth={0} />
        </div>
      </div>

      {/* Legend */}
      <div className="px-4 py-2 border-t border-slate-800 bg-slate-900/50">
        <div className="flex flex-wrap gap-3">
          {Object.entries(agentColors).map(([agent, color]) => (
            <div key={agent} className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-xs text-slate-400 capitalize">
                {agent.replace('coder_', '').replace('_', ' ')}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function FileTreeNode({ node, depth }: { node: FileNode; depth: number }) {
  const isRoot = depth === 0

  return (
    <div className={!isRoot ? 'ml-4 pl-3 border-l border-slate-700/50' : ''}>
      {!isRoot && (
        <div className="flex items-center gap-2 py-1 group">
          {/* Connection line */}
          <span className="w-3 h-px bg-slate-700/50" />

          {/* Icon */}
          {node.type === 'folder' ? (
            <FolderOpen className="w-4 h-4 text-amber-400 flex-shrink-0" />
          ) : (
            <FileCode
              className="w-4 h-4 flex-shrink-0"
              style={{ color: node.agent ? agentColors[node.agent] || '#94a3b8' : '#94a3b8' }}
            />
          )}

          {/* Name */}
          <span
            className={`text-sm font-mono truncate ${node.type === 'folder' ? 'text-slate-300 font-medium' : 'text-slate-400'
              }`}
          >
            {node.name}
          </span>

          {/* Step badge */}
          {node.stepIndex !== undefined && (
            <span className="ml-auto text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 font-mono">
              #{node.stepIndex + 1}
            </span>
          )}
        </div>
      )}

      {/* Children */}
      {node.children && node.children.length > 0 && (
        <div className={isRoot ? '' : 'mt-0.5'}>
          {node.children.map((child, i) => (
            <FileTreeNode key={child.path + i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

function buildFileTree(plan: TaskPlan): FileNode {
  const root: FileNode = {
    name: 'project',
    path: '/',
    type: 'folder',
    children: [],
  }

  // Collect all files from steps and affected_files
  const allFiles = new Set<string>()
  const fileToStep = new Map<string, { index: number; agent: string }>()

  plan.steps?.forEach((step, index) => {
    step.files_affected?.forEach((file) => {
      allFiles.add(file)
      if (!fileToStep.has(file)) {
        fileToStep.set(file, { index, agent: step.agent_persona })
      }
    })
  })

  plan.affected_files?.forEach((file) => {
    allFiles.add(file)
  })

  // Build tree structure
  Array.from(allFiles).sort().forEach((filePath) => {
    const parts = filePath.replace(/^\//, '').split('/')
    let current = root

    parts.forEach((part, i) => {
      const isFile = i === parts.length - 1
      const existingChild = current.children?.find((c) => c.name === part)

      if (existingChild) {
        current = existingChild
      } else {
        const stepInfo = isFile ? fileToStep.get(filePath) : undefined
        const newNode: FileNode = {
          name: part,
          path: parts.slice(0, i + 1).join('/'),
          type: isFile ? 'file' : 'folder',
          children: isFile ? undefined : [],
          stepIndex: stepInfo?.index,
          agent: stepInfo?.agent,
        }
        current.children = current.children || []
        current.children.push(newNode)
        current = newNode
      }
    })
  })

  // Sort children: folders first, then files
  sortChildren(root)

  return root
}

function sortChildren(node: FileNode) {
  if (node.children) {
    node.children.sort((a, b) => {
      if (a.type === b.type) return a.name.localeCompare(b.name)
      return a.type === 'folder' ? -1 : 1
    })
    node.children.forEach(sortChildren)
  }
}

function countFiles(node: FileNode): number {
  if (node.type === 'file') return 1
  return (node.children || []).reduce((sum, child) => sum + countFiles(child), 0)
}

function generateConnections(steps: TaskStep[]): { from: string; to: string }[] {
  const connections: { from: string; to: string }[] = []

  for (let i = 0; i < steps.length - 1; i++) {
    const currentFiles = steps[i].files_affected || []
    const nextFiles = steps[i + 1].files_affected || []

    currentFiles.forEach((from) => {
      nextFiles.forEach((to) => {
        if (from !== to) {
          connections.push({ from, to })
        }
      })
    })
  }

  return connections
}

export default ArchitectureDiagram
