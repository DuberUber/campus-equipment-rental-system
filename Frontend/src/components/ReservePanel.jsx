import React, { useState } from 'react';
import { apiFetch } from '../api';
import { DESK_CLOSES, DESK_OPENS, daysBetween, reservationWindow, todayISO } from '../dates';
import { errorMessages, formatDate, plural } from '../format';
import { validateReservation } from '../rentals';
import { useSession } from '../session';
import SearchSelect from './SearchSelect';

const hour = h => `${String(h).padStart(2, '0')}:00`;

// The reserve form for one item. The chosen dates (`selection`) are shared with the availability calendar.
export default function ReservePanel({ equipment, busy, selection, onChange, onReserved, onConflict }) {
  const { user } = useSession();
  const [student, setStudent] = useState(null);
  const [notes, setNotes] = useState('');
  const [errors, setErrors] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const { start, due } = selection;

  if (!equipment.is_reservable) {
    return (
      <section className="card reserve-panel" aria-label="Reserve this item">
        <h3>Reserve</h3>
        <p className="error">
          {equipment.is_active ? 'This item is waiting for repair and cannot be reserved.' : 'This item has been retired.'}
        </p>
      </section>
    );
  }

  function update(field, value) {
    setErrors([]);
    onChange({ ...selection, [field]: value });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const problems = validateReservation({ start, due, maxLoanDays: equipment.max_loan_days, busy });
    if (user.is_staff && !student) problems.push('Choose the student this reservation is for.');
    setErrors(problems);
    if (problems.length) return;

    setSubmitting(true);
    const times = reservationWindow(start, due);
    try {
      const reservation = await apiFetch('/reservations/', {
        method: 'POST',
        body: JSON.stringify({
          equipment: equipment.id,
          start_at: times.start.toISOString(),
          due_at: times.due.toISOString(),
          notes,
          ...(user.is_staff ? { student: student.id } : {}),
        }),
      });
      onReserved(reservation);
    } catch (error) {
      setErrors(errorMessages(error));
      setSubmitting(false);
      if (error.body?.equipment) onConflict?.();
    }
  }

  const days = start && due && due >= start ? daysBetween(start, due) + 1 : 0;

  return (
    <section className="card reserve-panel" aria-label="Reserve this item">
      <h3>Reserve</h3>
      <p className="muted">
        Pick the days on the calendar or below. Collect from {hour(DESK_OPENS)} on the first day and return by{' '}
        {hour(DESK_CLOSES)} on the due date, at {equipment.location_name}. Up to {plural(equipment.max_loan_days, 'day')}.
      </p>
      <form className="form" onSubmit={handleSubmit} noValidate>
        {user.is_staff && (
          <SearchSelect
            id="student"
            label="Student"
            path="/students/"
            value={student}
            onChange={setStudent}
            renderOption={s => `${s.full_name} (${s.student_number || s.username})`}
          />
        )}
        <div className="date-fields">
          <div className="field">
            <label htmlFor="start-date">Start date</label>
            <input id="start-date" type="date" value={start ?? ''} min={todayISO()} onChange={e => update('start', e.target.value || null)} />
          </div>
          <div className="field">
            <label htmlFor="due-date">Due date</label>
            <input id="due-date" type="date" value={due ?? ''} min={start ?? todayISO()} onChange={e => update('due', e.target.value || null)} />
          </div>
        </div>
        {days > 0 && (
          <p className="muted">{plural(days, 'day')}: {formatDate(start)} to {formatDate(due)}.</p>
        )}
        <div className="field">
          <label htmlFor="notes">Notes for the desk</label>
          <input id="notes" value={notes} onChange={e => setNotes(e.target.value)} maxLength={500} placeholder="Optional, e.g. the module it's for" />
        </div>
        {errors.map(message => <p key={message} className="error" role="alert">{message}</p>)}
        <div className="actions">
          <button type="submit" disabled={submitting}>{submitting ? 'Reserving...' : 'Reserve'}</button>
        </div>
      </form>
    </section>
  );
}
