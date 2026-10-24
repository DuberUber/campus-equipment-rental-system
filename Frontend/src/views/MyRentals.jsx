import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../api';
import Icon from '../components/Icon';
import LoadState from '../components/LoadState';
import Pagination from '../components/Pagination';
import ReservationRow from '../components/ReservationRow';
import { errorMessages, plural } from '../format';
import { buildQuery, useApi, usePaginatedList } from '../hooks';

const TABS = [
  { key: 'current', label: 'Current', ordering: 'due_at', empty: 'Nothing out with you right now.' },
  { key: 'upcoming', label: 'Upcoming', ordering: 'start_at', empty: 'You have no upcoming reservations.' },
  { key: 'past', label: 'History', ordering: '-start_at', empty: 'Your rental history is empty.' },
];

export default function MyRentals() {
  const [tabKey, setTabKey] = useState('current');
  const tab = TABS.find(t => t.key === tabKey);
  const rentals = usePaginatedList(`/me/history/${buildQuery({ when: tab.key, ordering: tab.ordering })}`);
  const overdue = useApi('/me/history/?overdue=true');
  const [errors, setErrors] = useState([]);
  const overdueCount = overdue.data?.count ?? 0;

  async function cancel(reservation) {
    if (!window.confirm(`Cancel your reservation of ${reservation.equipment_name}?`)) return;
    setErrors([]);
    try {
      await apiFetch(`/reservations/${reservation.id}/cancel/`, { method: 'POST' });
      rentals.reload();
    } catch (error) {
      setErrors(errorMessages(error));
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>My rentals</h2>
        <Link className="button" to="/equipment">Reserve equipment</Link>
      </div>

      {overdueCount > 0 && (
        <div className="alert-banner" role="alert">
          <Icon name="alert" />
          <span>
            You have {plural(overdueCount, 'overdue item')}. Please return {overdueCount === 1 ? 'it' : 'them'} to the
            desk: you can't reserve anything else until then.
          </span>
        </div>
      )}

      <div className="tabs" role="tablist">
        {TABS.map(t => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={t.key === tabKey}
            className={`tab${t.key === tabKey ? ' active' : ''}`}
            onClick={() => setTabKey(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {errors.map(message => <p key={message} className="error">{message}</p>)}
      <LoadState loading={rentals.loading && rentals.rows.length === 0} error={rentals.error}>
        {rentals.rows.length === 0 ? (
          <p className="muted">{tab.empty}</p>
        ) : (
          <ul className="rental-list">
            {rentals.rows.map(reservation => (
              <ReservationRow key={reservation.id} reservation={reservation}>
                {reservation.status === 'reserved' && tab.key !== 'past' && (
                  <button type="button" className="danger" onClick={() => cancel(reservation)}>Cancel</button>
                )}
              </ReservationRow>
            ))}
          </ul>
        )}
        <Pagination page={rentals.page} count={rentals.count} onChange={rentals.setPage} />
      </LoadState>
    </div>
  );
}
