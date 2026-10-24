import React from 'react';
import { Link } from 'react-router-dom';
import { toISODate } from '../dates';
import { formatDateTime, overdueText } from '../format';
import { displayStatus } from '../rentals';
import DateTile from './DateTile';
import StatusBadge from './StatusBadge';

// One reservation in a list (my rentals, the desk, a student's history). Overdue items are highlighted.
export default function ReservationRow({ reservation, showStudent = false, children = null }) {
  const r = reservation;
  return (
    <li className={`card rental-item${r.is_overdue ? ' overdue' : ''}`} data-testid={`reservation-${r.id}`}>
      <DateTile date={toISODate(new Date(r.start_at))} />
      <div className="rental-what">
        <Link to={`/reservations/${r.id}`}>{r.equipment_name}</Link>
        <span className="muted">{r.asset_tag} · {r.location_name}, {r.building}</span>
        {showStudent && (
          <span>
            {r.student_name}
            {r.student_number && <span className="muted"> · {r.student_number}</span>}
          </span>
        )}
      </div>
      <div className="rental-when">
        <span>From {formatDateTime(r.start_at)}</span>
        <span>Due {formatDateTime(r.due_at)}</span>
        {r.is_overdue && <strong className="overdue-text">{overdueText(r.due_at)}</strong>}
        {r.returned_late && <span className="late-text">Returned late</span>}
      </div>
      <StatusBadge status={displayStatus(r)} />
      {children && <div className="rental-actions">{children}</div>}
    </li>
  );
}
