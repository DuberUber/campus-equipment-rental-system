import React from 'react';
import { parseISODate } from '../dates';

// A calendar-page style date: month on top, large day number, weekday underneath.
export default function DateTile({ date }) {
  const day = parseISODate(date);
  return (
    <span className="date-tile" aria-hidden="true">
      <span className="date-tile-month">{day.toLocaleDateString(undefined, { month: 'short' })}</span>
      <span className="date-tile-day">{day.getDate()}</span>
      <span className="date-tile-weekday">{day.toLocaleDateString(undefined, { weekday: 'short' })}</span>
    </span>
  );
}
