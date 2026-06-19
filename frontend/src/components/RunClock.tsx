/**
 * Run clock: counts up from `hiding_started_at` (in `state.timers`). Used to size the run
 * time when a round ends. Ticks once a second.
 */

import { useEffect, useState } from 'react';
import { useStore } from '../lib/store';
import { elapsedSeconds, formatClock as fmt } from '../lib/time';

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
