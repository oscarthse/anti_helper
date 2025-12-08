
'use client'

import { useState, useEffect } from 'react'
import { Folder, FileCode, ChevronRight, ChevronDown, Loader2, RefreshCw } from 'lucide-react'
import { fetchFileTree } from '@/lib/api'
import { cn } from '@/lib/utils'

interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileNode[]
}

interface FileTreeProps {
  repoId: string
  className?: string
}

export function FileTree({ repoId, className }: FileTreeProps) {
  const [tree, setTree] = useState<FileNode[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadTree = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await fetchFileTree(repoId)
      setTree(data)
    } catch (err) {
      console.error('Failed to load file tree:', err)
      setError('Failed to load files')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadTree()
  }, [repoId])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8 text-slate-500">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 text-center text-red-400 text-sm">
        <p>{error}</p>
        <button
          onClick={loadTree}
          className="mt-2 text-xs underline hover:text-red-300"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className={cn("text-xs font-mono select-none", className)}>
      <div className="flex items-center justify-between mb-2 px-2">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Files
        </h3>
        <button
          onClick={loadTree}
          title="Refresh File Tree"
          className="p-1 hover:bg-slate-800 rounded text-slate-500 hover:text-slate-300 transition-colors"
        >
          <RefreshCw className="h-3 w-3" />
        </button>
      </div>
      <div className="space-y-0.5">
        {tree.map((node) => (
          <TreeNode key={node.path} node={node} depth={0} />
        ))}
        {tree.length === 0 && (
          <div className="text-slate-600 italic px-2">Empty repository</div>
        )}
      </div>
    </div>
  )
}

function TreeNode({ node, depth }: { node: FileNode; depth: number }) {
  const [isExpanded, setIsExpanded] = useState(true) // Expand by default? Or false? relative to depth?
  // Let's expand root level by default

  const hasChildren = node.type === 'directory' && node.children && node.children.length > 0

  const toggle = () => {
    if (node.type === 'directory') {
      setIsExpanded(!isExpanded)
    }
  }

  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-1.5 py-1 px-2 rounded hover:bg-slate-800/50 cursor-pointer transition-colors whitespace-nowrap",
          node.type === 'file' ? "text-slate-300" : "text-blue-300 font-medium"
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={toggle}
      >
        <span className="opacity-50 flex-shrink-0 w-4">
          {node.type === 'directory' && (
            isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />
          )}
        </span>

        {node.type === 'directory' ? (
          <Folder className="h-3.5 w-3.5 text-blue-400/80" />
        ) : (
          <FileCode className="h-3.5 w-3.5 text-slate-500" />
        )}

        <span className="truncate">{node.name}</span>
      </div>

      {isExpanded && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.path} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}
