/**
 * RepoCard Component
 *
 * Displays repository information in a card format.
 * Shows name, path, framework, and last scanned time.
 */

import { FolderGit2, Clock, Code } from 'lucide-react'
import type { Repository } from '@/types/schema'
import { cn } from '@/lib/utils'

interface RepoCardProps {
  repo: Repository
  className?: string
  onClick?: () => void
}

export function RepoCard({ repo, className, onClick }: RepoCardProps) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))

    if (diffHours < 1) return 'Just now'
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        "group p-4 rounded-lg border border-slate-800 bg-slate-900/50",
        "hover:bg-slate-800/50 hover:border-slate-700 transition-all cursor-pointer",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <FolderGit2 className="h-5 w-5 text-amber-400" />
          <h3 className="font-semibold text-slate-100 group-hover:text-white transition-colors">
            {repo.name}
          </h3>
        </div>
        {repo.framework && (
          <span className="px-2 py-0.5 text-xs font-mono rounded bg-slate-800 text-slate-400 border border-slate-700">
            {repo.framework}
          </span>
        )}
      </div>

      {/* Path */}
      <p className="text-sm font-mono text-slate-500 truncate mb-3">
        {repo.path}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-1">
          <Code className="h-3.5 w-3.5" />
          <span>{repo.project_type || 'Unknown'}</span>
        </div>
        <div className="flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          <span>{formatDate(repo.updated_at)}</span>
        </div>
      </div>
    </div>
  )
}

export default RepoCard
