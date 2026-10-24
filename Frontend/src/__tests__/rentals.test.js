import { addDays, toISODate } from '../dates';
import { displayStatus, nextSelection, validateReservation } from '../rentals';

const inDays = days => toISODate(addDays(new Date(), days));

test('a valid request has no errors', () => {
  expect(validateReservation({ start: inDays(1), due: inDays(2), maxLoanDays: 2 })).toEqual([]);
  // The start and due dates both count, so a one-day loan is the same day.
  expect(validateReservation({ start: inDays(1), due: inDays(1), maxLoanDays: 1 })).toEqual([]);
});

test('the due date cannot be today once the desk has closed', () => {
  const evening = new Date();
  evening.setHours(18, 0, 0, 0);

  expect(validateReservation({ start: inDays(0), due: inDays(0), maxLoanDays: 3, now: evening })).toEqual([
    'The desk has closed for today. Choose a due date from tomorrow.',
  ]);
});

test('reports several problems at once', () => {
  const busy = [{ start_at: addDays(new Date(), -1).toISOString(), end_at: addDays(new Date(), 1).toISOString() }];

  expect(validateReservation({ start: inDays(-1), due: inDays(5), maxLoanDays: 2, busy })).toEqual([
    'The start date is in the past.',
    'This item can be borrowed for at most 2 days.',
    expect.stringMatching(/^The item is already reserved on /),
  ]);
});

test('clicking days picks a start, then a due date, then starts over', () => {
  let selection = { start: null, due: null };
  selection = nextSelection(selection, '2026-11-03');
  expect(selection).toEqual({ start: '2026-11-03', due: '2026-11-03' });

  selection = nextSelection(selection, '2026-11-05');
  expect(selection).toEqual({ start: '2026-11-03', due: '2026-11-05' });

  expect(nextSelection(selection, '2026-11-09')).toEqual({ start: '2026-11-09', due: '2026-11-09' });
  expect(nextSelection({ start: '2026-11-03', due: '2026-11-03' }, '2026-11-01')).toEqual({
    start: '2026-11-01', due: '2026-11-01',
  });
});

test('overdue wins over the stored status', () => {
  expect(displayStatus({ status: 'checked_out', is_overdue: true })).toBe('overdue');
  expect(displayStatus({ status: 'checked_out', is_overdue: false })).toBe('checked_out');
});
