import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MyRentals from '../views/MyRentals';

const FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true };
const DAY = 86400000;
const iso = offsetDays => new Date(Date.now() + offsetDays * DAY).toISOString();

const reservation = (id, extra) => ({
  id, equipment: id, equipment_name: 'Digital multimeter', asset_tag: `MM-00${id}`, location_name: 'Engineering Desk',
  building: 'Engineering Building', start_at: iso(-5), due_at: iso(2), status: 'checked_out', is_overdue: false,
  returned_late: false, ...extra,
});

const OVERDUE = reservation(1, { due_at: iso(-2.5), is_overdue: true });
const ON_LOAN = reservation(2, { equipment_name: 'Raspberry Pi 5 starter kit' });

function page(rows) {
  return Promise.resolve({
    ok: true, status: 200, json: () => Promise.resolve({ count: rows.length, next: null, previous: null, results: rows }),
  });
}

beforeEach(() => {
  global.fetch = jest.fn(url => page(url.includes('overdue=true') ? [OVERDUE] : [OVERDUE, ON_LOAN]));
});

test('highlights overdue rentals and warns about the reservation block', async () => {
  render(<MemoryRouter future={FUTURE}><MyRentals /></MemoryRouter>);

  const overdueRow = await screen.findByTestId('reservation-1');
  const onLoanRow = screen.getByTestId('reservation-2');

  expect(overdueRow).toHaveClass('overdue');
  expect(within(overdueRow).getByText('Overdue')).toHaveClass('badge-overdue');
  expect(within(overdueRow).getByText('3 days overdue')).toBeInTheDocument();
  expect(onLoanRow).not.toHaveClass('overdue');
  expect(within(onLoanRow).getByText('Checked out')).toBeInTheDocument();
  expect(await screen.findByRole('alert')).toHaveTextContent(/1 overdue item.*can't reserve anything else/);
});

test('no warning when nothing is overdue', async () => {
  global.fetch = jest.fn(url => page(url.includes('overdue=true') ? [] : [ON_LOAN]));

  render(<MemoryRouter future={FUTURE}><MyRentals /></MemoryRouter>);

  expect(await screen.findByTestId('reservation-2')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
