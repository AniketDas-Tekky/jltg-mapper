/**
 * TypeScript mirror of `backend/app/schemas.py`.
 *
 * Event types, payload shapes, GameState and API DTOs are kept structurally in sync with
 * the Pydantic models so the client-side reducer (`reducer.ts`) produces the same derived
 * state the backend would. Only the bits the client needs are typed precisely; free-form
 * blobs (params, answers) stay `unknown`/`Record`.
 */

export const TOTAL_ZONES = 193;

export type EventType =
  | 'game_created'
  | 'player_joined'
  | 'role_assigned'
  | 'hiding_started'
  | 'question_asked'
  | 'question_answered'
  | 'zone_excluded'
  | 'zone_restored'
  | 'curse_logged'
  | 'note_added'
  | 'game_paused'
  | 'game_resumed'
  | 'round_ended'
  | 'role_rotated';

export type GameLifecycleStatus =
  | 'lobby'
  | 'hiding'
  | 'seeking'
  | 'paused'
  | 'ended';

export type Role = 'host' | 'seeker' | 'hider';

export type QuestionCategory = 'matching' | 'measuring' | 'radar' | 'thermometer';

export interface LatLon {
  lat: number;
  lon: number;
}

/** A persisted event as returned by the API / broadcast over WS. Mirrors `EventResponse`. */
export interface GameEvent {
  id?: string | null;
  game_id?: string | null;
  server_seq: number;
  client_event_id: string;
  player_id?: string | null;
  type: EventType | string;
  payload: Record<string, unknown>;
  created_at?: string | null;
}

export interface PlayerState {
  name?: string;
  role?: Role | string;
}

export interface QuestionRecord {
  question_id: string;
  category: QuestionCategory | string;
  subtype: string;
  seeker_location: LatLon;
  asked_by: string;
  params: Record<string, unknown>;
  answer: unknown;
}

export interface ScoreEntry {
  hider_id?: string | null;
  hider_name?: string | null;
  run_time_seconds: number;
}

export interface NoteRecord {
  text: string;
  author?: string | null;
}

export interface CurseRecord {
  curse: string;
  cast_by?: string | null;
  note?: string | null;
}

/** Reducer output. Mirrors `GameState`. */
export interface GameState {
  status: GameLifecycleStatus;
  last_seq: number;
  remaining_zone_ids: number[];
  remaining_area: Record<string, unknown> | null;
  timers: Record<string, unknown>;
  scoreboard: ScoreEntry[];
  players: Record<string, PlayerState>;
  questions: QuestionRecord[];
  notes: NoteRecord[];
  curses: CurseRecord[];
}

// --------------------------------------------------------------------------- API DTOs

export interface CreateGameResponse {
  game_id: string;
  join_code: string;
  player_id: string;
  token: string;
}

export interface JoinGameResponse {
  game_id: string;
  player_id: string;
  token: string;
  role: string;
}

export interface EventResponse extends GameEvent {
  id: string;
  game_id: string;
  player_id: string | null;
  created_at: string;
}

export interface StateResponse {
  game_id: string;
  last_seq: number;
  state: GameState;
}

/** WS frame shapes (see `backend/app/websocket.py`). */
export type WsFrame =
  | { kind: 'state'; game_id: string; last_seq: number; state: GameState }
  | { kind: 'event'; event: EventResponse }
  | { kind: 'ack'; duplicate: boolean; event: EventResponse }
  | { kind: 'error'; detail: string };
