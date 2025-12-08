import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Radio } from 'lucide-react';
import { cn } from '@/lib/utils';
import LogEntry from './LogEntry';

export default function LiveStream({ logs = [], isStreaming = false }) {
  const containerRef = useRef(null);
  const shouldAutoScroll = useRef(true);
  
  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (shouldAutoScroll.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);
  
  // Handle scroll to detect if user has scrolled up
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    shouldAutoScroll.current = scrollHeight - scrollTop - clientHeight < 100;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 flex-shrink-0">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-zinc-300">Activity Stream</h3>
          {isStreaming && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20"
            >
              <motion.div
                className="w-1.5 h-1.5 rounded-full bg-blue-400"
                animate={{ opacity: [1, 0.4, 1] }}
                transition={{ repeat: Infinity, duration: 1 }}
              />
              <span className="text-xs font-medium text-blue-400">Live</span>
            </motion.div>
          )}
        </div>
        <span className="text-xs text-zinc-500 font-mono">
          {logs.length} events
        </span>
      </div>
      
      {/* Stream content */}
      <div 
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent"
      >
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500">
            {isStreaming ? (
              <>
                <Loader2 className="w-8 h-8 animate-spin mb-3 text-zinc-600" />
                <p className="text-sm">Waiting for agent activity...</p>
              </>
            ) : (
              <>
                <Radio className="w-8 h-8 mb-3 text-zinc-600" />
                <p className="text-sm">No activity yet</p>
              </>
            )}
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            {logs.map((log, idx) => (
              <LogEntry 
                key={log.id || idx} 
                log={log} 
                isLatest={idx === logs.length - 1 && isStreaming}
              />
            ))}
          </AnimatePresence>
        )}
        
        {/* Typing indicator */}
        {isStreaming && logs.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2 px-4 py-2"
          >
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-zinc-500"
                  animate={{ y: [0, -4, 0] }}
                  transition={{
                    repeat: Infinity,
                    duration: 0.6,
                    delay: i * 0.1
                  }}
                />
              ))}
            </div>
            <span className="text-xs text-zinc-500">Agent working...</span>
          </motion.div>
        )}
      </div>
    </div>
  );
}