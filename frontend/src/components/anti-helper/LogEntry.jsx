import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Wrench, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import AgentAvatar from './AgentAvatar';
import ReactMarkdown from 'react-markdown';

const toolStatusIcons = {
  pending: Clock,
  success: CheckCircle2,
  error: XCircle
};

const toolStatusColors = {
  pending: 'text-zinc-400',
  success: 'text-emerald-400',
  error: 'text-rose-400'
};

export default function LogEntry({ log, isLatest = false }) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const hasDetails = log.technical_reasoning || (log.tool_calls && log.tool_calls.length > 0);
  const confidencePercent = Math.round((log.confidence_score || 0) * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className={cn(
        'relative rounded-xl border transition-all duration-200',
        isLatest 
          ? 'bg-zinc-800/80 border-zinc-700 shadow-lg shadow-black/20' 
          : 'bg-zinc-900/50 border-zinc-800 hover:border-zinc-700'
      )}
    >
      {/* Main content */}
      <div 
        className={cn(
          'p-4 cursor-pointer',
          hasDetails && 'cursor-pointer'
        )}
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-start gap-3">
          <AgentAvatar 
            persona={log.agent_persona} 
            size="md" 
            isActive={isLatest} 
          />
          
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <h4 className="text-sm font-semibold text-zinc-100 leading-tight">
                  {log.ui_title}
                </h4>
                <p className="text-xs text-zinc-400 mt-0.5 line-clamp-2">
                  {log.ui_subtitle}
                </p>
              </div>
              
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* Confidence indicator */}
                <div className="flex items-center gap-1">
                  <div className={cn(
                    'w-1.5 h-1.5 rounded-full',
                    confidencePercent >= 80 ? 'bg-emerald-400' :
                    confidencePercent >= 50 ? 'bg-amber-400' : 'bg-rose-400'
                  )} />
                  <span className="text-xs font-mono text-zinc-500">
                    {confidencePercent}%
                  </span>
                </div>
                
                {/* Expand toggle */}
                {hasDetails && (
                  <motion.div
                    animate={{ rotate: isExpanded ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChevronDown className="w-4 h-4 text-zinc-500" />
                  </motion.div>
                )}
              </div>
            </div>
            
            {/* Step indicator */}
            <div className="flex items-center gap-2 mt-2">
              <span className="text-xs font-mono text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">
                Step {log.step_number}
              </span>
              {log.requires_review && (
                <span className="text-xs font-medium text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
                  Review Required
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* Expanded content */}
      <AnimatePresence>
        {isExpanded && hasDetails && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-2 border-t border-zinc-800">
              {/* Technical reasoning */}
              {log.technical_reasoning && (
                <div className="mb-4">
                  <h5 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
                    Technical Reasoning
                  </h5>
                  <div className="prose prose-invert prose-sm max-w-none text-zinc-300">
                    <ReactMarkdown>{log.technical_reasoning}</ReactMarkdown>
                  </div>
                </div>
              )}
              
              {/* Tool calls */}
              {log.tool_calls && log.tool_calls.length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
                    Tool Calls
                  </h5>
                  <div className="space-y-2">
                    {log.tool_calls.map((tool, idx) => {
                      const StatusIcon = toolStatusIcons[tool.status] || Clock;
                      return (
                        <div 
                          key={idx}
                          className="flex items-start gap-2 p-2 rounded-lg bg-zinc-800/50"
                        >
                          <Wrench className="w-4 h-4 text-zinc-500 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono text-zinc-300">
                                {tool.tool_name}
                              </span>
                              <StatusIcon className={cn(
                                'w-3.5 h-3.5',
                                toolStatusColors[tool.status]
                              )} />
                            </div>
                            {tool.result && (
                              <p className="text-xs text-zinc-500 mt-1 truncate">
                                {tool.result}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Latest indicator glow */}
      {isLatest && (
        <motion.div
          className="absolute -inset-px rounded-xl bg-gradient-to-r from-blue-500/20 via-transparent to-cyan-500/20 -z-10"
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ repeat: Infinity, duration: 2 }}
        />
      )}
    </motion.div>
  );
}