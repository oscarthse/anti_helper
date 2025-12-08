import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Loader2, Cpu, Activity, CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import TaskCard from '@/components/anti-helper/TaskCard';
import NewTaskModal from '@/components/anti-helper/NewTaskModal';

// New Antigravity Imports
import { fetchTasks, createTask, fetchRepositories } from '@/api/antigravityClient';

export default function Dashboard() {
  const [filter, setFilter] = useState('all');
  const [showNewTask, setShowNewTask] = useState(false);
  const queryClient = useQueryClient();

  // Fetch all tasks from our FastAPI backend
  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => fetchTasks(),
    refetchOnWindowFocus: false,
  });

  // Fetch repositories for the New Task Modal
  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: () => fetchRepositories(),
  });

  const createTaskMutation = useMutation({
    mutationFn: (data) => createTask(data.repo_id, data.user_request),
    onSuccess: () => {
      console.log('[Dashboard] Task created successfully');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setShowNewTask(false);
    },
    onError: (error) => {
      console.error('[Dashboard] Failed to create task:', error);
      alert(`Failed to create task: ${error.message}`);
    },
  });

  const filteredTasks = tasks.filter(task => {
    if (filter === 'all') return true;
    if (filter === 'active') return ['planning', 'executing', 'testing', 'documenting', 'plan_review'].includes(task.status);
    if (filter === 'completed') return task.status === 'completed';
    if (filter === 'failed') return task.status === 'failed';
    return true;
  });

  const stats = {
    total: tasks.length,
    active: tasks.filter(t => ['planning', 'executing', 'testing', 'documenting'].includes(t.status)).length,
    completed: tasks.filter(t => t.status === 'completed').length,
    failed: tasks.filter(t => t.status === 'failed').length,
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 -z-10" />
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-500/5 via-transparent to-transparent -z-10" />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-zinc-100 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-white" />
              </div>
              Anti-Helper
            </h1>
            <p className="text-zinc-500 mt-1">Autonomous AI Development Platform</p>
          </div>

          <Button
            onClick={() => setShowNewTask(true)}
            className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white shadow-lg shadow-blue-500/20"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Task
          </Button>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8"
        >
          {[
            { label: 'Total Tasks', value: stats.total, icon: Cpu, color: 'text-zinc-400' },
            { label: 'Active', value: stats.active, icon: Activity, color: 'text-blue-400' },
            { label: 'Completed', value: stats.completed, icon: CheckCircle2, color: 'text-emerald-400' },
            { label: 'Failed', value: stats.failed, icon: XCircle, color: 'text-rose-400' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className={`w-4 h-4 ${stat.color}`} />
                <span className="text-xs text-zinc-500">{stat.label}</span>
              </div>
              <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            </div>
          ))}
        </motion.div>

        {/* Filters */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="mb-6"
        >
          <Tabs value={filter} onValueChange={setFilter}>
            <TabsList className="bg-zinc-900/50 border border-zinc-800">
              <TabsTrigger value="all" className="data-[state=active]:bg-zinc-800">All</TabsTrigger>
              <TabsTrigger value="active" className="data-[state=active]:bg-zinc-800">Active</TabsTrigger>
              <TabsTrigger value="completed" className="data-[state=active]:bg-zinc-800">Completed</TabsTrigger>
              <TabsTrigger value="failed" className="data-[state=active]:bg-zinc-800">Failed</TabsTrigger>
            </TabsList>
          </Tabs>
        </motion.div>

        {/* Task Grid */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-zinc-600 mb-3" />
            <p className="text-zinc-500">Loading tasks...</p>
          </div>
        ) : filteredTasks.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center py-20 rounded-xl border border-zinc-800 border-dashed bg-zinc-900/20"
          >
            <Cpu className="w-12 h-12 text-zinc-700 mb-4" />
            <h3 className="text-lg font-medium text-zinc-400 mb-1">No tasks found</h3>
            <p className="text-sm text-zinc-600 mb-4">
              {filter === 'all' ? 'Create your first task to get started' : `No ${filter} tasks`}
            </p>
            {filter === 'all' && (
              <Button
                onClick={() => setShowNewTask(true)}
                variant="outline"
                className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
              >
                <Plus className="w-4 h-4 mr-1.5" />
                Create Task
              </Button>
            )}
          </motion.div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredTasks.map((task, idx) => (
              <TaskCard key={task.id} task={task} index={idx} />
            ))}
          </div>
        )}
      </div>

      {/* New Task Modal */}
      <NewTaskModal
        open={showNewTask}
        onOpenChange={setShowNewTask}
        onSubmit={(data) => createTaskMutation.mutate(data)}
        isLoading={createTaskMutation.isPending}
        repositories={repos}
      />
    </div>
  );
}
