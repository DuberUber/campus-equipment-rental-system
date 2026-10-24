import React, { useState } from 'react';
import { apiFetch } from '../api';
import { CONDITION_LABELS, errorMessages } from '../format';

// Staff take a checked-out item back and record the condition it came back in.
export default function ReturnForm({ reservation, onReturned, onCancel }) {
  const [condition, setCondition] = useState('good');
  const [notes, setNotes] = useState('');
  const [errors, setErrors] = useState([]);
  const [saving, setSaving] = useState(false);
  const fieldId = `return-condition-${reservation.id}`;

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setErrors([]);
    try {
      const updated = await apiFetch(`/reservations/${reservation.id}/return/`, {
        method: 'POST',
        body: JSON.stringify({ return_condition: condition, notes }),
      });
      onReturned(updated);
    } catch (error) {
      setErrors(errorMessages(error));
      setSaving(false);
    }
  }

  return (
    <form className="form inline-form return-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor={fieldId}>Condition on return</label>
        <select id={fieldId} value={condition} onChange={e => setCondition(e.target.value)}>
          {Object.entries(CONDITION_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      <div className="field grow">
        <label htmlFor={`${fieldId}-notes`}>Notes</label>
        <input id={`${fieldId}-notes`} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Optional, e.g. a scuffed case" />
      </div>
      <button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Confirm return'}</button>
      {onCancel && <button type="button" className="secondary" onClick={onCancel}>Cancel</button>}
      {errors.map(message => <p key={message} className="error">{message}</p>)}
    </form>
  );
}
