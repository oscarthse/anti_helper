import React from 'react';
import { motion } from 'framer-motion';
import { Clock, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { createPageUrl } from '@/utils';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import StatusBadge from './StatusBadge';
import ProgressBar from './ProgressBar';
import AgentAvatar from './AgentAvatar';

export default function TaskCard({ task, index = 0 }) {
  const isActive = ['planning', 'executing', 'testing', 'documenting'].includes(task.status);
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
    >
      <Link to={createPageUrl(`TaskWarRoom?id=${task.id}`)}>
        <div className={cn(
          'relative group rounded-xl border p-5 transition-all duration-300',
          'bg-zinc-900/50 border-zinc-800 hover:border-zinc-700',
          'hover:shadow-xl hover:shadow-black/20',
          isActive && 'border-zinc-700'
        )}>
          {/* Active glow */}
          {isActive && (
            <motion.div
              className="absolute -inset-px rounded-xl bg-gradient-to-r from-blue-500/10 via-transparent to-cyan-500/10 -z-10"
              animate={{ opacity: [0.3, 0.6, 0.3] }}
              transition={{ repeat: Infinity, duration: 2 }}
            />
          )}
          
          {/* Header */}
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-semibold text-zinc-100 truncate mb-1">
                {task.title || 'Untitled Task'}
              </h3>
              <p className="text-sm text-zinc-500 line-clamp-2">
                {task.user_request}
              </p>
            </div>
            <StatusBadge status={task.status} size="sm" />
          </div>
          
          {/* Progress */}
          <div className="mb-4">
            <ProgressBar
              currentStep={task.current_step || 0}
              totalSteps={task.total_steps || 1}
              status={task.status}
              showLabel={false}
            />
          </div>
          
          {/* Footer */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {task.current_agent && (
                <AgentAvatar persona={task.current_agent} size="sm" isActive={isActive} />
              )}
              <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                <Clock className="w-3.5 h-3.5" />
                <span>{format(new Date(task.created_at || task.created_date), 'MMM d, h:mm a')}</span>
              </div>
            </div>
            
            <motion.div
              className="flex items-center gap-1 text-xs font-medium text-zinc-500 group-hover:text-zinc-300 transition-colors"
              whileHover={{ x: 2 }}
            >
              <span>View</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </motion.div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}