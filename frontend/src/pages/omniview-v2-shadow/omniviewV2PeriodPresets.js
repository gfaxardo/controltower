/**
 * Omniview V2 — Period Presets
 * OV2-UI-P1E: Quick date range navigation.
 *
 * Generates date ranges for common operational presets.
 * Uses ISO weeks (Monday start). Browser local date.
 */

function fmt(d) {
  return d.toISOString().slice(0, 10);
}

function todayDate() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function mondayOfWeek(d) {
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day; // ISO: Monday=1
  const m = new Date(d);
  m.setDate(d.getDate() + diff);
  return m;
}

export const PERIOD_PRESETS = [
  { id: 'today', label: 'Today' },
  { id: 'last_7d', label: 'Last 7d' },
  { id: 'this_week', label: 'This Week' },
  { id: 'this_month', label: 'This Month' },
  { id: 'prev_week', label: 'Prev Week' },
  { id: 'prev_month', label: 'Prev Month' },
];

export function getPresetRange(presetId) {
  const now = todayDate();
  switch (presetId) {
    case 'today':
      return { from: fmt(now), to: fmt(now) };
    case 'last_7d': {
      const start = new Date(now);
      start.setDate(now.getDate() - 6);
      return { from: fmt(start), to: fmt(now) };
    }
    case 'this_week': {
      const mon = mondayOfWeek(now);
      return { from: fmt(mon), to: fmt(now) };
    }
    case 'this_month': {
      const first = new Date(now.getFullYear(), now.getMonth(), 1);
      return { from: fmt(first), to: fmt(now) };
    }
    case 'prev_week': {
      const mon = mondayOfWeek(now);
      const prevMon = new Date(mon);
      prevMon.setDate(mon.getDate() - 7);
      const prevSun = new Date(prevMon);
      prevSun.setDate(prevMon.getDate() + 6);
      return { from: fmt(prevMon), to: fmt(prevSun) };
    }
    case 'prev_month': {
      const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const last = new Date(now.getFullYear(), now.getMonth(), 0);
      return { from: fmt(first), to: fmt(last) };
    }
    default:
      return null;
  }
}
