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
  const useRouting = useSearchStore((s) => s.useRouting);

  return useQuery<SearchResponse>({
    queryKey: ["search", query, useRouting],
    queryFn: () => getSearch(query, useRouting),
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
 * The set of source keys currently active, using the same rule as
 * useFilteredRecords:
 *   - routing ON  → the sources the server reports it queried
 *   - routing OFF → the user's manual selection
 *
 * `queriedSources` is returned too so callers can apply the same "keep unknown
 * sources rather than drop them" fallback.
 */
export function useActiveSourceKeys(): {
  keys: string[];
  queriedSources: string[];
} {
  const search = useSearch();
  const useRouting = useSearchStore((s) => s.useRouting);
  const selectedSources = useSearchStore((s) => s.selectedSources);

  const queriedSources = search.data?.sources ?? [];
  const keys = useRouting ? queriedSources : selectedSources;
  return { keys, queriedSources };
}

/**
 * Records filtered to the active source set.
 *
 * - routing ON  → keep the set the server reports it queried (response.sources)
 * - routing OFF → keep the user's manual selection (store.selectedSources)
 *
 * Until the backend accepts a source-filter param (see ARCHITECTURE.md §7,
 * phase 2), this filtering happens client-side. Records whose source maps to an
 * unknown key are kept rather than silently dropped.
 */
export function useFilteredRecords(): {
  records: SpeciesRecord[];
  activeSourceKeys: string[];
} {
  const search = useSearch();
  const useRouting = useSearchStore((s) => s.useRouting);
  const selectedSources = useSearchStore((s) => s.selectedSources);

  return useMemo(() => {
    const data = search.data;
    if (!data) return { records: [], activeSourceKeys: [] };

    const activeSourceKeys = useRouting ? data.sources : selectedSources;
    const allowed = new Set(activeSourceKeys);

    const records = data.results.filter((rec) => {
      const key = keyForApiName(sourceOf(rec));
      // keep when explicitly allowed, or when the key is unknown to our registry
      return allowed.has(key) || !data.sources.includes(key);
    });

    return { records, activeSourceKeys };
  }, [search.data, useRouting, selectedSources]);
}
