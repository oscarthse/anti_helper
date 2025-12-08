import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, Link, useSearchParams } from 'react-router-dom';
import { createPageUrl } from '@/utils';
import {
  ArrowLeft, Folder, ListTree, Clock, Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';

// New Antigravity Imports
import { fetchTask, deleteTask, pauseTask, resumeTask, fetchFileTree } from '@/api/antigravityClient';
import { useAgentEvents } from '@/hooks/useAgentEvents';

// UI Components
import StatusBadge from '@/components/anti-helper/StatusBadge';
import ProgressBar from '@/components/anti-helper/ProgressBar';
import TaskControls from '@/components/anti-helper/TaskControls';
import LiveStream from '@/components/anti-helper/LiveStream';
import TaskPlanView from '@/components/anti-helper/TaskPlanView';
import FileTree from '@/components/anti-helper/FileTree';
import AgentAvatar from '@/components/anti-helper/AgentAvatar';

export default function TaskWarRoom() {
  const [searchParams] = useSearchParams();
  const taskId = searchParams.get('id');
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [rightPanel, setRightPanel] = useState('plan');

  // Fetch task data (initial load + refetch on mutation)
  // CRITICAL: Refetch every 2s during execution for real-time progress
  const { data: task, isLoading: taskLoading, refetch: refetchTask } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => fetchTask(taskId),
    enabled: !!taskId,
    refetchOnWindowFocus: false,
    // TanStack Query v5: callback receives query object, access data via query.state.data
    refetchInterval: (query) => {
      const taskData = query.state.data;
      const isActive = taskData?.status && ['planning', 'executing', 'testing', 'documenting'].includes(taskData.status);
      return isActive ? 2000 : false;
    },
  });

  // Fetch ACTUAL file tree from repository filesystem
  const { data: fileTree, refetch: refetchFileTree, error: fileTreeError } = useQuery({
    queryKey: ['fileTree', task?.repo_id],
    queryFn: async () => {
      console.log('[FileTree] 📂 Fetching tree for repo_id:', task?.repo_id);
      const result = await fetchFileTree(task?.repo_id);
      console.log('[FileTree] 📂 Received tree data:', result?.length || 0, 'items');
      return result;
    },
    enabled: !!task?.repo_id,
    // TanStack Query v5: callback receives query object
    refetchInterval: () => {
      const isActive = task?.status && ['executing', 'testing', 'documenting'].includes(task.status);
      return isActive ? 3000 : false;
    },
  });

  // Debug: Log fileTree state on every render
  console.log('[TaskWarRoom] FileTree state:', {
    repoId: task?.repo_id,
    fileTree: fileTree?.length || 0,
    error: fileTreeError?.message
  });

  // SSE Hook for real-time logs, file events, and plan updates
  const {
    logs: agentLogs,
    fileEvents,
    taskPlan: ssePlan,
    status: streamStatus
  } = useAgentEvents(taskId, {
    onPlanReady: () => {
      console.log('[TaskWarRoom] Plan ready event - refetching task...');
      refetchTask();
    },
    onFileVerified: (fileData) => {
      console.log('[TaskWarRoom] File verified - refetching FileTree:', fileData.file_path);
      // Refetch actual filesystem tree
      refetchFileTree();
    }
  });

  // Use SSE plan if available, otherwise fall back to REST data
  const activePlan = ssePlan || task?.task_plan;
  const currentStep = task?.current_step || 0;

  // Determine if streaming based on task status
  const isStreaming = task && ['planning', 'executing', 'testing', 'documenting'].includes(task.status);

  // ==========================================================================
  // Mutations (wired to our hardened FastAPI endpoints)
  // ==========================================================================

  const pauseMutation = useMutation({
    mutationFn: () => pauseTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      refetchTask();
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => resumeTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      refetchTask();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteTask(taskId),
    onSuccess: () => {
      // Hard redirect to dashboard after deletion
      navigate(createPageUrl('Dashboard'));
    },
  });

  const retryMutation = useMutation({
    mutationFn: () => resumeTask(taskId), // Retry = Resume for now
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      refetchTask();
    },
  });

  // ==========================================================================
  // Render Guards
  // ==========================================================================

  if (!taskId) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-zinc-500 mb-4">No task ID provided</p>
          <Link to={createPageUrl('Dashboard')}>
            <Button variant="outline" className="border-zinc-700 text-zinc-300">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Dashboard
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  if (taskLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-600" />
      </div>
    );
  }

  if (!task) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-zinc-500 mb-4">Task not found</p>
          <Link to={createPageUrl('Dashboard')}>
            <Button variant="outline" className="border-zinc-700 text-zinc-300">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Dashboard
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const isControlLoading = pauseMutation.isPending || resumeMutation.isPending ||
    deleteMutation.isPending || retryMutation.isPending;

  // Calculate total steps from plan
  const totalSteps = task.task_plan?.steps?.length || 1;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Background */}
      <div className="fixed inset-0 bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 -z-10" />

      {/* Header */}
      <header className="flex-shrink-0 border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-full px-4 sm:px-6 py-4">
          <div className="flex items-start sm:items-center justify-between gap-4 flex-col sm:flex-row">
            <div className="flex items-start gap-4">
              <Link to={createPageUrl('Dashboard')}>
                <Button variant="ghost" size="icon" className="text-zinc-400 hover:text-zinc-100">
                  <ArrowLeft className="w-5 h-5" />
                </Button>
              </Link>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-1">
                  <h1 className="text-lg font-semibold text-zinc-100 truncate">
                    {task.title || 'Untitled Task'}
                  </h1>
                  <StatusBadge status={task.status} size="sm" />
                </div>
                <div className="flex items-center gap-3 text-xs text-zinc-500">
                  {task.current_agent && (
                    <div className="flex items-center gap-1.5">
                      <AgentAvatar persona={task.current_agent} size="sm" isActive={isStreaming} />
                      <span className="capitalize">{task.current_agent.replace('_', ' ')}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{format(new Date(task.created_at), 'MMM d, h:mm a')}</span>
                  </div>
                  {/* Stream Status Indicator */}
                  {streamStatus === 'connected' && (
                    <span className="text-emerald-400">● Live</span>
                  )}
                  {streamStatus === 'reconnecting' && (
                    <span className="text-amber-400">● Reconnecting...</span>
                  )}
                </div>
              </div>
            </div>

            <TaskControls
              task={task}
              onPause={() => pauseMutation.mutate()}
              onResume={() => resumeMutation.mutate()}
              onDelete={() => deleteMutation.mutate()}
              onRetry={() => retryMutation.mutate()}
              isLoading={isControlLoading}
            />
          </div>

          {/* Progress */}
          <div className="mt-4">
            <ProgressBar
              currentStep={task.current_step || 0}
              totalSteps={totalSteps}
              status={task.status}
            />
          </div>

          {/* Error message */}
          {task.error_message && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20"
            >
              <p className="text-sm text-rose-400">{task.error_message}</p>
            </motion.div>
          )}
        </div>
      </header>

      {/* Main Content - War Room */}
      <main className="flex-1 flex flex-col lg:flex-row min-h-0">
        {/* Left Panel - Activity Stream (60%) */}
        <div className="lg:w-[60%] flex flex-col border-r border-zinc-800 h-[50vh] lg:h-auto">
          {/* CRITICAL: Merge REST logs (task.agent_logs) with SSE logs (agentLogs) */}
          {/* REST provides immediate display, SSE adds live updates */}
          <LiveStream
            logs={[
              ...(task?.agent_logs || []),
              ...agentLogs.filter(log => !task?.agent_logs?.some(tl => tl.id === log.id))
            ]}
            isStreaming={isStreaming}
          />
        </div>

        {/* Right Panel - Plan/Files (40%) */}
        <div className="lg:w-[40%] flex flex-col bg-zinc-900/30 min-h-0 flex-1">
          <div className="flex-shrink-0 border-b border-zinc-800">
            <Tabs value={rightPanel} onValueChange={setRightPanel} className="w-full">
              <TabsList className="w-full justify-start bg-transparent border-b-0 rounded-none h-auto p-0">
                <button
                  onClick={() => setRightPanel('plan')}
                  className={cn(
                    "rounded-none border-b-2 border-transparent px-4 py-3 text-sm font-medium flex items-center",
                    rightPanel === 'plan' ? "border-blue-500 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
                  )}
                >
                  <ListTree className="w-4 h-4 mr-2" />
                  Plan
                </button>
                <button
                  onClick={() => setRightPanel('files')}
                  className={cn(
                    "rounded-none border-b-2 border-transparent px-4 py-3 text-sm font-medium flex items-center",
                    rightPanel === 'files' ? "border-blue-500 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
                  )}
                >
                  <Folder className="w-4 h-4 mr-2" />
                  Files
                  {fileEvents.length > 0 && (
                    <span className="ml-2 px-1.5 py-0.5 text-xs bg-zinc-700 rounded-full">
                      {fileEvents.length}
                    </span>
                  )}
                </button>
              </TabsList>
            </Tabs>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {rightPanel === 'plan' ? (
              <TaskPlanView
                plan={activePlan}
                currentStep={currentStep}
              />
            ) : (
              <FileTree
                tree={fileTree || []}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
