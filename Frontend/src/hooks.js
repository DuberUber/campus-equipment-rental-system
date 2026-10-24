import { useCallback, useEffect, useState } from 'react';
import { apiFetch, fetchAll } from './api';

// Matches the API's PAGE_SIZE.
export const PAGE_SIZE = 25;

function useRequest(key, request) {
  const [state, setState] = useState({ data: null, error: null, loading: Boolean(key) });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!key) return undefined;
    let cancelled = false;
    setState(previous => ({ ...previous, loading: true, error: null }));
    request(key)
      .then(data => { if (!cancelled) setState({ data, error: null, loading: false }); })
      .catch(error => { if (!cancelled) setState({ data: null, error, loading: false }); });
    return () => { cancelled = true; };
    // `request` is a module-level function; the key identifies the request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, version]);

  const reload = useCallback(() => setVersion(v => v + 1), []);
  return { ...state, reload };
}

// Fetch `path` whenever it changes; pass null to skip. Returns {data, error, loading, reload}.
export function useApi(path) {
  return useRequest(path, apiFetch);
}

// Every row of a paginated endpoint (follows `next` links); pass null to skip.
export function useAllPages(path) {
  const result = useRequest(path, fetchAll);
  return { ...result, rows: result.data ?? [] };
}

// Page through a paginated list endpoint; the page resets when the base path (e.g. filters) changes.
export function usePaginatedList(path) {
  const [pageState, setPageState] = useState({ path, page: 1 });
  const page = pageState.path === path ? pageState.page : 1;
  const setPage = useCallback(next => setPageState({ path, page: next }), [path]);

  const separator = path?.includes('?') ? '&' : '?';
  const result = useApi(path ? `${path}${separator}page=${page}` : null);
  return {
    ...result,
    rows: result.data?.results ?? [],
    count: result.data?.count ?? 0,
    page,
    setPage,
  };
}

export function buildQuery(params) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined),
  ).toString();
  return query ? `?${query}` : '';
}

// Delay a fast-changing value (e.g. a search box) so we don't fire a request per keystroke.
export function useDebouncedValue(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
