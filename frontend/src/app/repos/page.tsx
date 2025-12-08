"use client";

import { useEffect, useState } from "react";
import { FolderGit2, Trash2, Search, Plus } from "lucide-react";
import { fetchRepositories } from "@/lib/api";
import { Repository } from "../../../types/schema";

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadRepos() {
      try {
        const data = await fetchRepositories();
        setRepos(data);
      } catch (error) {
        console.error("Failed to fetch repositories:", error);
      } finally {
        setLoading(false);
      }
    }
    loadRepos();
  }, []);

  return (
    <div className="container mx-auto p-8 space-y-8">
      <div className="flex justify-between items-center bg-slate-900/50 p-6 rounded-xl border border-slate-800 backdrop-blur-sm">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Repositories</h1>
          <p className="text-slate-400">Manage your connected codebases</p>
        </div>
        <button className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors">
          <Plus className="w-4 h-4" />
          Add Repository
        </button>
      </div>

      <div className="grid gap-4">
        {loading ? (
          <div className="text-center py-12 text-slate-500">Loading repositories...</div>
        ) : repos.length === 0 ? (
          <div className="text-center py-12 border border-dashed border-slate-800 rounded-xl bg-slate-900/20">
            <FolderGit2 className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-300">No repositories found</h3>
            <p className="text-slate-500 mt-2">
              Use the CLI to register a repository:
              <br />
              <code className="bg-slate-950 px-2 py-1 rounded text-sm text-cyan-400 mt-2 inline-block">gravity repo add /path/to/repo</code>
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {repos.map((repo) => (
              <div
                key={repo.id}
                className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors group relative"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                    <FolderGit2 className="w-6 h-6" />
                  </div>
                  <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button className="p-2 hover:bg-red-500/10 text-slate-500 hover:text-red-400 rounded-lg transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <h3 className="font-semibold text-lg text-slate-100 mb-1">{repo.name}</h3>
                <p className="text-xs font-mono text-slate-500 truncate mb-4">{repo.path}</p>

                <div className="flex items-center gap-3 pt-4 border-t border-slate-800 text-xs text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    Active
                  </span>
                  <span className="ml-auto font-mono">ID: {repo.id.substring(0, 8)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
