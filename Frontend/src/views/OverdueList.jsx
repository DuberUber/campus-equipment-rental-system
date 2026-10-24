import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import LoadState from '../components/LoadState';
import Pagination from '../components/Pagination';
import ReturnForm from '../components/ReturnForm';
import { formatDateTime, overdueText } from '../format';
import { usePaginatedList } from '../hooks';

// Everything still checked out after its due time, longest overdue first (staff).
export default function OverdueList() {
  const overdue = usePaginatedList('/reservations/overdue/');
  const [returningId, setReturningId] = useState(null);

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Overdue returns</h2>
          <p className="muted">Students with an overdue item can't reserve anything else until it comes back.</p>
        </div>
      </div>
      <LoadState loading={overdue.loading && overdue.rows.length === 0} error={overdue.error}>
        {overdue.rows.length === 0 ? <p className="muted">Nothing is overdue.</p> : (
          <table>
            <thead>
              <tr><th>Item</th><th>Student</th><th>Due</th><th>Overdue</th><th>Return to</th><th /></tr>
            </thead>
            <tbody>
              {overdue.rows.map(r => (
                <tr key={r.id} className="overdue">
                  <td><Link to={`/reservations/${r.id}`}>{r.equipment_name}</Link> <span className="muted">{r.asset_tag}</span></td>
                  <td>
                    <Link to={`/students/${r.student}`}>{r.student_name}</Link>
                    <br /><span className="muted">{r.student_number} · {r.student_email}</span>
                  </td>
                  <td>{formatDateTime(r.due_at)}</td>
                  <td><strong className="overdue-text">{overdueText(r.due_at)}</strong></td>
                  <td>{r.location_name}</td>
                  <td>
                    {returningId === r.id ? (
                      <ReturnForm reservation={r} onReturned={() => { setReturningId(null); overdue.reload(); }} onCancel={() => setReturningId(null)} />
                    ) : (
                      <button type="button" onClick={() => setReturningId(r.id)}>Return</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <Pagination page={overdue.page} count={overdue.count} onChange={overdue.setPage} />
      </LoadState>
    </div>
  );
}
