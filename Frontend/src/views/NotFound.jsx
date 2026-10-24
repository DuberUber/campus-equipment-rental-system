import React from 'react';
import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div>
      <h2>Page not found</h2>
      <p><Link to="/">Back to the start page</Link></p>
    </div>
  );
}
