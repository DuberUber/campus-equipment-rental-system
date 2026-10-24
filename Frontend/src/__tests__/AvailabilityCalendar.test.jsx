import { fireEvent, render, screen } from '@testing-library/react';
import AvailabilityCalendar, { dayState } from '../components/AvailabilityCalendar';
import { addDays, atHour, startOfWeek, toISODate } from '../dates';

// Two weeks starting next Monday, so every day is in the future whatever today is.
const weekStart = addDays(startOfWeek(new Date()), 7);
const day = offset => toISODate(addDays(weekStart, offset));
const busyRange = (from, to) => ({ start_at: atHour(day(from), 9).toISOString(), end_at: atHour(day(to), 17).toISOString() });

const dayButtons = () => screen.getAllByRole('button');

test('marks busy and free days', () => {
  render(<AvailabilityCalendar weekStart={weekStart} busy={[busyRange(1, 2)]} />);

  const buttons = dayButtons();
  expect(buttons).toHaveLength(14);
  expect(buttons[0]).toHaveClass('calendar-day', 'free');
  expect(buttons[1]).toHaveClass('busy');
  expect(buttons[2]).toHaveClass('busy');
  expect(buttons[3]).toHaveClass('free');
  expect(buttons[1]).toBeDisabled();
  expect(buttons[1]).toHaveAccessibleName(/: Busy$/);
  expect(buttons[0]).toHaveAccessibleName(/: Free$/);
});

test('reports the chosen day and highlights the selected range', () => {
  const onSelect = jest.fn();

  render(<AvailabilityCalendar weekStart={weekStart} busy={[]} start={day(3)} due={day(5)} onSelect={onSelect} />);
  const buttons = dayButtons();
  fireEvent.click(buttons[8]);

  expect(onSelect).toHaveBeenCalledWith(day(8));
  expect(buttons[3]).toHaveClass('selected');
  expect(buttons[3]).toHaveAttribute('aria-pressed', 'true');
  expect(buttons[4]).toHaveClass('in-range');
  expect(buttons[5]).toHaveClass('selected');
  expect(buttons[6]).not.toHaveClass('in-range');
});

test('busy days cannot be chosen and past days are marked as past', () => {
  const onSelect = jest.fn();
  render(<AvailabilityCalendar weekStart={weekStart} busy={[busyRange(0, 0)]} onSelect={onSelect} />);

  fireEvent.click(dayButtons()[0]);

  expect(onSelect).not.toHaveBeenCalled();
  expect(dayState('2000-01-01', [])).toBe('past');
  expect(dayState(day(0), [busyRange(0, 0)])).toBe('busy');
});

test('a range ending at midnight does not mark the next day busy', () => {
  const range = { start_at: atHour(day(2), 9).toISOString(), end_at: atHour(day(3), 0).toISOString() };

  expect(dayState(day(2), [range])).toBe('busy');
  expect(dayState(day(3), [range])).toBe('free');
});
