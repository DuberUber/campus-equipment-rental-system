import { parseISODate } from './dates';

export const STATUS_LABELS = {
  reserved: 'Reserved',
  checked_out: 'Checked out',
  returned: 'Returned',
  cancelled: 'Cancelled',
  overdue: 'Overdue',
};

export const CONDITION_LABELS = {
  excellent: 'Excellent',
  good: 'Good',
  fair: 'Fair',
  needs_repair: 'Needs repair',
};

export const KIND_LABELS = { lab: 'Lab', sports: 'Sports' };

const dateTimeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' });
const dateFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
const shortDateFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
const weekdayFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short' });
const dayMonthFormat = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' });

export const formatDateTime = iso => (iso ? dateTimeFormat.format(new Date(iso)) : '');
// Calendar days ("YYYY-MM-DD") are parsed as local dates to avoid a timezone shift.
export const formatDate = isoDate => (isoDate ? dateFormat.format(parseISODate(isoDate)) : '');
// The day part of an API datetime, in local time, e.g. "Mon 26 Oct".
export const formatDay = iso => (iso ? shortDateFormat.format(new Date(iso)) : '');
export const formatWeekday = date => weekdayFormat.format(date);
export const formatDayMonth = date => dayMonthFormat.format(date);
export const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`;

// How late a checked-out item is, e.g. "3 days overdue" (started days, so at least one).
export function overdueText(dueAt, now = new Date()) {
  const days = Math.max(1, Math.ceil((now - new Date(dueAt)) / 86400000));
  return `${plural(days, 'day')} overdue`;
}

// Flatten a DRF validation error body ({field: [messages]}) into readable lines.
export function errorMessages(error) {
  const body = error?.body;
  if (!body || typeof body !== 'object' || Object.keys(body).length === 0) {
    return [error?.message || 'Something went wrong.'];
  }
  return Object.entries(body).flatMap(([field, messages]) => {
    const list = Array.isArray(messages) ? messages : [messages];
    const prefix = field === 'detail' || field === 'non_field_errors' ? '' : `${field.replace(/_/g, ' ')}: `;
    return list.map(message => `${prefix}${message}`);
  });
}
