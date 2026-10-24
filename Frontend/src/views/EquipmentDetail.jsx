import React, { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import AvailabilityCalendar from '../components/AvailabilityCalendar';
import Icon from '../components/Icon';
import LoadState from '../components/LoadState';
import ReservePanel from '../components/ReservePanel';
import WeekNavigator from '../components/WeekNavigator';
import { addDays, dayBoundsISO, startOfWeek, toISODate } from '../dates';
import { CONDITION_LABELS, KIND_LABELS, plural } from '../format';
import { buildQuery, useApi } from '../hooks';
import { nextSelection } from '../rentals';
import { useSession } from '../session';

const WEEKS = 3;

export default function EquipmentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useSession();
  const item = useApi(`/equipment/${id}/`);
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [selection, setSelection] = useState({ start: null, due: null });

  // Busy ranges for the visible weeks, stretched to cover the chosen dates when they fall outside them.
  const visibleFrom = toISODate(weekStart);
  const visibleTo = toISODate(addDays(weekStart, WEEKS * 7 - 1));
  const from = selection.start && selection.start < visibleFrom ? selection.start : visibleFrom;
  const to = selection.due && selection.due > visibleTo ? selection.due : visibleTo;
  const availability = useApi(`/equipment/${id}/availability/${buildQuery({
    from: dayBoundsISO(from).start,
    to: dayBoundsISO(to).end,
  })}`);
  const busy = availability.data?.busy ?? [];

  const data = item.data;
  return (
    <LoadState loading={item.loading && !data} error={item.error}>
      {data && (
        <div>
          <section className="profile-header card">
            <span className={`kind-mark kind-mark-lg kind-${data.kind}`} aria-hidden="true">
              <Icon name={data.kind === 'sports' ? 'ball' : 'flask'} size={36} />
            </span>
            <div>
              <div className="page-header compact">
                <h2>{data.name}</h2>
                {user.is_staff && <Link className="button secondary-button" to={`/manage-equipment?edit=${data.id}`}>Edit item</Link>}
              </div>
              <div className="chips">
                <span className="chip">{data.asset_tag}</span>
                <span className="chip">{KIND_LABELS[data.kind]} · {data.category_name}</span>
                <span className="chip">{data.location_name}, {data.building}</span>
                <span className={`chip condition-${data.condition}`}>{CONDITION_LABELS[data.condition]}</span>
                <span className="chip">Loans up to {plural(data.max_loan_days, 'day')}</span>
                {!data.is_active && <span className="chip chip-warning">Retired</span>}
                {data.is_checked_out && <span className="chip chip-accent">Out on loan now</span>}
              </div>
              {data.description && <p className="prewrap muted">{data.description}</p>}
            </div>
          </section>

          <section className="card">
            <h3>Availability</h3>
            <p className="muted">
              Click a free day to start, then another to choose the due date.
              <span className="legend">
                <span className="legend-day free">Free</span>
                <span className="legend-day busy">Busy</span>
                <span className="legend-day selected">Chosen</span>
              </span>
            </p>
            <WeekNavigator weekStart={weekStart} onChange={setWeekStart} />
            <LoadState loading={availability.loading && !availability.data} error={availability.error}>
              <AvailabilityCalendar
                weekStart={weekStart}
                weeks={WEEKS}
                busy={busy}
                start={selection.start}
                due={selection.due}
                onSelect={iso => setSelection(nextSelection(selection, iso))}
              />
            </LoadState>
          </section>

          <ReservePanel
            equipment={data}
            busy={busy}
            selection={selection}
            onChange={setSelection}
            onReserved={reservation => navigate(`/reservations/${reservation.id}`)}
            onConflict={availability.reload}
          />
        </div>
      )}
    </LoadState>
  );
}
