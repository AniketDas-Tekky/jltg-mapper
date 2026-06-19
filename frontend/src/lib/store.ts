/**
 * Global client state (Zustand).
 *
 * Holds the session identity (`gameId`/`playerId`/`token`/`role`/`joinCode`), the local
 * event log (`events`), the derived `state` (recomputed by the reducer whenever the log
 * changes), the live `connectionStatus`, and UI-only `selectedLayers` (which POI overlays
 * are toggled on the map).
 *
 * The session identity is persisted to localStorage so a refresh keeps you in the game.
 */

import { create } from 'zustand';
import { initialState, reduceEvents } from './reducer';
import type { GameEvent, GameState, Role } from './types';

export type ConnectionStatus = 'connecting' | 'online' | 'offline';

export interface Session {
  gameId: string;
  playerId: string;
  token: string;
  role: Role | string;
  joinCode?: string;
  name?: string;
}

const SESSION_KEY = 'jltg.session';

function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

function saveSession(s: Session | null): void {
  try {
    if (s) localStorage.setItem(SESSION_KEY, JSON.stringify(s));
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore quota / private-mode errors */
  }
}

export interface StoreState {
  session: Session | null;
  events: GameEvent[];
  state: GameState;
  connectionStatus: ConnectionStatus;
  selectedLayers: Record<string, boolean>;

  setSession: (s: Session | null) => void;
  /** Replace the full event log (e.g. from a server snapshot) and re-reduce. */
  setEvents: (events: GameEvent[]) => void;
  /** Merge new events into the log (idempotent on client_event_id) and re-reduce. */
  mergeEvents: (incoming: GameEvent[]) => void;
  setConnectionStatus: (s: ConnectionStatus) => void;
  toggleLayer: (id: string) => void;
  reset: () => void;
}

export const useStore = create<StoreState>((set, get) => ({
  session: loadSession(),
  events: [],
  state: initialState(),
  connectionStatus: 'connecting',
  selectedLayers: {},

  setSession: (s) => {
    saveSession(s);
    set({ session: s });
  },

  setEvents: (events) => {
    const deduped = dedupe(events);
    set({ events: deduped, state: reduceEvents(deduped) });
  },

  mergeEvents: (incoming) => {
    const merged = dedupe([...get().events, ...incoming]);
    set({ events: merged, state: reduceEvents(merged) });
  },

  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),

  toggleLayer: (id) =>
    set((st) => ({ selectedLayers: { ...st.selectedLayers, [id]: !st.selectedLayers[id] } })),

  reset: () => {
    saveSession(null);
    set({ session: null, events: [], state: initialState(), selectedLayers: {} });
  },
}));

/** De-duplicate by client_event_id, keeping the entry with the highest server_seq, sorted. */
function dedupe(events: GameEvent[]): GameEvent[] {
  const byId = new Map<string, GameEvent>();
  for (const e of events) {
    const prev = byId.get(e.client_event_id);
    if (!prev || (e.server_seq ?? 0) >= (prev.server_seq ?? 0)) {
      byId.set(e.client_event_id, e);
    }
  }
  return [...byId.values()].sort((a, b) => (a.server_seq ?? 0) - (b.server_seq ?? 0));
}
