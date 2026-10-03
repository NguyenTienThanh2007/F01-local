'use client';
import { useEffect, useRef, useState } from 'react';
import { projectRequest, ProjectAPIError } from '@/lib/projects/browser';
import type { Events, Snapshot } from '@/lib/workspace/contracts';
import { acceptEvents, eventRecord, reconnectDelay, type BuildEvent, type TraceState } from '@/lib/workspace/trace';
export type Transport = 'connecting' | 'live' | 'polling' | 'offline' | 'session expired' | 'access unavailable';
export function useBuildFeed(id: string, snapshot: Snapshot | null, changed: (events: BuildEvent[]) => void) {
  const [events, setEvents] = useState<BuildEvent[]>([]), [transport, setTransport] = useState<Transport>('connecting'), [historyReady,setHistoryReady] = useState(false), [connectionAttempt,setConnectionAttempt] = useState(0);
  const changedRef = useRef(changed); changedRef.current = changed;
  const cached = useRef<{ id: string; state: TraceState; historyReady: boolean } | null>(null);
  const ready = snapshot !== null;
  useEffect(() => {
    if (!snapshot) return;
    setTransport('connecting');
    let disposed = false, halted = false, source: EventSource | null = null;
    let reconnect: ReturnType<typeof setTimeout> | undefined, polling: ReturnType<typeof setInterval> | undefined, attempt = 0;
    const previous = cached.current?.id === id ? cached.current : null;
    let state: TraceState = previous?.state ?? { sequence: snapshot.last_sequence, events: snapshot.recent_events, pending: [] };
    let queue: Promise<void> = Promise.resolve(), historyLoaded = previous?.historyReady ?? false;
    setHistoryReady(historyLoaded);
    const controller = new AbortController();
    setEvents(state.events);
    function stop() { source?.close(); source = null; clearTimeout(reconnect); clearInterval(polling); polling = undefined; }
    function access(error: unknown) {
      if (error instanceof ProjectAPIError && (error.status === 401 || error.status === 404)) {
        halted = true; stop(); setTransport(error.status === 401 ? 'session expired' : 'access unavailable'); return true;
      }
      return false;
    }
    async function page(after: number) {
      const value = await projectRequest<Events>(`/projects/${id}/events?after_sequence=${after}`, { signal: controller.signal });
      if (!Array.isArray(value.items) || !value.items.every(e => eventRecord(e,id))) throw new Error('Invalid event response');
      return value;
    }
    function commit(incoming: BuildEvent[]) {
      const result = acceptEvents(state, incoming); state = result.state;
      if (!disposed) cached.current = { id, state, historyReady: historyLoaded };
      if (!disposed && result.applied.length) { setEvents(state.events); changedRef.current(result.applied); }
      return result;
    }
    async function recover(incoming: BuildEvent[] = []) {
      let result = commit(incoming);
      while (!disposed && !halted) {
        const previous = state.sequence, value = await page(state.sequence);
        result = commit(value.items);
        if (result.gap && previous === state.sequence) throw new Error('Sequence gap unresolved');
        if (!value.next_cursor && !result.gap) return;
      }
    }
    function enqueue(job: () => Promise<void>) {
      queue = queue.then(async () => { if (!disposed && !halted) await job(); }).catch(error => {
        if (!disposed && !access(error)) fallback();
      });
    }
    function fallback() {
      if (disposed || halted) return;
      source?.close(); source = null; setTransport('polling');
      if (!polling) {
        const poll = () => enqueue(async () => { try { if (!historyLoaded) await backfill(); await recover(); if (!source) setTransport('polling'); } catch (error) { if (!access(error)) setTransport('offline'); } });
        polling = setInterval(poll, 3000); poll();
      }
      if (typeof EventSource !== 'undefined' && !reconnect) reconnect = setTimeout(() => { reconnect = undefined; connect(); }, reconnectDelay(attempt++));
    }
    function connect() {
      if (disposed || halted) return;
      if (typeof EventSource === 'undefined') { fallback(); return; }
      source?.close();
      const stream = new EventSource(`/api/v1/projects/${id}/events/stream?after_sequence=${state.sequence}`); source = stream;
      stream.onopen = () => { if (disposed || source !== stream) return; attempt = 0; clearInterval(polling); polling = undefined; setTransport('live'); if (!historyLoaded) enqueue(backfill); };
      stream.addEventListener('build_event', event => {
        if (disposed || source !== stream) return;
        enqueue(async () => {
          const parsed: unknown = JSON.parse((event as MessageEvent).data);
          if (!eventRecord(parsed,id)) throw new Error('Invalid stream event');
          const result = commit([parsed]); if (result.gap) await recover();
        });
      });
      for (const [name,status] of [['session_expired','session expired'],['access_revoked','access unavailable']] as const) stream.addEventListener(name, () => { halted = true; stop(); setTransport(status); });
      stream.onerror = () => { if (source === stream) fallback(); };
    }
    async function backfill() {
      const boundary = state.sequence;
      let after = 0; const history: BuildEvent[] = [];
      for (;;) {
        const value = await page(after);
        history.push(...value.items.filter(e => e.sequence <= boundary));
        const last = value.items.at(-1)?.sequence ?? after;
        if (!value.next_cursor || last >= boundary) break;
        if (last <= after) throw new Error('Invalid history cursor');
        after = last;
      }
      if (history.length !== boundary || history.some((event,index) => event.sequence !== index + 1)) throw new Error('Incomplete event history');
      if (!disposed) { state.events = history; historyLoaded = true; cached.current = { id, state, historyReady: true }; setHistoryReady(true); setEvents(history); }
    }
    // The snapshot high-water sequence stays the subscription boundary during backfill.
    enqueue(async () => { if (!historyLoaded) await backfill(); else await recover(); connect(); });
    return () => { disposed = true; controller.abort(); stop(); };
  // A new snapshot refreshes projections, not the transport or its replay cursor.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, ready, connectionAttempt]);
  return { events, transport, historyReady, retry: () => setConnectionAttempt(value => value + 1) };
}
