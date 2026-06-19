/**
 * Realtime sync client.
 *
 * Responsibilities:
 *  1. Hold a WebSocket to `/ws/{game_id}?token=` and stay connected (auto-reconnect with
 *     backoff). On connect the server sends a `{kind:'state'}` snapshot; thereafter every
 *     appended event arrives as `{kind:'event', event}`.
 *  2. Persist every confirmed event to Dexie (`events`) and mirror it into the Zustand store.
 *  3. Emitting events: try the live socket; if offline, queue into the Dexie `outbox`.
 *  4. On (re)connect: flush the outbox over REST (idempotent on `client_event_id`, 409 == ok)
 *     and run a catch-up `GET /events?since_seq=last_seq`, then re-reduce.
 *
 * The client uses `import.meta.url`-independent relative URLs so the Vite dev proxy and a
 * same-origin production deploy both work.
 */

import {
  clearOutboxItem,
  lastSeq,
  loadEvents,
  loadOutbox,
  putEvent,
  queueOutbox,
  type StoredEvent,
} from './db';
import { getEvents, getState, postEvent } from './api';
import { useStore } from './store';
import type { EventResponse, WsFrame } from './types';

/**
 * Events whose effect on the surviving-zone set is computed server-side (Shapely
 * deduction for answers; manual overrides; round resets). After ingesting one we
 * re-pull the authoritative `remaining_zone_ids` from `GET /state`.
 */
const ZONE_EVENTS = new Set([
  'question_answered',
  'zone_excluded',
  'zone_restored',
  'round_ended',
  'role_rotated',
  'game_created',
]);

function wsUrl(gameId: string, token: string): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws/${gameId}?token=${encodeURIComponent(token)}`;
}

export interface SyncHandle {
  /** Submit an event. Returns once it's either sent or queued to the outbox. */
  send(type: string, payload: Record<string, unknown>): Promise<void>;
  close(): void;
}

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  // Fallback (older browsers): RFC4122-ish.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Persist a confirmed event to Dexie + the store, and drop any matching outbox entry. */
async function ingest(gameId: string, token: string, ev: EventResponse): Promise<void> {
  const stored: StoredEvent = { ...ev, game_id: gameId };
  await putEvent(stored);
  await clearOutboxItem(ev.client_event_id);
  useStore.getState().mergeEvents([stored]);
  // The browser can't run the deduction geometry; for events whose zone effect is
  // server-computed, pull the authoritative surviving set and overlay it.
  if (ZONE_EVENTS.has(ev.type)) {
    try {
      const snap = await getState(gameId, token);
      useStore.getState().applyServerZones(snap.state.remaining_zone_ids);
    } catch {
      /* offline — the next reconnect/state snapshot will reconcile */
    }
  }
}

export function startSync(gameId: string, token: string): SyncHandle {
  let socket: WebSocket | null = null;
  let closed = false;
  let backoff = 500;

  const setStatus = useStore.getState().setConnectionStatus;

  async function hydrateFromDexie(): Promise<void> {
    const stored = await loadEvents(gameId);
    if (stored.length) useStore.getState().setEvents(stored);
  }

  async function flushOutbox(): Promise<void> {
    const pending = await loadOutbox(gameId);
    for (const item of pending) {
      try {
        const ev = await postEvent(
          gameId,
          {
            client_event_id: item.client_event_id,
            type: item.type,
            payload: item.payload,
          },
          token,
        );
        await ingest(gameId, token, ev);
      } catch (err) {
        // 409 == already applied: the catch-up GET will pull it in; drop from outbox.
        const status = (err as { status?: number }).status;
        if (status === 409) {
          await clearOutboxItem(item.client_event_id);
        }
        // Other errors: leave it queued, retry on next connect.
      }
    }
  }

  async function catchUp(): Promise<void> {
    const since = await lastSeq(gameId);
    try {
      const events = await getEvents(gameId, since, token);
      for (const ev of events) await ingest(gameId, token, ev);
    } catch {
      /* offline — the WS snapshot or next reconnect will reconcile */
    }
  }

  function connect(): void {
    if (closed) return;
    setStatus('connecting');
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl(gameId, token));
    } catch {
      scheduleReconnect();
      return;
    }
    socket = ws;

    ws.onopen = async () => {
      backoff = 500;
      setStatus('online');
      // Reconcile: push anything queued while offline, then pull anything we missed.
      await flushOutbox();
      await catchUp();
    };

    ws.onmessage = async (msg) => {
      let frame: WsFrame;
      try {
        frame = JSON.parse(msg.data as string) as WsFrame;
      } catch {
        return;
      }
      if (frame.kind === 'event' || frame.kind === 'ack') {
        await ingest(gameId, token, frame.event);
      } else if (frame.kind === 'state') {
        // Snapshot of derived state; our log is the source of truth, so pull missing events.
        await catchUp();
      }
    };

    ws.onclose = () => {
      if (socket === ws) socket = null;
      if (!closed) {
        setStatus('offline');
        scheduleReconnect();
      }
    };

    ws.onerror = () => {
      try {
        ws.close();
      } catch {
        /* noop */
      }
    };
  }

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  function scheduleReconnect(): void {
    if (closed || reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, backoff);
    backoff = Math.min(backoff * 2, 10_000);
  }

  // Boot: load persisted log, then connect.
  void hydrateFromDexie().then(connect);

  // React to browser connectivity changes for snappier reconnects.
  const onOnline = () => {
    if (!socket || socket.readyState > WebSocket.OPEN) connect();
  };
  window.addEventListener('online', onOnline);

  return {
    async send(type, payload) {
      const clientEventId = uuid();
      const created_at = new Date().toISOString();
      // Always queue first so a crash mid-send doesn't lose the event.
      await queueOutbox({ client_event_id: clientEventId, game_id: gameId, type, payload, created_at });

      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ client_event_id: clientEventId, type, payload }));
        return;
      }
      // Offline: try REST opportunistically, else leave it queued for the next flush.
      try {
        const ev = await postEvent(gameId, { client_event_id: clientEventId, type, payload }, token);
        await ingest(gameId, token, ev);
      } catch {
        /* stays in outbox; flushed on reconnect */
      }
    },
    close() {
      closed = true;
      window.removeEventListener('online', onOnline);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) {
        try {
          socket.close();
        } catch {
          /* noop */
        }
      }
      setStatus('offline');
    },
  };
}

export { uuid };
