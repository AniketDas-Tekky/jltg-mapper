/**
 * IndexedDB persistence via Dexie.
 *
 * Two stores:
 *  - `events`  — the local copy of the authoritative event log (everything we've seen from
 *                the server, keyed by `client_event_id`, indexed by `server_seq`).
 *  - `outbox`  — events we created locally that have NOT yet been confirmed by the server
 *                (queued while offline / in-flight). They are flushed on (re)connect; once
 *                the server echoes them back (matched by `client_event_id`) they're removed.
 *
 * Both are scoped by `game_id` so multiple games can coexist in one browser profile.
 */

import Dexie, { type Table } from 'dexie';
import type { GameEvent } from './types';

/** A server-confirmed event, mirroring {@link GameEvent} but always with a `server_seq`. */
export interface StoredEvent extends GameEvent {
  game_id: string;
  server_seq: number;
}

/** A locally-created event awaiting server confirmation. */
export interface OutboxEvent {
  client_event_id: string;
  game_id: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export class GameDB extends Dexie {
  events!: Table<StoredEvent, string>;
  outbox!: Table<OutboxEvent, string>;

  constructor() {
    super('jltg-mapper');
    this.version(1).stores({
      // primary key: client_event_id; secondary indices for range queries.
      events: 'client_event_id, game_id, server_seq, [game_id+server_seq]',
      outbox: 'client_event_id, game_id',
    });
  }
}

export const db = new GameDB();

/** Upsert a confirmed event into the local log (idempotent on `client_event_id`). */
export async function putEvent(ev: StoredEvent): Promise<void> {
  await db.events.put(ev);
}

/** Load all stored events for a game, ordered by `server_seq`. */
export async function loadEvents(gameId: string): Promise<StoredEvent[]> {
  return db.events
    .where('[game_id+server_seq]')
    .between([gameId, Dexie.minKey], [gameId, Dexie.maxKey])
    .toArray();
}

/** Highest `server_seq` we've persisted for a game (0 if none). */
export async function lastSeq(gameId: string): Promise<number> {
  const last = await db.events
    .where('[game_id+server_seq]')
    .between([gameId, Dexie.minKey], [gameId, Dexie.maxKey])
    .last();
  return last?.server_seq ?? 0;
}

export async function queueOutbox(ev: OutboxEvent): Promise<void> {
  await db.outbox.put(ev);
}

export async function loadOutbox(gameId: string): Promise<OutboxEvent[]> {
  return db.outbox.where('game_id').equals(gameId).toArray();
}

export async function clearOutboxItem(clientEventId: string): Promise<void> {
  await db.outbox.delete(clientEventId);
}
