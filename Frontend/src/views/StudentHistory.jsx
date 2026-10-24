import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Avatar from '../components/Avatar';
import LoadState from '../components/LoadState';
import Pagination from '../components/Pagination';
import ReservationRow from '../components/ReservationRow';
import { buildQuery, useApi, usePaginatedList } from '../hooks';

const FILTERS = [
  { key: '', label: 'All' },
  { key: 'current', label: 'Current' },
  { key: 'upcoming', label: 'Upcoming' },
  { key: 'past', label: 'Past' },
];

export default function StudentHistory() {
  const { id } = useParams();
  const [when, setWhen] = useState('');
  const { data: student, loading, error } = useApi(`/students/${id}/`);
  const history = usePaginatedList(`/students/${id}/history/${buildQuery({ when })}`);

  return (
    <LoadState loading={loading && !student} error={error}>
      {student && (
        <div>
          <div className="page-header">
            <h2 className="title-with-avatar"><Avatar name={student.full_name} />{student.full_name}</h2>
            <Link to="/students">← Students</Link>
          </div>

          <section className="card">
            <dl className="details">
              <dt>Student number</dt>
              <dd>{student.student_number || <span className="muted">Not given</span>}</dd>
              <dt>Course</dt>
              <dd>{student.course || <span className="muted">Not given</span>}{student.year && `, year ${student.year}`}</dd>
              <dt>Email</dt>
              <dd>{student.email}</dd>
              <dt>Username</dt>
              <dd>{student.username}</dd>
              <dt>Active now</dt>
              <dd>
                {student.active_reservations}
                {student.overdue_reservations > 0 && (
                  <strong className="overdue-text"> · {student.overdue_reservations} overdue</strong>
                )}
              </dd>
            </dl>
          </section>

          <div className="section-header">
            <h3>Rental history ({history.count})</h3>
            <div className="tabs" role="tablist">
              {FILTERS.map(f => (
                <button
                  key={f.key || 'all'}
                  type="button"
                  role="tab"
                  aria-selected={f.key === when}
                  className={`tab${f.key === when ? ' active' : ''}`}
                  onClick={() => setWhen(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <LoadState loading={history.loading && history.rows.length === 0} error={history.error}>
            {history.rows.length === 0 ? <p className="muted">No reservations.</p> : (
              <ul className="rental-list">
                {history.rows.map(r => <ReservationRow key={r.id} reservation={r} />)}
              </ul>
            )}
            <Pagination page={history.page} count={history.count} onChange={history.setPage} />
          </LoadState>
        </div>
      )}
    </LoadState>
  );
}
