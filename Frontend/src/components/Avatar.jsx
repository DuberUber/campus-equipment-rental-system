import React from 'react';

// Initials in a tinted circle; the tint is derived from the name so each person keeps their colour.
export function initials(name = '') {
  const words = name.split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? '') + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase() || '?';
}

export function nameHue(name = '') {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) % 360;
  return hash;
}

export default function Avatar({ name, size = 'md' }) {
  return (
    <span className={`avatar avatar-${size}`} style={{ '--avatar-hue': nameHue(name) }} aria-hidden="true">
      {initials(name)}
    </span>
  );
}
