import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Folder, FolderOpen, FileCode, FileJson, FileText,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';

const fileIcons = {
  js: FileCode,
  jsx: FileCode,
  ts: FileCode,
  tsx: FileCode,
  py: FileCode,
  json: FileJson,
  md: FileText,
  txt: FileText,
  default: FileText
};

function FileNode({ node, depth = 0 }) {
  const [isOpen, setIsOpen] = useState(depth < 2);
  const isFolder = node.type === 'directory';
  const ext = node.name.split('.').pop()?.toLowerCase();
  const FileIcon = isFolder
    ? (isOpen ? FolderOpen : Folder)
    : (fileIcons[ext] || fileIcons.default);

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        className={cn(
          'group flex items-center gap-1.5 py-1 px-2 rounded-md cursor-pointer transition-colors',
          'hover:bg-zinc-800/50'
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={() => isFolder && setIsOpen(!isOpen)}
      >
        {isFolder && (
          <motion.div
            animate={{ rotate: isOpen ? 90 : 0 }}
            transition={{ duration: 0.15 }}
          >
            <ChevronRight className="w-3 h-3 text-zinc-500" />
          </motion.div>
        )}

        <FileIcon className={cn(
          'w-4 h-4 flex-shrink-0',
          isFolder ? 'text-amber-400' : 'text-zinc-400'
        )} />

        <span className="text-sm text-zinc-300 truncate flex-1">
          {node.name}
        </span>
      </motion.div>

      <AnimatePresence>
        {isFolder && isOpen && node.children && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
          >
            {node.children.map((child, idx) => (
              <FileNode
                key={child.path || idx}
                node={child}
                depth={depth + 1}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function FileTree({ tree = [] }) {
  if (tree.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-zinc-500">
        <Folder className="w-8 h-8 mb-2 text-zinc-600" />
        <p className="text-sm">No files yet</p>
      </div>
    );
  }

  return (
    <div className="py-2">
      {tree.map((node, idx) => (
        <FileNode
          key={node.path || idx}
          node={node}
        />
      ))}
    </div>
  );
}
