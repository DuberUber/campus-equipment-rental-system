import { DESK_CLOSES, daysBetween, daysInRange, isDayBusy, todayISO } from './dates';
import { formatDate, plural } from './format';

// Check a reservation request before sending it, mirroring the API's rules so students get instant feedback.
// The API re-checks everything (and the rules students can't see, such as their own loan limit).
export function validateReservation({ start, due, maxLoanDays, busy = [], now = new Date() }) {
  if (!start || !due) return ['Choose a start date and a due date.'];
  const today = todayISO();
  const errors = [];
  if (start < today) errors.push('The start date is in the past.');
  if (due < start) {
    errors.push('The due date must be on or after the start date.');
    return errors;
  }
  if (daysBetween(start, due) + 1 > maxLoanDays) {
    errors.push(`This item can be borrowed for at most ${plural(maxLoanDays, 'day')}.`);
  }
  if (due === today && now.getHours() >= DESK_CLOSES) {
    errors.push('The desk has closed for today. Choose a due date from tomorrow.');
  }
  const firstBusy = daysInRange(start, due).find(day => isDayBusy(day, busy));
  if (firstBusy) errors.push(`The item is already reserved on ${formatDate(firstBusy)}.`);
  return errors;
}

// Clicking calendar days: the first click picks the start date, a later day then picks the due date, and a
// click before the start (or once both are set) starts over.
export function nextSelection({ start, due }, iso) {
  if (!start || (due && due !== start) || iso < start) return { start: iso, due: iso };
  return { start, due: iso };
}

// The status to show for a reservation: overdue wins over checked out.
export const displayStatus = reservation => (reservation.is_overdue ? 'overdue' : reservation.status);
