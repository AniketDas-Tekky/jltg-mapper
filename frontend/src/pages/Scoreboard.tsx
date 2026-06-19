/**
 * Scoreboard: shows the run-time leaderboard accumulated from `round_ended` events
 * (highest run time wins, matching the backend's descending sort).
 */

import { useNavigate } from 'react-router-dom';
import { useStore } from '../lib/store';

function fmt(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}m ${String(s).padStart(2, '0')}s`;
}

export default function Scoreboard() {
  const navigate = useNavigate();
  const scoreboard = useStore((s) => s.state.scoreboard);
  const reset = useStore((s) => s.reset);

  return (
    <main className="min-h-dvh bg-slate-900 p-6 text-slate-100">
      <div className="mx-auto max-w-md space-y-6">
        <h1 className="text-2xl font-bold">Scoreboard</h1>
        <ol className="space-y-2">
          {scoreboard.length === 0 && <li className="text-slate-500">No rounds finished yet.</li>}
          {scoreboard.map((entry, i) => (
            <li
              key={`${entry.hider_id ?? 'anon'}-${i}`}
              className="flex items-center justify-between rounded-lg bg-slate-800 px-4 py-3"
            >
              <span>
                <span className="mr-2 text-slate-500">#{i + 1}</span>
                {entry.hider_name ?? 'Hider'}
              </span>
              <span className="font-mono">{fmt(entry.run_time_seconds)}</span>
            </li>
          ))}
        </ol>
        <button
          onClick={() => {
            reset();
            navigate('/');
          }}
          className="w-full rounded-lg bg-slate-700 py-2.5 font-semibold"
        >
          New game
        </button>
      </div>
    </main>
  );
}
