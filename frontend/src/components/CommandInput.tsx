/**
 * CommandInput Component
 *
 * Central command palette for creating new tasks.
 * Prominent search-bar style input with repo selector.
 */

'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Send, ChevronDown, Loader2, Zap } from 'lucide-react'
import type { Repository } from '@/types/schema'
import { createTask } from '@/lib/api'
import { cn } from '@/lib/utils'

interface CommandInputProps {
  repos: Repository[]
  className?: string
}

export function CommandInput({ repos, className }: CommandInputProps) {
  const router = useRouter()
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(
    repos.length > 0 ? repos[0] : null
  )
  const [userRequest, setUserRequest] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    if (!selectedRepo || !userRequest.trim()) return

    setIsSubmitting(true)
    setError(null)

    try {
      const task = await createTask(selectedRepo.id, userRequest.trim())
      router.push(`/task/${task.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create task')
      setIsSubmitting(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSubmit()
    }
  }

  return (
    <div className={cn("w-full max-w-3xl mx-auto", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Zap className="h-5 w-5 text-amber-400" />
        <h2 className="text-sm font-medium text-slate-300">
          New Mission
        </h2>
      </div>

      {/* Main Input Container */}
      <div className="relative rounded-xl border border-slate-700 bg-slate-900/80 backdrop-blur-sm overflow-hidden shadow-lg shadow-slate-950/50">
        {/* Repo Selector */}
        <div className="flex items-center border-b border-slate-800">
          <button
            type="button"
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="flex items-center gap-2 px-4 py-3 text-sm text-slate-300 hover:bg-slate-800 transition-colors"
          >
            <span className="font-mono text-slate-500">repo:</span>
            <span className="font-medium">
              {selectedRepo?.name || 'Select repository'}
            </span>
            <ChevronDown className={cn(
              "h-4 w-4 text-slate-500 transition-transform",
              isDropdownOpen && "rotate-180"
            )} />
          </button>

          {/* Dropdown */}
          {isDropdownOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 z-50 border border-slate-700 rounded-lg bg-slate-900 shadow-xl max-h-48 overflow-auto">
              {repos.map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => {
                    setSelectedRepo(repo)
                    setIsDropdownOpen(false)
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-slate-800 transition-colors",
                    selectedRepo?.id === repo.id && "bg-slate-800"
                  )}
                >
                  <span className="text-sm font-medium text-slate-100">
                    {repo.name}
                  </span>
                  <span className="text-xs font-mono text-slate-500 truncate">
                    {repo.path}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Text Input */}
        <textarea
          value={userRequest}
          onChange={(e) => setUserRequest(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe what you want to build or fix..."
          rows={3}
          className="w-full px-4 py-3 bg-transparent text-slate-100 placeholder:text-slate-500 resize-none focus:outline-none text-sm"
        />

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-slate-800 bg-slate-900/50">
          <div className="text-xs text-slate-500">
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 font-mono">
              ⌘
            </kbd>
            {' + '}
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 font-mono">
              Enter
            </kbd>
            {' to submit'}
          </div>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || !selectedRepo || !userRequest.trim()}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all",
              "bg-amber-500 text-slate-950 hover:bg-amber-400",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-amber-500"
            )}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Launching...
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                Launch Mission
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-3 px-4 py-2 rounded-lg bg-red-950/50 border border-red-900 text-red-400 text-sm">
          {error}
        </div>
      )}
    </div>
  )
}

export default CommandInput
