import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Send, Loader2, FolderGit2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from '@/lib/utils';

export default function NewTaskModal({
  open,
  onOpenChange,
  onSubmit,
  isLoading = false,
  repositories = []  // Array of { id, name, path } from backend
}) {
  const [title, setTitle] = useState('');
  const [request, setRequest] = useState('');
  const [repoId, setRepoId] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!request.trim() || !repoId) return;

    onSubmit({
      title: title.trim() || undefined,
      user_request: request.trim(),
      repo_id: repoId
    });
  };

  const handleClose = () => {
    setTitle('');
    setRequest('');
    setRepoId('');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-zinc-900 border-zinc-800 max-w-xl">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            Create New Task
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          {/* Repository Selector (REQUIRED) */}
          <div>
            <label className="block text-xs font-medium text-zinc-500 mb-1.5">
              Target Repository *
            </label>
            <Select value={repoId} onValueChange={setRepoId} disabled={isLoading}>
              <SelectTrigger className="bg-zinc-800/50 border-zinc-700 text-zinc-100">
                <SelectValue placeholder="Select a repository..." />
              </SelectTrigger>
              <SelectContent className="bg-zinc-800 border-zinc-700">
                {repositories.length === 0 ? (
                  <div className="px-3 py-2 text-sm text-zinc-500">
                    No repositories found. Add one first.
                  </div>
                ) : (
                  repositories.map((repo) => (
                    <SelectItem
                      key={repo.id}
                      value={repo.id}
                      className="text-zinc-100 focus:bg-zinc-700"
                    >
                      <div className="flex items-center gap-2">
                        <FolderGit2 className="w-4 h-4 text-blue-400" />
                        <span>{repo.name}</span>
                        <span className="text-xs text-zinc-500 ml-2 font-mono truncate max-w-[200px]">
                          {repo.path}
                        </span>
                      </div>
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
            {repositories.length === 0 && (
              <p className="text-xs text-amber-400 mt-1.5">
                No repositories configured. Add a repo to get started.
              </p>
            )}
          </div>

          {/* Title (optional) */}
          <div>
            <label className="block text-xs font-medium text-zinc-500 mb-1.5">
              Title (optional)
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Give your task a memorable name..."
              className="bg-zinc-800/50 border-zinc-700 text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600"
              disabled={isLoading}
            />
          </div>

          {/* Request */}
          <div>
            <label className="block text-xs font-medium text-zinc-500 mb-1.5">
              What do you want to build? *
            </label>
            <Textarea
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              placeholder="Describe your task in detail. The more specific you are, the better the results..."
              className={cn(
                "min-h-[120px] bg-zinc-800/50 border-zinc-700 text-zinc-100",
                "placeholder:text-zinc-600 focus:border-zinc-600 resize-none"
              )}
              disabled={isLoading}
            />
            <p className="text-xs text-zinc-600 mt-1.5">
              Be specific about the functionality, tech stack, and any constraints.
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isLoading}
              className="border-zinc-700 text-zinc-400 hover:bg-zinc-800"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!request.trim() || !repoId || isLoading}
              className={cn(
                "bg-gradient-to-r from-blue-600 to-cyan-600 text-white",
                "hover:from-blue-500 hover:to-cyan-500",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-1.5" />
                  Create Task
                </>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
