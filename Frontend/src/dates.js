// Calendar helpers. Calendar days are plain "YYYY-MM-DD" strings in the browser's local time, so these work
// with local days and never go through UTC (Date#toISOString would shift the day).

const pad = number => String(number).padStart(2, '0');

export const toISODate = date => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

export function parseISODate(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function addDays(date, days) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

// Weeks start on Monday.
export function startOfWeek(date) {
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  return addDays(day, -((day.getDay() + 6) % 7));
}

export const weekDays = weekStart => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));

export const todayISO = () => toISODate(new Date());

// Whole days from one calendar day to another (rounded, so a daylight-saving change doesn't matter).
export const daysBetween = (fromISO, toISO) => Math.round((parseISODate(toISO) - parseISODate(fromISO)) / 86400000);

// Every calendar day from `fromISO` to `toISO`, both included.
export function daysInRange(fromISO, toISO) {
  const days = [];
  for (let day = parseISODate(fromISO); toISODate(day) <= toISO; day = addDays(day, 1)) days.push(toISODate(day));
  return days;
}

// The equipment desks hand items out from opening time and take them back until closing time.
export const DESK_OPENS = 9;
export const DESK_CLOSES = 17;

export function atHour(iso, hour) {
  const moment = parseISODate(iso);
  moment.setHours(hour, 0, 0, 0);
  return moment;
}

// When a reservation for these days starts and is due: collect from opening time on the first day (or in a
// minute, if that time has already passed today) and return by closing time on the last day.
export function reservationWindow(startISO, dueISO, now = new Date()) {
  let start = atHour(startISO, DESK_OPENS);
  if (start < now) {
    start = new Date(now.getTime() + 60000);
    start.setSeconds(0, 0);
  }
  return { start, due: atHour(dueISO, DESK_CLOSES) };
}

// Is the day busy? `ranges` are the API's busy ranges ({start_at, end_at} datetimes).
export function isDayBusy(iso, ranges) {
  const dayStart = parseISODate(iso);
  const dayEnd = addDays(dayStart, 1);
  return ranges.some(range => new Date(range.start_at) < dayEnd && new Date(range.end_at) > dayStart);
}

// Bounds of a local calendar day as ISO datetimes, for the API's datetime filters.
export function dayBoundsISO(iso) {
  const start = parseISODate(iso);
  return { start: start.toISOString(), end: addDays(start, 1).toISOString() };
}
