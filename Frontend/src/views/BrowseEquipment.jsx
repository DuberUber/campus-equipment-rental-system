import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import Icon from '../components/Icon';
import LoadState from '../components/LoadState';
import Pagination from '../components/Pagination';
import { addDays, reservationWindow, todayISO, toISODate } from '../dates';
import { CONDITION_LABELS, formatDate, plural } from '../format';
import { buildQuery, useApi, useDebouncedValue, usePaginatedList } from '../hooks';

const TABS = [
  { kind: 'lab', label: 'Lab', icon: 'flask', blurb: 'Oscilloscopes, multimeters, Raspberry Pi kits, microscopes and cameras.' },
  { kind: 'sports', label: 'Sports', icon: 'ball', blurb: 'Footballs, tennis rackets, hurleys, training bibs and cones.' },
];

export default function BrowseEquipment() {
  const [kind, setKind] = useState('lab');
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const [range, setRange] = useState({ from: '', to: '' });
  const debouncedSearch = useDebouncedValue(search);
  const tab = TABS.find(t => t.kind === kind);

  const categories = useApi(`/categories/${buildQuery({ kind, page_size: 100 })}`);
  // Only filter by availability once both dates make a valid range (the same times a reservation would use).
  const rangeValid = range.from && range.to && range.to >= range.from && range.from >= todayISO();
  const freeWindow = rangeValid ? reservationWindow(range.from, range.to) : null;
  const equipment = usePaginatedList(`/equipment/${buildQuery({
    kind,
    category,
    search: debouncedSearch,
    available_from: freeWindow?.start.toISOString(),
    available_to: freeWindow?.due.toISOString(),
    ordering: 'name',
  })}`);

  function chooseTab(next) {
    setKind(next);
    setCategory('');
  }

  const updateRange = field => event => setRange({ ...range, [field]: event.target.value });
  const quickRange = days => setRange({ from: todayISO(), to: toISODate(addDays(new Date(), days - 1)) });

  return (
    <div>
      <section className="hero-banner">
        <p className="eyebrow">Equipment desk</p>
        <h2>Browse equipment</h2>
        <p>Reserve lab kit and sports gear for your project, practical or match, then collect it from the desk.</p>
        <div className="tabs hero-tabs" role="tablist" aria-label="Equipment type">
          {TABS.map(t => (
            <button
              key={t.kind}
              type="button"
              role="tab"
              aria-selected={t.kind === kind}
              className={`tab${t.kind === kind ? ' active' : ''}`}
              onClick={() => chooseTab(t.kind)}
            >
              <Icon name={t.icon} size={18} />{t.label}
            </button>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="filters">
          <input
            type="search"
            placeholder="Search by name or asset tag..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search equipment"
          />
          <select value={category} onChange={e => setCategory(e.target.value)} aria-label="Category">
            <option value="">All {tab.label.toLowerCase()} categories</option>
            {(categories.data?.results ?? []).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <fieldset className="date-range">
          <legend>Show what's free</legend>
          <div className="field">
            <label htmlFor="free-from">From</label>
            <input id="free-from" type="date" value={range.from} min={todayISO()} onChange={updateRange('from')} />
          </div>
          <div className="field">
            <label htmlFor="free-to">To</label>
            <input id="free-to" type="date" value={range.to} min={range.from || todayISO()} onChange={updateRange('to')} />
          </div>
          <div className="quick-ranges">
            <button type="button" className="secondary" onClick={() => quickRange(1)}>Today</button>
            <button type="button" className="secondary" onClick={() => quickRange(3)}>Next 3 days</button>
            <button type="button" className="secondary" onClick={() => quickRange(7)}>This week</button>
            {(range.from || range.to) && (
              <button type="button" className="link" onClick={() => setRange({ from: '', to: '' })}>Clear dates</button>
            )}
          </div>
        </fieldset>
        {range.from && range.to && !rangeValid && (
          <p className="error">Choose a range that starts today or later and ends on or after its start.</p>
        )}
      </section>

      <h3 className="section-title">
        {rangeValid
          ? `${tab.label} equipment free from ${formatDate(range.from)} to ${formatDate(range.to)} (${equipment.count})`
          : `${tab.label} equipment (${equipment.count})`}
      </h3>
      <p className="muted section-blurb">{tab.blurb}</p>
      <LoadState loading={equipment.loading && equipment.rows.length === 0} error={equipment.error}>
        {equipment.rows.length === 0 && (
          <p className="muted">{rangeValid ? 'Nothing matching is free for those dates. Try other dates.' : 'No equipment matches your search.'}</p>
        )}
        <div className="cards">
          {equipment.rows.map(item => (
            <Link key={item.id} className="card card-link equipment-card" to={`/equipment/${item.id}`}>
              <span className="equipment-card-head">
                <span className={`kind-mark kind-${item.kind}`} aria-hidden="true">
                  <Icon name={item.kind === 'sports' ? 'ball' : 'flask'} size={20} />
                </span>
                <span>
                  <strong>{item.name}</strong>
                  <small className="muted">{item.asset_tag} · {item.category_name}</small>
                </span>
              </span>
              {item.description && <p className="muted clamp">{item.description}</p>}
              <span className="chips">
                <span className="chip">{item.location_name}</span>
                <span className={`chip condition-${item.condition}`}>{CONDITION_LABELS[item.condition]}</span>
                <span className="chip">Up to {plural(item.max_loan_days, 'day')}</span>
              </span>
              <small className={rangeValid ? 'free-tag' : item.is_checked_out ? 'out-tag' : 'free-tag'}>
                {rangeValid ? 'Free for your dates' : item.is_checked_out ? 'Out on loan now' : 'On the shelf now'}
              </small>
            </Link>
          ))}
        </div>
        <Pagination page={equipment.page} count={equipment.count} onChange={equipment.setPage} />
      </LoadState>
    </div>
  );
}
