/**
 * React glue around {@link startSync}. Starts a sync session for the current game on mount,
 * tears it down on unmount, and exposes a stable `send` function for emitting events.
 */

import { useEffect, useRef } from 'react';
import { startSync, type SyncHandle } from './sync';
import { useStore } from './store';

export function useSync(): { send: SyncHandle['send'] | null } {
  const session = useStore((s) => s.session);
  const handleRef = useRef<SyncHandle | null>(null);

  useEffect(() => {
    if (!session) return;
    const handle = startSync(session.gameId, session.token);
    handleRef.current = handle;
    return () => {
      handle.close();
      handleRef.current = null;
    };
  }, [session]);

  return {
    send: session
      ? (type, payload) => handleRef.current?.send(type, payload) ?? Promise.resolve()
      : null,
  };
}
