import React from 'react';
import { addDays, isDayBusy, todayISO, toISODate } from '../dates';
import { formatDayMonth } from '../format';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function dayState(iso, busy, today = todayISO()) {
  if (iso < today) return 'past';
  return isDayBusy(iso, busy) ? 'busy' : 'free';
}

const STATE_LABELS = { past: 'Past', busy: 'Busy', free: 'Free' };

// A grid of calendar days, one row per week from `weekStart`, marking when an item is busy or free.
// Free days can be clicked to choose the reservation's start and due dates (`start`, `due`).
export default function AvailabilityCalendar({ weekStart, weeks = 2, busy, start = null, due = null, onSelect }) {
  const today = todayISO();
  const days = Array.from({ length: weeks * 7 }, (_, index) => addDays(weekStart, index));

  return (
    <div className="calendar" role="group" aria-label="Availability">
      {WEEKDAYS.map(name => <span key={name} className="calendar-weekday" aria-hidden="true">{name}</span>)}
      {days.map(day => {
        const iso = toISODate(day);
        const state = dayState(iso, busy, today);
        const chosen = iso === start || iso === due;
        const inRange = start && due && iso > start && iso < due;
        const classes = ['calendar-day', state, chosen && 'selected', inRange && 'in-range', iso === today && 'today']
          .filter(Boolean).join(' ');
        return (
          <button
            key={iso}
            type="button"
            className={classes}
            disabled={state !== 'free'}
            aria-pressed={chosen}
            aria-label={`${day.toLocaleDateString(undefined, { weekday: 'long' })} ${formatDayMonth(day)}: ${STATE_LABELS[state]}`}
            onClick={() => onSelect?.(iso)}
          >
            <strong>{day.getDate()}</strong>
            <small>{STATE_LABELS[state]}</small>
          </button>
        );
      })}
    </div>
  );
}
