import React from 'react';
import { STATUS_LABELS } from '../format';

// A reservation status (reserved, checked_out, returned, cancelled) or "overdue".
export default function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}
