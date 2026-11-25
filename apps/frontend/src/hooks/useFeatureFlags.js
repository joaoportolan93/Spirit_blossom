/**
 * useFeatureFlags — hook para consumir feature flags do backend.
 *
 * Cache em sessionStorage para evitar múltiplas requisições.
 * Degradação graciosa: em caso de erro, retorna {} (todas as flags false por default).
 */

import { useState, useEffect } from "react";
import { api } from "../services/api";

const CACHE_KEY = "feature_flags_cache";
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutos

function readCache() {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const { flags, ts } = JSON.parse(raw);
    if (Date.now() - ts < CACHE_TTL_MS) return flags;
  } catch {
    // ignore
  }
  return null;
}

function writeCache(flags) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ flags, ts: Date.now() }));
  } catch {
    // ignore
  }
}

export function useFeatureFlags() {
  const [flags, setFlags] = useState(() => readCache() || {});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const cached = readCache();
    if (cached) {
      setFlags(cached);
      return;
    }

    let isMounted = true;
    setLoading(true);

    api
      .get("/api/feature-flags/")
      .then((res) => {
        if (isMounted && res.data?.flags) {
          setFlags(res.data.flags);
          writeCache(res.data.flags);
        }
      })
      .catch(() => {
        // Degradação graciosa — flags permanecem {} (tudo false)
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  /**
   * isEnabled(key) — verifica se uma flag está ativa.
   * Default seguro: false se a flag não existir.
   */
  function isEnabled(key) {
    return flags[key] === true;
  }

  return { flags, isEnabled, loading };
}

export default useFeatureFlags;
