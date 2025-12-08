import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, Pause, Trash2, RotateCcw, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export default function TaskControls({ 
  task, 
  onPause, 
  onResume, 
  onDelete,
  onRetry,
  isLoading = false 
}) {
  const isPaused = task?.status === 'paused';
  const isFailed = task?.status === 'failed';
  const isCompleted = task?.status === 'completed';
  const isActive = ['planning', 'executing', 'testing', 'documenting'].includes(task?.status);

  return (
    <div className="flex items-center gap-2">
      {/* Pause/Resume Button */}
      <AnimatePresence mode="wait">
        {isActive && (
          <motion.div
            key="pause"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
          >
            <Button
              variant="outline"
              size="sm"
              onClick={onPause}
              disabled={isLoading}
              className={cn(
                'border-amber-500/30 text-amber-400 hover:bg-amber-500/10 hover:text-amber-300',
                'transition-all duration-200'
              )}
            >
              <Pause className="w-4 h-4 mr-1.5" />
              Pause
            </Button>
          </motion.div>
        )}
        
        {isPaused && (
          <motion.div
            key="resume"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
          >
            <Button
              variant="outline"
              size="sm"
              onClick={onResume}
              disabled={isLoading}
              className={cn(
                'border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300',
                'transition-all duration-200',
                'relative overflow-hidden'
              )}
            >
              <motion.div
                className="absolute inset-0 bg-emerald-500/10"
                animate={{ opacity: [0, 0.5, 0] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
              />
              <Play className="w-4 h-4 mr-1.5 relative z-10" />
              <span className="relative z-10">Resume</span>
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Retry Button (for failed tasks) */}
      {isFailed && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            disabled={isLoading}
            className="border-blue-500/30 text-blue-400 hover:bg-blue-500/10 hover:text-blue-300"
          >
            <RotateCcw className="w-4 h-4 mr-1.5" />
            Retry
          </Button>
        </motion.div>
      )}
      
      {/* Delete Button */}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            disabled={isLoading}
            className="border-rose-500/30 text-rose-400 hover:bg-rose-500/10 hover:text-rose-300"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent className="bg-zinc-900 border-zinc-800">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-zinc-100 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-rose-400" />
              Delete Task
            </AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400">
              This will permanently delete this task and all associated logs, 
              changesets, and file operations. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={onDelete}
              className="bg-rose-500/20 border-rose-500/30 text-rose-400 hover:bg-rose-500/30"
            >
              Delete Task
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}