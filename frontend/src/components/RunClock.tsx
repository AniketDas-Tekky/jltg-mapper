/**
 * Run clock: counts up from `hiding_started_at` (in `state.timers`). Used to size the run
 * time when a round ends. Ticks once a second.
 */

import { useEffect, useState } from 'react';
import { useStore } from '../lib/store';

export function elapsedSeconds(startedAtIso: string | undefined): number {
  if (!startedAtIso) return 0;
  const start = Date.parse(startedAtIso);
  if (Number.isNaN(start)) return 0;
  return Math.max(0, Math.floor((Date.now() - start) / 1000));
}

function fmt(total: number): string {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function RunClock() {
  const startedAt = useStore((s) => s.state.timers.hiding_started_at as string | undefined);
  const [, tick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="font-mono tabular-nums">{fmt(elapsedSeconds(startedAt))}</span>
  );
}
