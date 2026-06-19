/**
 * Seeker view: the map (with the shrinking remaining-zones overlay), a question composer
 * that captures the seeker's geolocation and emits `question_asked`, a Q/A log, manual
 * zone exclude/restore controls, and the run clock. When a round ends -> scoreboard.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../components/Map';
import { RunClock } from '../components/RunClock';
import { elapsedSeconds } from '../lib/time';
import { getCurrentPosition } from '../lib/geo';
import { QUESTION_OPTIONS } from '../lib/questions';
import { useStore } from '../lib/store';
import { useSync } from '../lib/useSync';
import { uuid } from '../lib/sync';

export default function SeekerView() {
  const navigate = useNavigate();
  const session = useStore((s) => s.session);
  const status = useStore((s) => s.state.status);
  const questions = useStore((s) => s.state.questions);
  const remaining = useStore((s) => s.state.remaining_zone_ids);
  const startedAt = useStore((s) => s.state.timers.hiding_started_at as string | undefined);
  const { send } = useSync();

  const [optionIdx, setOptionIdx] = useState(0);
  const [radius, setRadius] = useState(1);
  const [zoneInput, setZoneInput] = useState('');
  const [asking, setAsking] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) navigate('/');
  }, [session, navigate]);

  useEffect(() => {
    if (status === 'ended') navigate('/scoreboard');
  }, [status, navigate]);

  if (!session) return null;

  async function askQuestion() {
    setAsking(true);
    setGeoError(null);
    const opt = QUESTION_OPTIONS[optionIdx];
    try {
      const loc = await getCurrentPosition();
      const params: Record<string, unknown> = {};
      if (opt.needsRadius) params.radius_miles = radius;
      await send?.('question_asked', {
        question_id: uuid(),
        category: opt.category,
        subtype: opt.subtype,
        seeker_location: loc,
        asked_by: session!.playerId,
        params,
      });
    } catch {
      setGeoError('Could not get your location. Enable location access.');
    } finally {
      setAsking(false);
    }
  }

  async function excludeZone() {
    const id = parseInt(zoneInput, 10);
    if (!Number.isNaN(id)) {
      await send?.('zone_excluded', { zone_id: id, reason: 'manual' });
      setZoneInput('');
    }
  }

  async function restoreZone() {
    const id = parseInt(zoneInput, 10);
    if (!Number.isNaN(id)) {
      await send?.('zone_restored', { zone_id: id, reason: 'manual' });
      setZoneInput('');
    }
  }

  async function endRound() {
    await send?.('round_ended', {
      run_time_seconds: elapsedSeconds(startedAt),
      hider_name: null,
    });
  }

  const opt = QUESTION_OPTIONS[optionIdx];

  return (
    <div className="flex h-dvh flex-col bg-slate-900 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <span className="font-semibold">Seeker</span>
        <span className="text-sm text-slate-400">
          {remaining.length} zones left · <RunClock />
        </span>
        <button onClick={endRound} className="rounded bg-rose-600 px-3 py-1 text-sm">
          End round
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          <MapView />
        </div>

        <aside className="flex w-80 flex-col gap-4 overflow-auto border-l border-slate-800 p-4">
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase text-slate-400">Ask a question</h2>
            <select
              className="mb-2 w-full rounded bg-slate-800 px-2 py-2 text-sm"
              value={optionIdx}
              onChange={(e) => setOptionIdx(Number(e.target.value))}
            >
              {QUESTION_OPTIONS.map((o, i) => (
                <option key={o.label} value={i}>
                  {o.label}
                </option>
              ))}
            </select>
            {opt.needsRadius && (
              <label className="mb-2 flex items-center gap-2 text-sm">
                Radius (mi)
                <input
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={radius}
                  onChange={(e) => setRadius(Number(e.target.value))}
                  className="w-20 rounded bg-slate-800 px-2 py-1"
                />
              </label>
            )}
            <button
              onClick={askQuestion}
              disabled={asking}
              className="w-full rounded bg-cyan-600 py-2 text-sm font-semibold disabled:opacity-50"
            >
              {asking ? 'Capturing location…' : 'Ask (captures GPS)'}
            </button>
            {geoError && <p className="mt-1 text-xs text-rose-400">{geoError}</p>}
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase text-slate-400">Manual zones</h2>
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="zone id"
                value={zoneInput}
                onChange={(e) => setZoneInput(e.target.value)}
                className="w-full rounded bg-slate-800 px-2 py-1 text-sm"
              />
              <button onClick={excludeZone} className="rounded bg-slate-700 px-2 text-sm">
                Exclude
              </button>
              <button onClick={restoreZone} className="rounded bg-slate-700 px-2 text-sm">
                Restore
              </button>
            </div>
          </section>

          <section className="min-h-0 flex-1">
            <h2 className="mb-2 text-sm font-semibold uppercase text-slate-400">Q/A log</h2>
            <ul className="space-y-2 text-sm">
              {questions.length === 0 && <li className="text-slate-500">No questions yet.</li>}
              {[...questions].reverse().map((q) => (
                <li key={q.question_id} className="rounded bg-slate-800 px-3 py-2">
                  <div className="font-medium capitalize">
                    {q.category} · {q.subtype}
                  </div>
                  <div className="text-xs text-slate-400">
                    {q.answer == null ? 'awaiting answer…' : `answer: ${String(q.answer)}`}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
