import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiFetch } from '../api';
import LoadState from '../components/LoadState';
import ReturnForm from '../components/ReturnForm';
import StatusBadge from '../components/StatusBadge';
import { CONDITION_LABELS, errorMessages, formatDateTime, overdueText } from '../format';
import { useApi } from '../hooks';
import { displayStatus } from '../rentals';
import { useSession } from '../session';

const notRecorded = <span className="muted">Not yet</span>;

export default function ReservationDetail() {
  const { id } = useParams();
  const { user } = useSession();
  const { data: reservation, loading, error, reload } = useApi(`/reservations/${id}/`);
  const [actionErrors, setActionErrors] = useState([]);
  const [returning, setReturning] = useState(false);

  async function run(action) {
    setActionErrors([]);
    try {
      await apiFetch(`/reservations/${id}/${action}/`, { method: 'POST' });
      reload();
    } catch (err) {
      setActionErrors(errorMessages(err));
    }
  }

  function cancel() {
    if (window.confirm('Cancel this reservation?')) run('cancel');
  }

  if (!reservation) {
    return <LoadState loading={loading} error={error} />;
  }

  const r = reservation;
  const staff = user.is_staff;
  return (
    <div>
      <div className="page-header">
        <h2>{r.equipment_name} <StatusBadge status={displayStatus(r)} /></h2>
        <Link to={staff ? '/desk' : '/rentals'}>{staff ? '← Equipment desk' : '← My rentals'}</Link>
      </div>

      {r.is_overdue && (
        <div className="alert-banner" role="alert">
          {overdueText(r.due_at)}: due back {formatDateTime(r.due_at)} at {r.location_name}.
        </div>
      )}

      <div className="grid">
        <section className={`card${r.is_overdue ? ' overdue' : ''}`}>
          <h3>Reservation</h3>
          <dl className="details">
            <dt>Item</dt>
            <dd><Link to={`/equipment/${r.equipment}`}>{r.equipment_name}</Link> <span className="muted">({r.asset_tag})</span></dd>
            <dt>Category</dt>
            <dd>{r.category_name}</dd>
            <dt>Collect from</dt>
            <dd>{r.location_name}, {r.building}</dd>
            <dt>From</dt>
            <dd>{formatDateTime(r.start_at)}</dd>
            <dt>Due back</dt>
            <dd>{formatDateTime(r.due_at)}</dd>
            <dt>Notes</dt>
            <dd className="prewrap">{r.notes || <span className="muted">None</span>}</dd>
            <dt>Reserved</dt>
            <dd>{formatDateTime(r.created_at)}</dd>
          </dl>
          <div className="actions">
            {staff && r.status === 'reserved' && <button type="button" onClick={() => run('checkout')}>Check out</button>}
            {staff && r.status === 'checked_out' && !returning && (
              <button type="button" onClick={() => setReturning(true)}>Return</button>
            )}
            {r.status === 'reserved' && <button type="button" className="danger" onClick={cancel}>Cancel reservation</button>}
          </div>
          {returning && r.status === 'checked_out' && (
            <ReturnForm reservation={r} onReturned={() => { setReturning(false); reload(); }} onCancel={() => setReturning(false)} />
          )}
          {actionErrors.map(message => <p key={message} className="error">{message}</p>)}
        </section>

        <section className="card">
          <h3>Desk record</h3>
          <dl className="details">
            {staff && (
              <>
                <dt>Student</dt>
                <dd>
                  <Link to={`/students/${r.student}`}>{r.student_name}</Link>
                  {r.student_number && <span className="muted"> · {r.student_number}</span>}
                </dd>
                <dt>Email</dt>
                <dd>{r.student_email}</dd>
              </>
            )}
            <dt>Checked out</dt>
            <dd>{r.checked_out_at ? `${formatDateTime(r.checked_out_at)} by ${r.checked_out_by_name ?? 'staff'}` : notRecorded}</dd>
            <dt>Returned</dt>
            <dd>
              {r.returned_at ? `${formatDateTime(r.returned_at)} by ${r.returned_by_name ?? 'staff'}` : notRecorded}
              {r.returned_late && <span className="late-text"> (late)</span>}
            </dd>
            <dt>Condition</dt>
            <dd>{r.return_condition ? CONDITION_LABELS[r.return_condition] : notRecorded}</dd>
          </dl>
        </section>
      </div>
    </div>
  );
}
