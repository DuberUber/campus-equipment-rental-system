export const API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/api';
export const ADMIN_URL = `${API_URL.replace(/\/api\/?$/, '')}/admin/`;

const TOKEN_KEY = 'equipmentrental.authToken';

export const auth = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: token => localStorage.setItem(TOKEN_KEY, token),
  clearToken: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(status, body) {
    super(`Request failed with status ${status}`);
    this.status = status;
    this.body = body;
  }
}

// `path` is relative to API_URL, or an absolute URL such as a paginated response's `next` link.
export async function apiFetch(path, options = {}) {
  const token = auth.getToken();
  const url = /^https?:\/\//.test(path) ? path : `${API_URL}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...options.headers,
    },
  });
  if (response.status === 401) {
    // Token missing, expired or revoked: send the user back to the login screen.
    auth.clearToken();
    window.dispatchEvent(new Event('auth:logout'));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body);
  }
  return response.status === 204 ? null : response.json();
}

// List endpoints are paginated ({count, next, previous, results}).
export async function fetchPage(path, page = 1) {
  const separator = path.includes('?') ? '&' : '?';
  return apiFetch(`${path}${separator}page=${page}`);
}

export async function fetchList(path) {
  const data = await fetchPage(path);
  return data.results;
}

// Follow `next` links to collect every row, e.g. every category for a filter (capped at maxPages).
export async function fetchAll(path, maxPages = 10) {
  const rows = [];
  let next = path;
  for (let page = 0; next && page < maxPages; page += 1) {
    const data = await apiFetch(next);
    rows.push(...data.results);
    next = data.next;
  }
  return rows;
}

export async function login(username, password) {
  auth.clearToken();
  const { token } = await apiFetch('/auth/token/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  auth.setToken(token);
}

export async function register(details) {
  auth.clearToken();
  const { token, user } = await apiFetch('/auth/register/', {
    method: 'POST',
    body: JSON.stringify(details),
  });
  auth.setToken(token);
  return user;
}

export async function logout() {
  try {
    await apiFetch('/auth/logout/', { method: 'POST' });
  } catch {
    // The token is discarded locally either way.
  } finally {
    auth.clearToken();
  }
}
