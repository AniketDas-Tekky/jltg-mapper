/**
 * Thin REST client for the FastAPI backend. Routes match `backend/app/api/*` exactly.
 * In dev, `/api` and `/ws` are proxied to :8000 by Vite (see vite.config.ts).
 */

import type {
  CreateGameResponse,
  EventResponse,
  JoinGameResponse,
  StateResponse,
} from './types';

const BASE = '/api';

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init: RequestInit, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new ApiError(res.status, body, `${res.status} ${path}`);
  }
  return body as T;
}

export function createGame(hostName: string): Promise<CreateGameResponse> {
  return request('/games', {
    method: 'POST',
    body: JSON.stringify({ host_name: hostName }),
  });
}

export function joinGame(
  joinCode: string,
  name: string,
  role: 'seeker' | 'hider',
): Promise<JoinGameResponse> {
  return request(`/games/${encodeURIComponent(joinCode.toUpperCase())}/join`, {
    method: 'POST',
    body: JSON.stringify({ name, role }),
  });
}

export function getState(gameId: string, token: string): Promise<StateResponse> {
  return request(`/games/${gameId}/state`, { method: 'GET' }, token);
}

export function getEvents(
  gameId: string,
  sinceSeq: number,
  token: string,
): Promise<EventResponse[]> {
  return request(`/games/${gameId}/events?since_seq=${sinceSeq}`, { method: 'GET' }, token);
}

export interface PostEventBody {
  client_event_id: string;
  type: string;
  payload: Record<string, unknown>;
}

/**
 * Append an event over REST. On a duplicate `client_event_id` the backend returns 409 with
 * `detail.server_seq`; callers treat that as success (already applied).
 */
export async function postEvent(
  gameId: string,
  body: PostEventBody,
  token: string,
): Promise<EventResponse> {
  return request(`/games/${gameId}/events`, {
    method: 'POST',
    body: JSON.stringify(body),
  }, token);
}

export async function health(): Promise<boolean> {
  try {
    const res = await fetch('/health');
    return res.ok;
  } catch {
    return false;
  }
}
