import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { 
  Clock, Loader2, Eye, Play, TestTube, FileText, 
  CheckCircle2, XCircle, AlertTriangle, Pause 
} from 'lucide-react';

const statusConfig = {
  pending: {
    icon: Clock,
    label: 'Pending',
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-500/10',
    borderColor: 'border-zinc-500/20'
  },
  planning: {
    icon: Loader2,
    label: 'Planning',
    color: 'text-violet-400',
    bgColor: 'bg-violet-500/10',
    borderColor: 'border-violet-500/20',
    animate: true
  },
  plan_review: {
    icon: Eye,
    label: 'Review Plan',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/20'
  },
  executing: {
    icon: Play,
    label: 'Executing',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/20',
    animate: true
  },
  testing: {
    icon: TestTube,
    label: 'Testing',
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/20',
    animate: true
  },
  documenting: {
    icon: FileText,
    label: 'Documenting',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    animate: true
  },
  completed: {
    icon: CheckCircle2,
    label: 'Completed',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20'
  },
  failed: {
    icon: XCircle,
    label: 'Failed',
    color: 'text-rose-400',
    bgColor: 'bg-rose-500/10',
    borderColor: 'border-rose-500/20'
  },
  review_required: {
    icon: AlertTriangle,
    label: 'Needs Review',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/20'
  },
  paused: {
    icon: Pause,
    label: 'Paused',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/20'
  }
};

export default function StatusBadge({ status, size = 'md' }) {
  const config = statusConfig[status] || statusConfig.pending;
  const Icon = config.icon;
  
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5'
  };
  
  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-3.5 h-3.5',
    lg: 'w-4 h-4'
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        sizeClasses[size],
        config.bgColor,
        config.borderColor,
        config.color
      )}
    >
      <Icon 
        className={cn(
          iconSizes[size],
          config.animate && 'animate-spin'
        )} 
      />
      <span>{config.label}</span>
    </motion.div>
  );
}

export { statusConfig };