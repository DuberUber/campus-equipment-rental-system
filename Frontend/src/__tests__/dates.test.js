import {
  addDays, atHour, dayBoundsISO, daysBetween, daysInRange, isDayBusy, parseISODate, reservationWindow, startOfWeek,
  toISODate, weekDays,
} from '../dates';

test('weeks start on Monday', () => {
  expect(toISODate(startOfWeek(new Date(2026, 8, 16)))).toBe('2026-09-14'); // Wednesday
  expect(toISODate(startOfWeek(new Date(2026, 8, 20)))).toBe('2026-09-14'); // Sunday
  expect(toISODate(startOfWeek(new Date(2026, 8, 21, 23, 30)))).toBe('2026-09-21'); // Monday night
});

test('dates round-trip as local calendar days', () => {
  const date = parseISODate('2026-12-31');
  expect(date.getDate()).toBe(31);
  expect(toISODate(date)).toBe('2026-12-31');
  expect(toISODate(addDays(date, 1))).toBe('2027-01-01');
});

test('weekDays lists the seven days of a week', () => {
  expect(weekDays(new Date(2026, 8, 28)).map(toISODate)).toEqual([
    '2026-09-28', '2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04',
  ]);
});

test('counts and lists days in a range, across month ends and clock changes', () => {
  expect(daysBetween('2026-10-30', '2026-11-02')).toBe(3);
  expect(daysBetween('2026-10-24', '2026-10-26')).toBe(2); // includes the October clock change in Europe
  expect(daysInRange('2026-10-30', '2026-11-01')).toEqual(['2026-10-30', '2026-10-31', '2026-11-01']);
  expect(daysInRange('2026-10-30', '2026-10-30')).toEqual(['2026-10-30']);
});

test('a reservation runs from desk opening on the first day to closing on the due date', () => {
  const now = new Date(2026, 9, 20, 8, 0);
  const { start, due } = reservationWindow('2026-10-21', '2026-10-23', now);

  expect(start).toEqual(new Date(2026, 9, 21, 9, 0));
  expect(due).toEqual(new Date(2026, 9, 23, 17, 0));
  expect(atHour('2026-10-21', 9)).toEqual(start);
});

test('a reservation made after opening time today starts in a minute', () => {
  const now = new Date(2026, 9, 20, 13, 45, 30);

  expect(reservationWindow('2026-10-20', '2026-10-20', now).start).toEqual(new Date(2026, 9, 20, 13, 46, 0));
});

test('a day is busy when any range overlaps it', () => {
  const ranges = [{ start_at: new Date(2026, 9, 21, 9).toISOString(), end_at: new Date(2026, 9, 22, 17).toISOString() }];

  expect(isDayBusy('2026-10-20', ranges)).toBe(false);
  expect(isDayBusy('2026-10-21', ranges)).toBe(true);
  expect(isDayBusy('2026-10-22', ranges)).toBe(true);
  expect(isDayBusy('2026-10-23', ranges)).toBe(false);
  expect(isDayBusy('2026-10-21', [])).toBe(false);
});

test('day bounds cover one local day', () => {
  const { start, end } = dayBoundsISO('2026-10-21');

  expect(new Date(start)).toEqual(new Date(2026, 9, 21));
  expect(new Date(end)).toEqual(new Date(2026, 9, 22));
});
