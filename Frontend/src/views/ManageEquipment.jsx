import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiFetch } from '../api';
import LoadState from '../components/LoadState';
import Pagination from '../components/Pagination';
import { CONDITION_LABELS, KIND_LABELS, errorMessages } from '../format';
import { buildQuery, useApi, useDebouncedValue, usePaginatedList } from '../hooks';

const EMPTY_FORM = {
  name: '', category: '', location: '', asset_tag: '', description: '', condition: 'good', max_loan_days: 7, is_active: true,
};

const toForm = item => ({
  name: item.name, category: String(item.category), location: String(item.location), asset_tag: item.asset_tag,
  description: item.description, condition: item.condition, max_loan_days: item.max_loan_days, is_active: item.is_active,
});

// Staff add equipment to the catalogue and edit it (?edit=<id> opens an item in the form).
export default function ManageEquipment() {
  const [searchParams, setSearchParams] = useSearchParams();
  const editId = searchParams.get('edit');
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const equipment = usePaginatedList(`/equipment/${buildQuery({ search: debouncedSearch, kind, ordering: 'name' })}`);
  const categories = useApi('/categories/?page_size=100');
  const locations = useApi('/locations/?page_size=100');
  const editing = useApi(editId ? `/equipment/${editId}/` : null);

  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState([]);
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setErrors([]);
    if (!editId) setForm(EMPTY_FORM);
    else if (editing.data) setForm(toForm(editing.data));
  }, [editId, editing.data]);

  const update = field => event => {
    const { type, checked, value } = event.target;
    setForm({ ...form, [field]: type === 'checkbox' ? checked : value });
  };

  function startNew() {
    setMessage('');
    setSearchParams({});
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setErrors([]);
    setMessage('');
    const body = JSON.stringify({
      ...form, category: Number(form.category), location: Number(form.location), max_loan_days: Number(form.max_loan_days),
    });
    try {
      const saved = editId
        ? await apiFetch(`/equipment/${editId}/`, { method: 'PATCH', body })
        : await apiFetch('/equipment/', { method: 'POST', body });
      setMessage(`${editId ? 'Saved' : 'Added'} ${saved.name} (${saved.asset_tag}).`);
      equipment.reload();
      if (editId) editing.reload();
      else setForm(EMPTY_FORM);
    } catch (error) {
      setErrors(errorMessages(error));
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete ${form.name}? Items with rental history can't be deleted; mark them inactive instead.`)) return;
    setErrors([]);
    try {
      await apiFetch(`/equipment/${editId}/`, { method: 'DELETE' });
      setMessage(`Deleted ${form.name}.`);
      equipment.reload();
      setSearchParams({});
    } catch (error) {
      setErrors(error.status === 409
        ? ['This item has rental history, so it cannot be deleted. Untick "Available to reserve" to retire it instead.']
        : errorMessages(error));
    }
  }

  const categoryList = categories.data?.results ?? [];
  const locationList = locations.data?.results ?? [];

  return (
    <div>
      <div className="page-header">
        <h2>Manage equipment</h2>
        {editId && <button type="button" onClick={startNew}>Add new item</button>}
      </div>

      <section className="card">
        <h3>{editId ? `Edit ${editing.data?.name ?? 'item'}` : 'Add an item'}</h3>
        <form className="form equipment-form" onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="eq-name">Name</label>
              <input id="eq-name" value={form.name} onChange={update('name')} required maxLength={255} />
            </div>
            <div className="field">
              <label htmlFor="eq-tag">Asset tag</label>
              <input id="eq-tag" value={form.asset_tag} onChange={update('asset_tag')} required maxLength={30} />
            </div>
            <div className="field">
              <label htmlFor="eq-category">Category</label>
              <select id="eq-category" value={form.category} onChange={update('category')} required>
                <option value="">Choose a category</option>
                {categoryList.map(c => <option key={c.id} value={c.id}>{c.name} ({KIND_LABELS[c.kind]})</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="eq-location">Location</label>
              <select id="eq-location" value={form.location} onChange={update('location')} required>
                <option value="">Choose a location</option>
                {locationList.map(l => <option key={l.id} value={l.id}>{l.name} ({l.building})</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="eq-condition">Condition</label>
              <select id="eq-condition" value={form.condition} onChange={update('condition')}>
                {Object.entries(CONDITION_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="eq-days">Longest loan (days)</label>
              <input id="eq-days" type="number" min={1} max={90} value={form.max_loan_days} onChange={update('max_loan_days')} required />
            </div>
          </div>
          <div className="field">
            <label htmlFor="eq-description">Description</label>
            <textarea id="eq-description" rows={3} value={form.description} onChange={update('description')} />
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={form.is_active} onChange={update('is_active')} />
            Available to reserve (untick to retire the item)
          </label>
          {message && <p className="success">{message}</p>}
          {errors.map(text => <p key={text} className="error">{text}</p>)}
          <div className="actions">
            <button type="submit" disabled={saving}>{saving ? 'Saving...' : editId ? 'Save changes' : 'Add item'}</button>
            {editId && <button type="button" className="danger" onClick={remove}>Delete</button>}
            {editId && <Link to={`/equipment/${editId}`}>View item</Link>}
          </div>
        </form>
      </section>

      <section className="card">
        <h3>Catalogue ({equipment.count})</h3>
        <div className="filters">
          <input type="search" placeholder="Search by name or asset tag..." value={search} onChange={e => setSearch(e.target.value)} aria-label="Search catalogue" />
          <select value={kind} onChange={e => setKind(e.target.value)} aria-label="Type">
            <option value="">Lab and sports</option>
            <option value="lab">Lab</option>
            <option value="sports">Sports</option>
          </select>
        </div>
        <LoadState loading={equipment.loading && equipment.rows.length === 0} error={equipment.error}>
          <table>
            <thead>
              <tr><th>Asset tag</th><th>Name</th><th>Category</th><th>Location</th><th>Condition</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {equipment.rows.map(item => (
                <tr key={item.id} className={String(item.id) === editId ? 'selected-row' : ''}>
                  <td>{item.asset_tag}</td>
                  <td><Link to={`/equipment/${item.id}`}>{item.name}</Link></td>
                  <td>{item.category_name}</td>
                  <td>{item.location_name}</td>
                  <td><span className={`chip condition-${item.condition}`}>{CONDITION_LABELS[item.condition]}</span></td>
                  <td>{!item.is_active ? 'Retired' : item.is_checked_out ? 'On loan' : 'In stock'}</td>
                  <td>
                    <button type="button" className="link" onClick={() => { setMessage(''); setSearchParams({ edit: item.id }); }}>
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={equipment.page} count={equipment.count} onChange={equipment.setPage} />
        </LoadState>
      </section>
    </div>
  );
}
