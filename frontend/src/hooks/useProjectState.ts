/**
 * useProjectState.ts
 * "The Wiring" for the Glass Cockpit.
 *
 * Main Responsibility:
 * Maintain a "Truth-First" local store of the Backend DAG.
 * Subscribes to /api/dashboard/{id}/stream via WebSocket.
 *
 * Logic:
 * 1. Initial Load: Fetch /api/dashboard/{id}/state
 * 2. Subscription: Connect WS.
 * 3. On Message: Patch the local state.
 */

import { useState, useEffect, useRef } from 'react';

// Types (should match Backend Pydantic)
export interface DAGNode {
  id: string;
  title: string | null;
  status: 'PENDING' | 'PLANNING' | 'PLAN_REVIEW' | 'REVIEW_REQUIRED' | 'EXECUTING' | 'TESTING' | 'DOCUMENTING' | 'COMPLETED' | 'FAILED' | 'PAUSED';
  retry_count: number;
  agent: string | null;
}

export interface DAGEdge {
  blocker: string; // UUID
  blocked: string; // UUID
}

export interface ProjectState {
  tasks: DAGNode[];
  edges: DAGEdge[];
  lastUpdated: string | null;
  isConnected: boolean;
}

export function useProjectState(rootTaskId: string) {
  const [state, setState] = useState<ProjectState>({
    tasks: [],
    edges: [],
    lastUpdated: null,
    isConnected: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!rootTaskId) return;

    // 1. Initial Fetch (Snapshot)
    const fetchSnapshot = async () => {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/dashboard/${rootTaskId}/state`);
        if (res.ok) {
          const snapshot = await res.json();
          setState(prev => ({
            ...prev,
            tasks: snapshot.tasks,
            edges: snapshot.edges,
            lastUpdated: snapshot.updated_at
          }));
        }
      } catch (err) {
        console.error("Failed to fetch initial state", err);
      }
    };

    fetchSnapshot();

    // 2. WebSocket Connection
    const connect = () => {
      const wsUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/^http/, 'ws') + `/api/dashboard/${rootTaskId}/stream`;

      // Close existing
      if (wsRef.current) {
        wsRef.current.close();
      }

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("Glass Cockpit Connected");
        setState(prev => ({ ...prev, isConnected: true }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "STATE_UPDATE") {
            // Replace state (Truth-First)
            // We trust the backend's "Snapshot" in the event data
            setState(prev => ({
              ...prev,
              tasks: msg.data.tasks,
              edges: msg.data.edges,
              lastUpdated: msg.data.timestamp
            }));
          }
        } catch (err) {
          console.error("WS Parse Error", err);
        }
      };

      ws.onclose = () => {
        console.log("Glass Cockpit Disconnected");
        setState(prev => ({ ...prev, isConnected: false }));
        // Reconnect logic
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error("WS Error", err);
        setState(prev => ({ ...prev, isConnected: false }));
        ws.close();
      };
    };

    connect();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };

  }, [rootTaskId]);

  return state;
}
