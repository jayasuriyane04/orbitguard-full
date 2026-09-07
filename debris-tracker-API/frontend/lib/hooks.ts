"use client";

import { useEffect, useState, useRef } from "react";
import { ApiError } from "@/lib/api";

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Minimal data-fetching hook (no external dependency). `deps` controls when
 * a fresh fetch runs, same as a manual useEffect dependency list would.
 */
export function useApiData<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = []
): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  // Keep the latest fetcher in a ref so callers can pass a fresh inline
  // closure each render without it needing to be a dependency (it would
  // otherwise cause a refetch loop since arrow functions are never `===`
  // across renders). Updated in an effect, never during render.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- standard "reset loading/error before fetch" pattern
    setLoading(true);
    setError(null);

    fetcherRef
      .current()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError) {
          setError(`${err.status}: ${err.message}`);
        } else if (err instanceof TypeError) {
          setError(
            "Can't reach the ORBITGUARD API. Confirm the backend is running and NEXT_PUBLIC_API_BASE_URL is set."
          );
        } else {
          setError(String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadToken]);

  return { data, loading, error, reload: () => setReloadToken((t) => t + 1) };
}
