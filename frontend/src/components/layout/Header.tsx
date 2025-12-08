/**
 * Header Component
 *
 * Top navigation bar for Mission Control.
 * Displays logo, connection status, and settings.
 */

'use client'

import { Activity, Settings, Zap } from 'lucide-react'
import Link from 'next/link'

interface HeaderProps {
  isConnected?: boolean
}

export function Header({ isConnected = true }: HeaderProps) {
  return (
    <header className="h-14 border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="flex items-center justify-between h-full px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 group">
          <div className="relative">
            <Zap className="h-6 w-6 text-amber-400 group-hover:text-amber-300 transition-colors" />
            <div className="absolute inset-0 bg-amber-400/20 blur-lg group-hover:bg-amber-300/30 transition-all" />
          </div>
          <span className="text-lg font-semibold text-slate-100 tracking-tight">
            Antigravity
          </span>
          <span className="text-xs font-mono text-slate-500 ml-1">DEV</span>
        </Link>

        {/* Status & Actions */}
        <div className="flex items-center gap-4">
          {/* Connection Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800">
            <div className={`
              w-2 h-2 rounded-full
              ${isConnected
                ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]'
                : 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]'
              }
            `} />
            <span className="text-xs font-mono text-slate-400">
              {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>

          {/* Activity Indicator */}
          <button className="p-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors">
            <Activity className="h-5 w-5" />
          </button>

          {/* Settings */}
          <button className="p-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors">
            <Settings className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  )
}

export default Header
