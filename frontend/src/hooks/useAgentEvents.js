/**
 * useAgentEvents Hook
 *
 * Connects to the SSE stream for real-time agent log updates.
 * Implements Exponential Backoff Reconnection Logic.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE_URL = typeof window !== 'undefined' && import.meta?.env?.VITE_API_URL
  ? import.meta.env.VITE_API_URL
  : 'http://localhost:8000';

/**
 * Hook for subscribing to agent events via SSE.
 *
 * @param {string} taskId - The task ID to subscribe to.
 * @param {object} [options] - Optional callbacks.
 * @param {function} [options.onPlanReady] - Called when plan_ready event is received.
 * @param {function} [options.onStatusChange] - Called when status changes.
 * @param {function} [options.onFileVerified] - Called when file_verified event is received.
 * @returns {{ logs: Array, fileEvents: Array, status: string, taskPlan: object, taskStatus: string }}
 */
export function useAgentEvents(taskId, options) {
  const [logs, setLogs] = useState([]);
  const [fileEvents, setFileEvents] = useState([]);
  const [taskPlan, setTaskPlan] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [status, setStatus] = useState('idle'); // 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error'

  const onPlanReady = options?.onPlanReady;
  const onStatusChange = options?.onStatusChange;
  const onFileVerified = options?.onFileVerified;

  const processedLogIds = useRef(new Set());
  const processedFileEventIds = useRef(new Set());
  const retryCount = useRef(0);
  const reconnectTimeout = useRef(null);
  const maxRetries = 50;

  const connect = useCallback(() => {
    if (!taskId) return null;

    setStatus('connecting');
    const eventSource = new EventSource(`${API_BASE_URL}/api/stream/task/${taskId}`);

    eventSource.onopen = () => {
      console.log('[useAgentEvents] Connected to stream');
      setStatus('connected');
      retryCount.current = 0;
    };

    // Handle initial status event
    eventSource.addEventListener('status', (event) => {
      try {
        const data = JSON.parse(event.data);
        setTaskStatus(data.status);
        onStatusChange?.(data);
      } catch (err) {
        console.error('[useAgentEvents] Failed to parse status:', err);
      }
    });

    // Handle plan_ready event
    eventSource.addEventListener('plan_ready', (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[useAgentEvents] Plan ready:', data);
        setTaskPlan(data.task_plan);
        setTaskStatus(data.status);
        onPlanReady?.(data);
      } catch (err) {
        console.error('[useAgentEvents] Failed to parse plan_ready:', err);
      }
    });

    // Handle agent log events
    eventSource.addEventListener('agent_log', (event) => {
      try {
        const log = JSON.parse(event.data);
        console.log('[useAgentEvents] 🔴 Received agent_log:', log.ui_title, log.id);
        if (processedLogIds.current.has(log.id)) {
          console.log('[useAgentEvents] ⚠️ Duplicate log skipped:', log.id);
          return;
        }
        processedLogIds.current.add(log.id);
        setLogs((prev) => {
          console.log('[useAgentEvents] ✅ Updating logs state, new count:', prev.length + 1);
          return [...prev, log];
        });
      } catch (err) {
        console.error('[useAgentEvents] Failed to parse log:', err);
      }
    });

    // Handle verified file events - CRITICAL FOR FILE TREE SYNC
    eventSource.addEventListener('file_verified', (event) => {
      try {
        const fileData = JSON.parse(event.data);
        const eventKey = `${fileData.file_path}-${fileData.timestamp}`;

        if (processedFileEventIds.current.has(eventKey)) return;
        processedFileEventIds.current.add(eventKey);

        console.log('[useAgentEvents] File verified:', fileData.file_path);
        setFileEvents((prev) => [...prev, fileData]);

        // CALLBACK BRIDGE: Trigger FileTree refetch
        onFileVerified?.(fileData);
      } catch (err) {
        console.error('[useAgentEvents] Failed to parse file event:', err);
      }
    });

    // Handle stream completion
    eventSource.addEventListener('complete', () => {
      console.log('[useAgentEvents] Stream completed');
      eventSource.close();
    });

    // Handle errors with exponential backoff
    eventSource.onerror = () => {
      console.warn('[useAgentEvents] Connection error');
      eventSource.close();

      if (retryCount.current < maxRetries) {
        const delay = Math.min(1000 * Math.pow(1.5, retryCount.current), 10000);
        console.log(`[useAgentEvents] Reconnecting in ${delay}ms (attempt ${retryCount.current + 1})`);
        setStatus('reconnecting');
        retryCount.current++;
        reconnectTimeout.current = setTimeout(() => connect(), delay);
      } else {
        setStatus('error');
      }
    };

    return eventSource;
  }, [taskId, onPlanReady, onStatusChange, onFileVerified]);

  useEffect(() => {
    if (!taskId) {
      setStatus('idle');
      return;
    }

    // Reset state when taskId changes
    setLogs([]);
    setFileEvents([]);
    setTaskPlan(null);
    setTaskStatus(null);
    processedLogIds.current.clear();
    processedFileEventIds.current.clear();
    retryCount.current = 0;

    const eventSource = connect();

    return () => {
      if (eventSource) eventSource.close();
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    };
  }, [taskId, connect]);

  return { logs, fileEvents, taskPlan, taskStatus, status };
}
