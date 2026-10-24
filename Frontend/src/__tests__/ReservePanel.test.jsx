import { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ReservePanel from '../components/ReservePanel';
import { addDays, atHour, toISODate } from '../dates';
import { SessionContext } from '../session';

const STUDENT = { id: 7, full_name: 'Aoife Brennan', is_staff: false };
const STAFF = { id: 2, full_name: 'Equipment Desk', is_staff: true };
const ITEM = {
  id: 4, name: 'Digital multimeter', location_name: 'Engineering Equipment Desk', max_loan_days: 3,
  is_active: true, is_reservable: true,
};
const inDays = days => toISODate(addDays(new Date(), days));

function jsonResponse(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
}

// The panel's dates live in its parent (shared with the calendar), so render it inside a small stateful host.
function Host({ user = STUDENT, equipment = ITEM, busy = [], onReserved = () => {} }) {
  const [selection, setSelection] = useState({ start: null, due: null });
  return (
    <SessionContext.Provider value={{ user, reload: () => {} }}>
      <ReservePanel equipment={equipment} busy={busy} selection={selection} onChange={setSelection} onReserved={onReserved} />
    </SessionContext.Provider>
  );
}

function chooseDates(start, due) {
  fireEvent.change(screen.getByLabelText('Start date'), { target: { value: start } });
  fireEvent.change(screen.getByLabelText('Due date'), { target: { value: due } });
}

const reserve = () => fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));
const posts = () => global.fetch.mock.calls.filter(([, options]) => options?.method === 'POST');

beforeEach(() => {
  global.fetch = jest.fn(() => jsonResponse({ id: 31 }, 201));
});

test('asks for both dates', () => {
  render(<Host />);
  reserve();

  expect(screen.getByRole('alert')).toHaveTextContent('Choose a start date and a due date.');
  expect(posts()).toHaveLength(0);
});

test('rejects a due date before the start date', () => {
  render(<Host />);
  chooseDates(inDays(3), inDays(2));
  reserve();

  expect(screen.getByText('The due date must be on or after the start date.')).toBeInTheDocument();
  expect(posts()).toHaveLength(0);
});

test('rejects loans longer than the item allows', () => {
  render(<Host />);
  chooseDates(inDays(1), inDays(4));
  reserve();

  expect(screen.getByText('This item can be borrowed for at most 3 days.')).toBeInTheDocument();
  expect(posts()).toHaveLength(0);
});

test('rejects dates in the past', () => {
  render(<Host />);
  chooseDates(inDays(-2), inDays(-1));
  reserve();

  expect(screen.getByText('The start date is in the past.')).toBeInTheDocument();
});

test('rejects a range that covers a busy day', () => {
  const busy = [{ start_at: atHour(inDays(2), 9).toISOString(), end_at: atHour(inDays(2), 17).toISOString() }];
  render(<Host busy={busy} />);
  chooseDates(inDays(1), inDays(3));
  reserve();

  expect(screen.getByText(/the item is already reserved on/i)).toBeInTheDocument();
  expect(posts()).toHaveLength(0);
});

test('sends a valid reservation from desk opening to closing time', async () => {
  const onReserved = jest.fn();
  render(<Host onReserved={onReserved} />);
  chooseDates(inDays(1), inDays(3));
  fireEvent.change(screen.getByLabelText('Notes for the desk'), { target: { value: 'Circuits lab' } });

  expect(screen.getByText(/^3 days:/)).toBeInTheDocument();
  reserve();

  await waitFor(() => expect(onReserved).toHaveBeenCalledWith({ id: 31 }));
  const [url, options] = posts()[0];
  expect(url).toMatch(/\/reservations\/$/);
  expect(JSON.parse(options.body)).toEqual({
    equipment: 4,
    start_at: atHour(inDays(1), 9).toISOString(),
    due_at: atHour(inDays(3), 17).toISOString(),
    notes: 'Circuits lab',
  });
});

test('shows the API error when the reservation is refused', async () => {
  global.fetch = jest.fn(() => jsonResponse({ student: ['Aoife Brennan has overdue equipment.'] }, 400));
  render(<Host />);
  chooseDates(inDays(1), inDays(2));
  reserve();

  expect(await screen.findByText('student: Aoife Brennan has overdue equipment.')).toBeInTheDocument();
});

test('staff must choose the student', async () => {
  global.fetch = jest.fn(() => jsonResponse({ count: 0, next: null, previous: null, results: [] }));
  render(<Host user={STAFF} />);
  chooseDates(inDays(1), inDays(2));
  reserve();

  expect(await screen.findByText('Choose the student this reservation is for.')).toBeInTheDocument();
  expect(posts()).toHaveLength(0);
});

test('items that cannot be reserved explain why', () => {
  render(<Host equipment={{ ...ITEM, is_reservable: false }} />);

  expect(screen.getByText(/waiting for repair/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Reserve' })).not.toBeInTheDocument();
});
