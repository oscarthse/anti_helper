import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

export default function ProgressBar({ 
  currentStep, 
  totalSteps, 
  status,
  showLabel = true,
  className 
}) {
  const progress = totalSteps > 0 ? (currentStep / totalSteps) * 100 : 0;
  
  const getGradient = () => {
    switch (status) {
      case 'completed':
        return 'from-emerald-500 to-emerald-400';
      case 'failed':
        return 'from-rose-500 to-rose-400';
      case 'paused':
        return 'from-amber-500 to-amber-400';
      case 'review_required':
        return 'from-amber-500 to-orange-400';
      default:
        return 'from-blue-500 to-cyan-400';
    }
  };

  return (
    <div className={cn('w-full', className)}>
      {showLabel && (
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-zinc-500 font-medium">
            Progress
          </span>
          <span className="text-xs text-zinc-400 font-mono">
            {currentStep}/{totalSteps} steps
          </span>
        </div>
      )}
      
      <div className="relative h-2 bg-zinc-800 rounded-full overflow-hidden">
        {/* Background glow */}
        <div className="absolute inset-0 bg-gradient-to-r from-zinc-800 via-zinc-700/50 to-zinc-800" />
        
        {/* Progress fill */}
        <motion.div
          className={cn(
            'absolute inset-y-0 left-0 bg-gradient-to-r rounded-full',
            getGradient()
          )}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ 
            type: 'spring', 
            stiffness: 100, 
            damping: 20 
          }}
        />
        
        {/* Shimmer effect for active states */}
        {['executing', 'testing', 'planning', 'documenting'].includes(status) && (
          <motion.div
            className="absolute inset-y-0 w-20 bg-gradient-to-r from-transparent via-white/20 to-transparent"
            animate={{ x: ['-100%', '400%'] }}
            transition={{ 
              repeat: Infinity, 
              duration: 1.5, 
              ease: 'linear' 
            }}
          />
        )}
      </div>
      
      {/* Percentage label */}
      {showLabel && (
        <div className="mt-1.5 text-right">
          <span className="text-xs font-mono text-zinc-500">
            {Math.round(progress)}%
          </span>
        </div>
      )}
    </div>
  );
}