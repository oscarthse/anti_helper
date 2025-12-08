import React from 'react';
import { motion } from 'framer-motion';
import { Brain, Code, TestTube, Settings, Cpu } from 'lucide-react';
import { cn } from '@/lib/utils';

const agentConfig = {
  planner: {
    icon: Brain,
    color: 'from-violet-500 to-purple-600',
    bgColor: 'bg-violet-500/10',
    label: 'Planner'
  },
  coder_be: {
    icon: Code,
    color: 'from-blue-500 to-cyan-600',
    bgColor: 'bg-blue-500/10',
    label: 'Backend Coder'
  },
  coder_fe: {
    icon: Code,
    color: 'from-emerald-500 to-teal-600',
    bgColor: 'bg-emerald-500/10',
    label: 'Frontend Coder'
  },
  qa: {
    icon: TestTube,
    color: 'from-amber-500 to-orange-600',
    bgColor: 'bg-amber-500/10',
    label: 'QA Agent'
  },
  system: {
    icon: Settings,
    color: 'from-zinc-400 to-zinc-500',
    bgColor: 'bg-zinc-500/10',
    label: 'System'
  }
};

export default function AgentAvatar({ persona, size = 'md', isActive = false }) {
  const config = agentConfig[persona] || agentConfig.system;
  const Icon = config.icon;
  
  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12'
  };
  
  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6'
  };

  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={cn(
        'relative rounded-xl flex items-center justify-center',
        sizeClasses[size],
        config.bgColor
      )}
    >
      <div className={cn(
        'absolute inset-0 rounded-xl bg-gradient-to-br opacity-20',
        config.color
      )} />
      <Icon className={cn(iconSizes[size], 'text-zinc-100 relative z-10')} />
      
      {isActive && (
        <motion.div
          className={cn(
            'absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-gradient-to-br',
            config.color
          )}
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
        >
          <div className="absolute inset-0.5 rounded-full bg-zinc-900" />
          <div className={cn(
            'absolute inset-1 rounded-full bg-gradient-to-br',
            config.color
          )} />
        </motion.div>
      )}
    </motion.div>
  );
}

export { agentConfig };