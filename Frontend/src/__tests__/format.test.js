import { errorMessages, overdueText, plural } from '../format';

test('flattens DRF validation errors into readable lines', () => {
  const error = {
    body: {
      due_at: ['Football can be borrowed for at most 2 days.'],
      non_field_errors: ['Something else.'],
    },
  };
  expect(errorMessages(error)).toEqual([
    'due at: Football can be borrowed for at most 2 days.',
    'Something else.',
  ]);
});

test('falls back to the error message when there is no body', () => {
  expect(errorMessages(new Error('Network down'))).toEqual(['Network down']);
});

test('describes how overdue an item is in started days', () => {
  const now = new Date(2026, 9, 24, 12);

  expect(overdueText(new Date(2026, 9, 24, 9).toISOString(), now)).toBe('1 day overdue');
  expect(overdueText(new Date(2026, 9, 21, 17).toISOString(), now)).toBe('3 days overdue');
});

test('pluralises counts', () => {
  expect(plural(1, 'day')).toBe('1 day');
  expect(plural(14, 'day')).toBe('14 days');
});
