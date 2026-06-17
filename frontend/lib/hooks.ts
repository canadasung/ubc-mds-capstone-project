/**
 * TanStack Query hooks — the server-state layer. These cache by query key so a
 * single search is fetched once and shared across every view, replacing the
 * per-rerun re-execution and @st.cache_data of the Streamlit app.
 *
 * useSearch() is backed by Zustand (live SSE stream) rather than React Query
 * so that the smart-cache logic (skip re-fetch on source-only removals, merge
 * on incremental additions) can inspect and update cached state directly.
 */

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { getSearch, getSources, getTaxonomy, openSearchStream } from "./api";
import { keyForApiName } from "./sources";
import { sourceOf } from "./fields";
import { useSearchStore } from "./store";
import { ApiError } from "./types";
import type { SearchResponse, SpeciesRecord } from "./types";

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: getSources,
  });
}

/**
 * Registers the SSE live-search effect. Fires whenever submittedQuery or
 * submittedSources change. Handles smart-cache logic:
 *   - same query, no new sources → skip re-fetch (client-side filter handles it)
 *   - same query, new sources added → fetch only the new sources, merge results
 *   - query changed → full fetch
 */
function useLiveSearchEffect() {
  const submittedQuery = useSearchStore((s) => s.submittedQuery);
  const submittedSources = useSearchStore((s) => s.submittedSources);
  const cachedQuery = useSearchStore((s) => s.cachedQuery);
  const cachedSources = useSearchStore((s) => s.cachedSources);
  const cachedData = useSearchStore((s) => s.cachedData);
  const setCachedSearch = useSearchStore((s) => s.setCachedSearch);
  const setIsSearching = useSearchStore((s) => s.setIsSearching);
  const setSearchProgress = useSearchStore((s) => s.setSearchProgress);
  const setSearchError = useSearchStore((s) => s.setSearchError);
  const setSearchSuggestions = useSearchStore((s) => s.setSearchSuggestions);

  // submittedSources.join is stable as long as the array contents don't change
  const submittedSourcesKey = submittedSources.join(",");

  useEffect(() => {
    if (!submittedQuery) return;

    const addedSources = submittedSources.filter((s) => !cachedSources.includes(s));

    // Same query, no new sources — client-side filtering is sufficient
    if (submittedQuery === cachedQuery && addedSources.length === 0) return;

    const isIncremental = submittedQuery === cachedQuery && addedSources.length > 0;
    const sourcesToFetch = isIncremental ? addedSources : submittedSources;

    setIsSearching(true);
    setSearchProgress(null);
    setSearchError(null);
    setSearchSuggestions(null);

    const cleanup = openSearchStream(
      submittedQuery,
      sourcesToFetch,
      (source, done, total) => setSearchProgress({ source, done, total }),
      (data: SearchResponse) => {
        if (isIncremental && cachedData) {
          const merged: SearchResponse = {
            ...data,
            results: [...cachedData.results, ...data.results],
            sources: [...new Set([...cachedData.sources, ...data.sources])],
          };
          setCachedSearch(submittedQuery, submittedSources, merged);
        } else {
          setCachedSearch(submittedQuery, submittedSources, data);
        }
        setIsSearching(false);
        setSearchProgress(null);
      },
      (names: string[]) => {
        setSearchSuggestions(names);
        setSearchError("No results found.");
        setIsSearching(false);
        setSearchProgress(null);
      },
      (err: Error) => {
        setSearchError(err.message);
        setIsSearching(false);
        setSearchProgress(null);
      },
    );

    return cleanup;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submittedQuery, submittedSourcesKey]);
}

/** Store-backed replacement for the old TanStack Query useSearch(). */
export function useSearch() {
  useLiveSearchEffect();

  const data = useSearchStore((s) => s.cachedData) ?? undefined;
  const isFetching = useSearchStore((s) => s.isSearching);
  const searchError = useSearchStore((s) => s.searchError);
  const searchSuggestions = useSearchStore((s) => s.searchSuggestions);

  const error = searchError
    ? Object.assign(new ApiError(0, searchError), {
        available: searchSuggestions ?? undefined,
      })
    : null;

  return { data, isFetching, error };
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
    // Normalise the queried sources list to keys for comparison
    const queriedKeys = new Set(data.sources.map((s) => keyForApiName(s)));

    const records = data.results.filter((rec) => {
      const key = keyForApiName(sourceOf(rec));
      // keep when explicitly allowed, or when the key is unknown to our registry
      return allowed.has(key) || !queriedKeys.has(key);
    });

    return { records, activeSourceKeys: selectedSources };
  }, [search.data, selectedSources]);
}
