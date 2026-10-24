import React from 'react';
import { addDays, startOfWeek, toISODate } from '../dates';
import { formatDayMonth } from '../format';

// Previous / next week controls with the visible range, e.g. "15 Sept – 21 Sept".
export default function WeekNavigator({ weekStart, onChange, allowPast = false }) {
  const thisWeek = startOfWeek(new Date());
  const isThisWeek = toISODate(weekStart) === toISODate(thisWeek);
  const atEarliest = !allowPast && weekStart <= thisWeek;
  return (
    <div className="week-nav">
      <button type="button" className="secondary" onClick={() => onChange(addDays(weekStart, -7))} disabled={atEarliest}>
        ← Previous week
      </button>
      <strong aria-live="polite">{formatDayMonth(weekStart)} – {formatDayMonth(addDays(weekStart, 6))}</strong>
      <button type="button" className="secondary" onClick={() => onChange(addDays(weekStart, 7))}>
        Next week →
      </button>
      {!isThisWeek && (
        <button type="button" className="link" onClick={() => onChange(thisWeek)}>This week</button>
      )}
    </div>
  );
}
