/**
 * Entry screen: create a new game (host) or join an existing one by code.
 *
 * Create -> POST /api/games, persist the host session, go to the lobby.
 * Join   -> POST /api/games/{code}/join with name + role, persist session, go to lobby.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createGame, joinGame, ApiError } from '../lib/api';
import { useStore } from '../lib/store';

export default function Join() {
  const navigate = useNavigate();
  const setSession = useStore((s) => s.setSession);
  const setEvents = useStore((s) => s.setEvents);

  const [mode, setMode] = useState<'join' | 'create'>('join');
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState<'seeker' | 'hider'>('seeker');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await createGame(name.trim() || 'Host');
      setEvents([]);
      setSession({
        gameId: res.game_id,
        playerId: res.player_id,
        token: res.token,
        role: 'host',
        joinCode: res.join_code,
        name: name.trim() || 'Host',
      });
      navigate('/lobby');
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : 'Could not create game');
    } finally {
      setBusy(false);
    }
  }

  async function onJoin(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await joinGame(code.trim(), name.trim(), role);
      setEvents([]);
      setSession({
        gameId: res.game_id,
        playerId: res.player_id,
        token: res.token,
        role: res.role,
        joinCode: code.trim().toUpperCase(),
        name: name.trim(),
      });
      navigate('/lobby');
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setError('Game not found');
      else setError(err instanceof ApiError ? `Error ${err.status}` : 'Could not join game');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-slate-900 p-6 text-slate-100">
      <div className="w-full max-w-sm rounded-2xl bg-slate-800/70 p-6 shadow-xl">
        <h1 className="mb-1 text-2xl font-bold">jltg-mapper</h1>
        <p className="mb-5 text-sm text-slate-400">SF Hide &amp; Seek companion</p>

        <div className="mb-5 flex rounded-lg bg-slate-900 p-1 text-sm">
          <button
            type="button"
            className={`flex-1 rounded-md py-1.5 ${mode === 'join' ? 'bg-slate-700' : ''}`}
            onClick={() => setMode('join')}
          >
            Join
          </button>
          <button
            type="button"
            className={`flex-1 rounded-md py-1.5 ${mode === 'create' ? 'bg-slate-700' : ''}`}
            onClick={() => setMode('create')}
          >
            Create
          </button>
        </div>

        <form onSubmit={mode === 'join' ? onJoin : onCreate} className="space-y-3">
          {mode === 'join' && (
            <input
              className="w-full rounded-lg bg-slate-900 px-3 py-2 uppercase tracking-widest placeholder:tracking-normal placeholder:normal-case"
              placeholder="Join code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
            />
          )}
          <input
            className="w-full rounded-lg bg-slate-900 px-3 py-2"
            placeholder={mode === 'create' ? 'Host name' : 'Your name'}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required={mode === 'join'}
          />
          {mode === 'join' && (
            <div className="flex gap-2 text-sm">
              {(['seeker', 'hider'] as const).map((r) => (
                <button
                  type="button"
                  key={r}
                  className={`flex-1 rounded-lg py-2 capitalize ${
                    role === r ? 'bg-cyan-600 text-white' : 'bg-slate-900 text-slate-300'
                  }`}
                  onClick={() => setRole(r)}
                >
                  {r}
                </button>
              ))}
            </div>
          )}

          {error && <p className="text-sm text-rose-400">{error}</p>}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-cyan-600 py-2.5 font-semibold text-white disabled:opacity-50"
          >
            {busy ? '…' : mode === 'join' ? 'Join game' : 'Create game'}
          </button>
        </form>
      </div>
    </main>
  );
}
