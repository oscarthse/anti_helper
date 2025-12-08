import React from 'react';
import { motion } from 'framer-motion';
import { 
  CheckCircle2, Circle, ArrowRight, AlertTriangle,
  Brain, Code, TestTube, FileText 
} from 'lucide-react';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';

const stepTypeIcons = {
  plan: Brain,
  code: Code,
  test: TestTube,
  document: FileText,
  default: Circle
};

const stepTypeColors = {
  plan: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
  code: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  test: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  document: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  default: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20'
};

export default function TaskPlanView({ plan, currentStep = 0 }) {
  if (!plan) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-zinc-500">
        <Brain className="w-10 h-10 mb-3 text-zinc-600" />
        <p className="text-sm font-medium">No plan generated yet</p>
        <p className="text-xs mt-1">The planner agent will create one shortly</p>
      </div>
    );
  }

  const steps = plan.steps || [];
  const summary = plan.summary || '';

  return (
    <div className="space-y-6">
      {/* Summary */}
      {summary && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700/50"
        >
          <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            Plan Summary
          </h4>
          <div className="prose prose-invert prose-sm max-w-none text-zinc-300">
            <ReactMarkdown>{summary}</ReactMarkdown>
          </div>
        </motion.div>
      )}
      
      {/* Steps */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          Execution Steps ({currentStep}/{steps.length})
        </h4>
        
        <div className="space-y-2">
          {steps.map((step, idx) => {
            const isCompleted = idx < currentStep;
            const isCurrent = idx === currentStep;
            const stepType = step.type || 'default';
            const Icon = stepTypeIcons[stepType] || stepTypeIcons.default;
            
            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className={cn(
                  'relative flex items-start gap-3 p-3 rounded-lg border transition-all',
                  isCompleted && 'bg-emerald-500/5 border-emerald-500/20',
                  isCurrent && 'bg-blue-500/5 border-blue-500/30 shadow-lg shadow-blue-500/5',
                  !isCompleted && !isCurrent && 'bg-zinc-900/30 border-zinc-800'
                )}
              >
                {/* Status indicator */}
                <div className={cn(
                  'flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center border',
                  isCompleted && 'bg-emerald-500/20 border-emerald-500/30',
                  isCurrent && 'bg-blue-500/20 border-blue-500/30',
                  !isCompleted && !isCurrent && 'bg-zinc-800 border-zinc-700'
                )}>
                  {isCompleted ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : isCurrent ? (
                    <motion.div
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ repeat: Infinity, duration: 1 }}
                    >
                      <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
                    </motion.div>
                  ) : (
                    <span className="text-xs font-mono text-zinc-500">{idx + 1}</span>
                  )}
                </div>
                
                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      'inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded border',
                      stepTypeColors[stepType]
                    )}>
                      <Icon className="w-3 h-3" />
                      {stepType}
                    </span>
                    {step.requires_review && (
                      <span className="inline-flex items-center gap-1 text-xs text-amber-400">
                        <AlertTriangle className="w-3 h-3" />
                        Review
                      </span>
                    )}
                  </div>
                  
                  <h5 className={cn(
                    'text-sm font-medium',
                    isCompleted ? 'text-zinc-400' : 'text-zinc-200'
                  )}>
                    {step.title || step.name || `Step ${idx + 1}`}
                  </h5>
                  
                  {step.description && (
                    <p className="text-xs text-zinc-500 mt-1">
                      {step.description}
                    </p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}