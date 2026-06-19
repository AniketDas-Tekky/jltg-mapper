/**
 * Hider view: the map, a hide-time zone confirmation (capture GPS once hidden, recorded as a
 * note so seekers can't see it but it's logged), and a list of pending questions to answer.
 * Answering emits `question_answered`; the server's deduction engine then shrinks the zones.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MapView from '../components/Map';
import { RunClock } from '../components/RunClock';
import { getCurrentPosition } from '../lib/geo';
import { answerOptions } from '../lib/questions';
import { useStore } from '../lib/store';
import { useSync } from '../lib/useSync';

export default function HiderView() {
  const navigate = useNavigate();
  const session = useStore((s) => s.session);
  const status = useStore((s) => s.state.status);
  const questions = useStore((s) => s.state.questions);
  const { send } = useSync();

  const [confirmed, setConfirmed] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) navigate('/');
  }, [session, navigate]);

  useEffect(() => {
    if (status === 'ended') navigate('/scoreboard');
  }, [status, navigate]);

  if (!session) return null;

  async function confirmHidingSpot() {
    setConfirming(true);
    setGeoError(null);
    try {
      const loc = await getCurrentPosition();
      await send?.('note_added', {
        text: `hider confirmed hiding spot at ${loc.lat.toFixed(5)},${loc.lon.toFixed(5)}`,
        author: session!.playerId,
      });
      setConfirmed(true);
    } catch {
      setGeoError('Could not get your location.');
    } finally {
      setConfirming(false);
    }
  }

  async function answer(questionId: string, value: string) {
    await send?.('question_answered', {
      question_id: questionId,
      answer: value,
      hider_id: session!.playerId,
    });
  }

  const pending = questions.filter((q) => q.answer == null);

  return (
    <div className="flex h-dvh flex-col bg-slate-900 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <span className="font-semibold">Hider</span>
        <span className="text-sm text-slate-400">
          <RunClock />
        </span>
        <span className="text-xs uppercase text-cyan-400">{status}</span>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          <MapView />
        </div>

        <aside className="flex w-80 flex-col gap-4 overflow-auto border-l border-slate-800 p-4">
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase text-slate-400">Your hiding spot</h2>
            {confirmed ? (
              <p className="text-sm text-emerald-400">Hiding spot confirmed.</p>
            ) : (
              <button
                onClick={confirmHidingSpot}
                disabled={confirming}
                className="w-full rounded bg-cyan-600 py-2 text-sm font-semibold disabled:opacity-50"
              >
                {confirming ? 'Capturing…' : 'Confirm hiding spot (GPS)'}
              </button>
            )}
            {geoError && <p className="mt-1 text-xs text-rose-400">{geoError}</p>}
          </section>

          <section className="min-h-0 flex-1">
            <h2 className="mb-2 text-sm font-semibold uppercase text-slate-400">
              Questions to answer ({pending.length})
            </h2>
            <ul className="space-y-3 text-sm">
              {pending.length === 0 && <li className="text-slate-500">No pending questions.</li>}
              {pending.map((q) => (
                <li key={q.question_id} className="rounded bg-slate-800 px-3 py-2">
                  <div className="mb-2 font-medium capitalize">
                    {q.category} · {q.subtype}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {answerOptions(q.category).map((opt) => (
                      <button
                        key={opt}
                        onClick={() => answer(q.question_id, opt)}
                        className="rounded bg-cyan-700 px-3 py-1 text-xs capitalize"
                      >
                        {opt}
                      </button>
                    ))}
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
