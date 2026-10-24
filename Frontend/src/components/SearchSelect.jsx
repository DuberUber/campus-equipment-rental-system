import React, { useEffect, useState } from 'react';
import { fetchList } from '../api';

// A select whose options come from a searchable, paginated endpoint, so it scales past one page of rows.
export default function SearchSelect({ id, label, path, value, onChange, renderOption }) {
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState([]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchList(`${path}?search=${encodeURIComponent(query)}`)
        .then(setOptions)
        .catch(() => setOptions([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [path, query]);

  // Keep the current choice visible even when it isn't in the latest search results.
  const visible = value && !options.some(option => option.id === value.id) ? [value, ...options] : options;

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        type="search"
        placeholder={`Search ${label.toLowerCase()}...`}
        value={query}
        onChange={e => setQuery(e.target.value)}
      />
      <select
        id={id}
        value={value?.id ?? ''}
        onChange={e => onChange(visible.find(option => String(option.id) === e.target.value) ?? null)}
        required
      >
        <option value="">Select {label.toLowerCase()}</option>
        {visible.map(option => (
          <option key={option.id} value={option.id}>{renderOption(option)}</option>
        ))}
      </select>
    </div>
  );
}
