/**
 * Pre-game lobby: shows the join code + roster (derived from `player_joined` events) and,
 * for the host, a "Start hiding" button that emits `hiding_started`. Once the game leaves
 * lobby status, players are routed to their role view.
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../lib/store';
import { useSync } from '../lib/useSync';

export default function Lobby() {
  const navigate = useNavigate();
  const session = useStore((s) => s.session);
  const players = useStore((s) => s.state.players);
  const status = useStore((s) => s.state.status);
  const { send } = useSync();

  useEffect(() => {
    if (!session) navigate('/');
  }, [session, navigate]);

  // Leave the lobby once hiding/seeking begins.
  useEffect(() => {
    if (!session) return;
    if (status === 'hiding' || status === 'seeking') {
      navigate(session.role === 'hider' ? '/hider' : '/seeker');
    } else if (status === 'ended') {
      navigate('/scoreboard');
    }
  }, [status, session, navigate]);

  if (!session) return null;

  const roster = Object.entries(players);
  const isHost = session.role === 'host';

  async function startHiding() {
    await send?.('hiding_started', {
      started_at: new Date().toISOString(),
      hiding_duration_seconds: 1800,
    });
  }

  return (
    <main className="min-h-dvh bg-slate-900 p-6 text-slate-100">
      <div className="mx-auto max-w-md space-y-6">
        <div>
          <p className="text-sm text-slate-400">Join code</p>
          <p className="font-mono text-4xl font-bold tracking-widest">{session.joinCode}</p>
        </div>

        <div>
          <h2 className="mb-2 text-lg font-semibold">Players ({roster.length})</h2>
          <ul className="space-y-1">
            {roster.length === 0 && <li className="text-slate-500">Waiting for players…</li>}
            {roster.map(([id, p]) => (
              <li
                key={id}
                className="flex items-center justify-between rounded-lg bg-slate-800 px-3 py-2"
              >
                <span>{p.name ?? 'Player'}</span>
                <span className="text-xs uppercase text-cyan-400">{p.role}</span>
              </li>
            ))}
          </ul>
        </div>

        {isHost ? (
          <button
            onClick={startHiding}
            className="w-full rounded-lg bg-cyan-600 py-3 font-semibold text-white"
          >
            Start hiding
          </button>
        ) : (
          <p className="text-center text-sm text-slate-400">Waiting for the host to start…</p>
        )}

        <p className="text-center text-xs text-slate-500">You are: {session.role}</p>
      </div>
    </main>
  );
}
