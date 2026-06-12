/**
 * TanStack Query hooks — the server-state layer. These cache by query key so a
 * single search is fetched once and shared across every view, replacing the
 * per-rerun re-execution and @st.cache_data of the Streamlit app.
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { getSearch, getSources, getTaxonomy } from "./api";
import { keyForApiName } from "./sources";
import { sourceOf } from "./fields";
import { useSearchStore } from "./store";
import type { SearchResponse, SpeciesRecord } from "./types";

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: getSources,
  });
}

/** Raw search for the currently-submitted query. */
export function useSearch() {
  const query = useSearchStore((s) => s.submittedQuery);

  return useQuery<SearchResponse>({
    queryKey: ["search", query],
    queryFn: () => getSearch(query),
    enabled: query.length > 0,
  });
}

export function useTaxonomy() {
  const query = useSearchStore((s) => s.submittedQuery);

  return useQuery({
    queryKey: ["taxonomy", query],
    queryFn: () => getTaxonomy(query),
    enabled: query.length > 0,
  });
}

/**
 * The set of source keys currently active (the user's manual selection).
 * `queriedSources` is the full list returned by the server, used for the
 * "keep unknown sources" fallback in useFilteredRecords.
 */
export function useActiveSourceKeys(): {
  keys: string[];
  queriedSources: string[];
} {
  const search = useSearch();
  const selectedSources = useSearchStore((s) => s.selectedSources);

  const queriedSources = search.data?.sources ?? [];
  return { keys: selectedSources, queriedSources };
}

/**
 * Records filtered to the user's manually selected source set.
 * Filtering happens client-side; records whose source maps to an unknown key
 * are kept rather than silently dropped.
 */
export function useFilteredRecords(): {
  records: SpeciesRecord[];
  activeSourceKeys: string[];
} {
  const search = useSearch();
  const selectedSources = useSearchStore((s) => s.selectedSources);

  return useMemo(() => {
    const data = search.data;
    if (!data) return { records: [], activeSourceKeys: [] };

    const allowed = new Set(selectedSources);

    const records = data.results.filter((rec) => {
      const key = keyForApiName(sourceOf(rec));
      // keep when explicitly allowed, or when the key is unknown to our registry
      return allowed.has(key) || !data.sources.includes(key);
    });

    return { records, activeSourceKeys: selectedSources };
  }, [search.data, selectedSources]);
}
