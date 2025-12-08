/**
 * DiffViewer Component
 *
 * Displays code diffs with syntax highlighting.
 * Simple implementation without external dependencies.
 */

import { FileCode, Plus, Minus } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DiffViewerProps {
  changeSet?: Record<string, unknown>
  className?: string
}

export function DiffViewer({ changeSet, className }: DiffViewerProps) {
  if (!changeSet) {
    return (
      <div className={cn("h-full flex items-center justify-center p-4", className)}>
        <div className="text-center text-slate-500">
          <FileCode className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No code changes yet</p>
          <p className="text-xs mt-1 text-slate-600">
            Diffs will appear here when the Coder Agent makes changes
          </p>
        </div>
      </div>
    )
  }

  const diff = (changeSet.diff as string) || ''
  const filePath = (changeSet.file_path as string) || 'unknown'
  const explanation = (changeSet.explanation as string) || ''
  const action = (changeSet.action as string) || 'modified'

  const lines = diff.split('\n')

  return (
    <div className={cn("h-full flex flex-col overflow-hidden", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-2 min-w-0">
          <FileCode className="h-4 w-4 text-slate-500 flex-shrink-0" />
          <span className="text-xs font-mono text-slate-300 truncate">
            {filePath.split('/').pop()}
          </span>
          <ActionBadge action={action} />
        </div>
      </div>

      {/* Explanation */}
      {explanation && (
        <div className="px-4 py-2 text-xs text-slate-400 bg-slate-900/30 border-b border-slate-800">
          {explanation}
        </div>
      )}

      {/* Diff Content */}
      <div className="flex-1 overflow-auto">
        <pre className="text-xs font-mono p-4">
          {lines.map((line, index) => (
            <DiffLine key={index} line={line} />
          ))}
        </pre>
      </div>
    </div>
  )
}

function DiffLine({ line }: { line: string }) {
  const isAddition = line.startsWith('+') && !line.startsWith('+++')
  const isDeletion = line.startsWith('-') && !line.startsWith('---')
  const isHeader = line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')

  return (
    <div
      className={cn(
        "flex items-start",
        isAddition && "bg-emerald-950/30 text-emerald-300",
        isDeletion && "bg-red-950/30 text-red-300",
        isHeader && "text-slate-500",
        !isAddition && !isDeletion && !isHeader && "text-slate-400"
      )}
    >
      {/* Line indicator */}
      <span className="w-6 flex-shrink-0 text-center">
        {isAddition && <Plus className="h-3 w-3 inline" />}
        {isDeletion && <Minus className="h-3 w-3 inline" />}
      </span>

      {/* Line content */}
      <code className="flex-1 whitespace-pre-wrap break-all">
        {line}
      </code>
    </div>
  )
}

function ActionBadge({ action }: { action: string }) {
  const config: Record<string, { label: string; className: string }> = {
    created: { label: 'NEW', className: 'bg-emerald-950 text-emerald-400 border-emerald-800' },
    modified: { label: 'MOD', className: 'bg-amber-950 text-amber-400 border-amber-800' },
    deleted: { label: 'DEL', className: 'bg-red-950 text-red-400 border-red-800' },
  }

  const { label, className } = config[action] || config.modified

  return (
    <span className={cn("px-1.5 py-0.5 text-[10px] font-mono rounded border", className)}>
      {label}
    </span>
  )
}

export default DiffViewer
