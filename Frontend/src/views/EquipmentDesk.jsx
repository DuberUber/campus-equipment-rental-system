import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../api';
import LoadState from '../components/LoadState';
import Pagination from '../components/Pagination';
import ReservationRow from '../components/ReservationRow';
import ReturnForm from '../components/ReturnForm';
import { addDays, dayBoundsISO, parseISODate, todayISO, toISODate } from '../dates';
import { errorMessages, formatDate } from '../format';
import { buildQuery, usePaginatedList } from '../hooks';

function DeskList({ list, empty, renderActions }) {
  return (
    <LoadState loading={list.loading && list.rows.length === 0} error={list.error}>
      {list.rows.length === 0 ? <p className="muted">{empty}</p> : (
        <ul className="rental-list">
          {list.rows.map(reservation => (
            <ReservationRow key={reservation.id} reservation={reservation} showStudent>
              {renderActions(reservation)}
            </ReservationRow>
          ))}
        </ul>
      )}
      <Pagination page={list.page} count={list.count} onChange={list.setPage} />
    </LoadState>
  );
}

// The desk's day: items waiting to be collected and items due back (including anything overdue).
export default function EquipmentDesk() {
  const [day, setDay] = useState(todayISO());
  const [returningId, setReturningId] = useState(null);
  const [message, setMessage] = useState('');
  const [errors, setErrors] = useState([]);
  const bounds = dayBoundsISO(day);
  const isToday = day === todayISO();

  const pickups = usePaginatedList(`/reservations/${buildQuery({
    status: 'reserved', start_before: bounds.end, due_after: bounds.start, ordering: 'start_at',
  })}`);
  const returns = usePaginatedList(`/reservations/${buildQuery({
    status: 'checked_out', due_before: bounds.end, ordering: 'due_at',
  })}`);

  function moveDay(days) {
    setDay(toISODate(addDays(parseISODate(day), days)));
    setReturningId(null);
  }

  async function checkOut(reservation) {
    setErrors([]);
    setMessage('');
    try {
      await apiFetch(`/reservations/${reservation.id}/checkout/`, { method: 'POST' });
      setMessage(`${reservation.equipment_name} checked out to ${reservation.student_name}.`);
      pickups.reload();
      returns.reload();
    } catch (error) {
      setErrors(errorMessages(error));
    }
  }

  function returned(reservation) {
    setReturningId(null);
    setMessage(`${reservation.equipment_name} returned by ${reservation.student_name}.`);
    returns.reload();
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Equipment desk</h2>
          <p className="muted">{isToday ? 'Today' : formatDate(day)}: pickups and returns.</p>
        </div>
        <div className="day-nav">
          <button type="button" className="secondary" onClick={() => moveDay(-1)}>← Previous day</button>
          <input type="date" value={day} onChange={e => e.target.value && setDay(e.target.value)} aria-label="Desk day" />
          <button type="button" className="secondary" onClick={() => moveDay(1)}>Next day →</button>
          {!isToday && <button type="button" className="link" onClick={() => setDay(todayISO())}>Today</button>}
        </div>
      </div>

      {message && <p className="success" role="status">{message}</p>}
      {errors.map(text => <p key={text} className="error">{text}</p>)}

      <div className="grid desk-grid">
        <section className="card">
          <h3>Pickups ({pickups.count})</h3>
          <p className="muted">Reserved items that can be collected {isToday ? 'today' : 'on this day'}.</p>
          <DeskList
            list={pickups}
            empty="No pickups."
            renderActions={reservation => (
              <button type="button" onClick={() => checkOut(reservation)} disabled={!isToday}>Check out</button>
            )}
          />
        </section>
        <section className="card">
          <h3>Returns due ({returns.count})</h3>
          <p className="muted">
            Items due back by the end of {isToday ? 'today' : 'this day'}, overdue ones first.{' '}
            <Link to="/overdue">See all overdue items</Link>.
          </p>
          <DeskList
            list={returns}
            empty="Nothing due back."
            renderActions={reservation => (returningId === reservation.id ? (
              <ReturnForm reservation={reservation} onReturned={() => returned(reservation)} onCancel={() => setReturningId(null)} />
            ) : (
              <button type="button" onClick={() => setReturningId(reservation.id)}>Return</button>
            ))}
          />
        </section>
      </div>
    </div>
  );
}
