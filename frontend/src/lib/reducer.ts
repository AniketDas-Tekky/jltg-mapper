/**
 * Client-side event reducer — a faithful TypeScript port of `backend/app/reducer.py`.
 *
 * `reduceEvents(events)` folds an ordered list of {@link GameEvent} into a {@link GameState}.
 * Pure & deterministic: no I/O, no clock reads, input not mutated. Events are sorted by
 * `server_seq` defensively. Unknown event types and malformed payloads are skipped so the
 * log stays forward-compatible — same semantics as the backend.
 *
 * DEDUCTION SEAM: zone elimination on `question_answered` is SERVER-AUTHORITATIVE for now.
 * The backend runs the real Shapely deduction engine; the client only learns the surviving
 * zones via the periodic state snapshots / `remaining_zone_ids` it receives. So here the
 * client treats `question_answered` as a no-op for zone elimination (it still records the
 * answer on the question). A full client-side geometry port is intentionally out of scope.
 */

import {
  TOTAL_ZONES,
  type CurseRecord,
  type GameEvent,
  type GameLifecycleStatus,
  type GameState,
  type NoteRecord,
  type QuestionRecord,
  type ScoreEntry,
} from './types';

function asString(v: unknown): string | null {
  return v == null ? null : String(v);
}

function range(n: number): number[] {
  return Array.from({ length: n }, (_, i) => i);
}

class StateBuilder {
  status: GameLifecycleStatus = 'lobby';
  last_seq = 0;
  remaining: Set<number> = new Set();
  remaining_area: Record<string, unknown> | null = null;
  timers: Record<string, unknown> = {};
  scoreboard: ScoreEntry[] = [];
  players: Record<string, { name?: string; role?: string }> = {};
  questions: QuestionRecord[] = [];
  notes: NoteRecord[] = [];
  curses: CurseRecord[] = [];
  private questionsById: Record<string, QuestionRecord> = {};

  apply(event: GameEvent): void {
    this.last_seq = Math.max(this.last_seq, event.server_seq);
    const p = event.payload || {};
    switch (event.type) {
      case 'game_created': {
        const total = (typeof p.total_zones === 'number' && p.total_zones) || TOTAL_ZONES;
        this.remaining = new Set(range(total));
        this.status = 'lobby';
        break;
      }
      case 'player_joined': {
        const id = asString(p.player_id);
        if (id) this.players[id] = { name: p.name as string, role: p.role as string };
        break;
      }
      case 'role_assigned': {
        const id = asString(p.player_id);
        if (id) {
          this.players[id] = { ...(this.players[id] ?? {}), role: p.role as string };
        }
        break;
      }
      case 'hiding_started': {
        this.status = 'hiding';
        this.timers.hiding_started_at = p.started_at;
        this.timers.hiding_duration_seconds = p.hiding_duration_seconds ?? 3600;
        break;
      }
      case 'question_asked': {
        if (this.status === 'hiding') this.status = 'seeking';
        const loc = (p.seeker_location ?? {}) as { lat?: number; lon?: number };
        const record: QuestionRecord = {
          question_id: String(p.question_id),
          category: p.category as string,
          subtype: p.subtype as string,
          seeker_location: { lat: loc.lat ?? 0, lon: loc.lon ?? 0 },
          asked_by: String(p.asked_by),
          params: (p.params as Record<string, unknown>) ?? {},
          answer: null,
        };
        this.questions.push(record);
        this.questionsById[record.question_id] = record;
        break;
      }
      case 'question_answered': {
        const record = this.questionsById[String(p.question_id)];
        if (record) {
          record.answer = p.answer ?? null;
          // Zone elimination is server-authoritative (see module docstring): no-op here.
        }
        break;
      }
      case 'zone_excluded': {
        if (typeof p.zone_id === 'number') this.remaining.delete(p.zone_id);
        break;
      }
      case 'zone_restored': {
        if (typeof p.zone_id === 'number') this.remaining.add(p.zone_id);
        break;
      }
      case 'curse_logged': {
        this.curses.push({
          curse: p.curse as string,
          cast_by: asString(p.cast_by),
          note: (p.note as string) ?? null,
        });
        break;
      }
      case 'note_added': {
        this.notes.push({ text: p.text as string, author: asString(p.author) });
        break;
      }
      case 'game_paused': {
        if (this.status !== 'ended') {
          this.timers.paused_at = p.paused_at;
          this.timers._status_before_pause = this.status;
          this.status = 'paused';
        }
        break;
      }
      case 'game_resumed': {
        if (this.status === 'paused') {
          const prev = (this.timers._status_before_pause as GameLifecycleStatus) ?? 'seeking';
          this.status = prev;
          this.timers.resumed_at = p.resumed_at;
          delete this.timers._status_before_pause;
          delete this.timers.paused_at;
        }
        break;
      }
      case 'round_ended': {
        this.status = 'ended';
        this.scoreboard.push({
          hider_id: asString(p.hider_id),
          hider_name: (p.hider_name as string) ?? null,
          run_time_seconds: (p.run_time_seconds as number) ?? 0,
        });
        this.scoreboard.sort((a, b) => b.run_time_seconds - a.run_time_seconds);
        break;
      }
      case 'role_rotated': {
        const assignments = (p.assignments as Record<string, string>) ?? {};
        for (const [pid, role] of Object.entries(assignments)) {
          this.players[pid] = { ...(this.players[pid] ?? {}), role };
        }
        this.remaining = new Set(range(TOTAL_ZONES));
        this.remaining_area = null;
        this.status = 'lobby';
        break;
      }
      default:
        // unknown event type -> no-op
        break;
    }
  }

  build(): GameState {
    return {
      status: this.status,
      last_seq: this.last_seq,
      remaining_zone_ids: Array.from(this.remaining).sort((a, b) => a - b),
      remaining_area: this.remaining_area,
      timers: { ...this.timers },
      scoreboard: [...this.scoreboard],
      players: { ...this.players },
      questions: [...this.questions],
      notes: [...this.notes],
      curses: [...this.curses],
    };
  }
}

/** Fold `events` (any order) into a {@link GameState}. Pure and deterministic. */
export function reduceEvents(events: GameEvent[]): GameState {
  const builder = new StateBuilder();
  const ordered = [...events].sort((a, b) => a.server_seq - b.server_seq);
  for (const e of ordered) builder.apply(e);
  return builder.build();
}

/** Empty initial state (mirrors `GameState()` defaults). */
export function initialState(): GameState {
  return {
    status: 'lobby',
    last_seq: 0,
    remaining_zone_ids: [],
    remaining_area: null,
    timers: {},
    scoreboard: [],
    players: {},
    questions: [],
    notes: [],
    curses: [],
  };
}
