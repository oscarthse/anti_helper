/**
 * TerminalOutput Component
 *
 * Matrix-style console for raw command output.
 * Black background with green monospace text.
 */

import { Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TerminalOutputProps {
  output?: string
  className?: string
}

export function TerminalOutput({ output, className }: TerminalOutputProps) {
  const lines = output?.split('\n').filter(Boolean) || []

  return (
    <div className={cn("h-full flex flex-col bg-black", className)}>
      {/* Terminal Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-800 bg-slate-900/80">
        <Terminal className="h-3.5 w-3.5 text-emerald-400" />
        <span className="text-xs font-mono text-slate-400">Terminal</span>

        {/* Mock traffic lights */}
        <div className="flex items-center gap-1.5 ml-auto">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
        </div>
      </div>

      {/* Terminal Content */}
      <div className="flex-1 overflow-auto p-3 font-mono text-xs">
        {lines.length === 0 ? (
          <div className="text-slate-600">
            <span className="text-emerald-400">$</span> Waiting for commands...
            <span className="animate-pulse">▋</span>
          </div>
        ) : (
          <div className="space-y-1">
            {lines.map((line, index) => (
              <TerminalLine key={index} line={line} />
            ))}
            <div className="text-emerald-400">
              <span>$</span>
              <span className="animate-pulse ml-1">▋</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function TerminalLine({ line }: { line: string }) {
  // Detect different types of output
  const isError = line.toLowerCase().includes('error') ||
    line.toLowerCase().includes('failed') ||
    line.toLowerCase().includes('exception')
  const isSuccess = line.toLowerCase().includes('passed') ||
    line.toLowerCase().includes('success') ||
    line.toLowerCase().includes('ok')
  const isCommand = line.startsWith('$') || line.startsWith('>')
  const isPath = line.includes('/') && !line.includes(' ')

  return (
    <div className={cn(
      "whitespace-pre-wrap break-all",
      isError && "text-red-400",
      isSuccess && "text-emerald-400",
      isCommand && "text-amber-400",
      isPath && "text-cyan-400",
      !isError && !isSuccess && !isCommand && !isPath && "text-emerald-300/70"
    )}>
      {line}
    </div>
  )
}

export default TerminalOutput
