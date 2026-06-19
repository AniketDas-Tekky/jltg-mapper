/** Time helpers shared across components (kept out of component files so
 *  react-refresh fast-refresh stays happy with component-only exports). */

export function elapsedSeconds(startedAtIso: string | undefined): number {
  if (!startedAtIso) return 0;
  const start = Date.parse(startedAtIso);
  if (Number.isNaN(start)) return 0;
  return Math.max(0, Math.floor((Date.now() - start) / 1000));
}

export function formatClock(total: number): string {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}
