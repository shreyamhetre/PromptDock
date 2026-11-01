import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

// Fetch `path` and re-fetch when it (or `reloadKey`) changes.
export function useApi(path, params, reloadKey = 0) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const paramsKey = JSON.stringify(params || {});

  const load = useCallback(() => {
    if (!path) return;
    setState((s) => ({ ...s, loading: true }));
    api(path, { params: JSON.parse(paramsKey) })
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => setState({ data: null, error, loading: false }));
  }, [path, paramsKey]);

  useEffect(load, [load, reloadKey]);
  return { ...state, reload: load };
}

export function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
