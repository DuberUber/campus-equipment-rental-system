import React from 'react';
import { errorMessages } from '../format';

// Shared loading / error placeholder for pages backed by useApi.
export default function LoadState({ loading, error, children }) {
  if (error) {
    return <p className="error">{errorMessages(error).join(' ')}</p>;
  }
  if (loading) {
    return <p className="muted">Loading...</p>;
  }
  return children;
}
