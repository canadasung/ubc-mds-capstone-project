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

import { getSources, openSearchStream } from "./api";
import { keyForApiName } from "./sources";
import { sourceOf } from "./fields";
import { useSearchStore } from "./store";
import { ApiError } from "./types";
import type { SearchResponse, SpeciesRecord, TaxonomyRow, TaxonomyResponse } from "./types";

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: getSources,
  });
}

/**
 * Registers the SSE live-search effect. Call this ONCE near the root of the
 * component tree (page.tsx). Do NOT call it from inside useSearch() — useSearch()
 * is called by multiple components simultaneously, which would open multiple
 * competing SSE connections.
 *
 * Smart-cache logic:
 *   - same query, no new sources → brief "filtering" flash, no re-fetch
 *   - same query, new sources added → fetch only the new sources, merge results
 *   - query changed → full fetch
 */
export function useLiveSearchEffect() {
  const submittedQuery = useSearchStore((s) => s.submittedQuery);
  const submittedSources = useSearchStore((s) => s.submittedSources);
  const cachedQuery = useSearchStore((s) => s.cachedQuery);
  const cachedSources = useSearchStore((s) => s.cachedSources);
  const cachedData = useSearchStore((s) => s.cachedData);
  const setCachedSearch = useSearchStore((s) => s.setCachedSearch);
  const setIsSearching = useSearchStore((s) => s.setIsSearching);
  const setIsFiltering = useSearchStore((s) => s.setIsFiltering);
  const setSearchProgress = useSearchStore((s) => s.setSearchProgress);
  const setSearchError = useSearchStore((s) => s.setSearchError);
  const setSearchSuggestions = useSearchStore((s) => s.setSearchSuggestions);
  const setStreamCancel = useSearchStore((s) => s.setStreamCancel);

  // submittedSources.join is stable as long as the array contents don't change
  const submittedSourcesKey = submittedSources.join(",");

  useEffect(() => {
    if (!submittedQuery) return;

    const addedSources = submittedSources.filter((s) => !cachedSources.includes(s));

    // Same query, no new sources — client-side filtering is sufficient.
    // Only flash the "filtering" indicator when there's cached data to show
    // (i.e. not on an initial search where cachedData is null).
    if (submittedQuery === cachedQuery && addedSources.length === 0) {
      if (cachedData) {
        setIsFiltering(true);
        const t = setTimeout(() => setIsFiltering(false), 800);
        return () => clearTimeout(t);
      }
      return;
    }

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
        if (isIncremental && cachedData) {
          // Newly-added source returned nothing — keep existing results, just
          // update the cache key so we don't re-fetch this source next time.
          setCachedSearch(submittedQuery, submittedSources, cachedData);
        } else {
          setSearchSuggestions(names);
          setSearchError("No results found.");
        }
        setIsSearching(false);
        setSearchProgress(null);
      },
      (err: Error) => {
        setSearchError(err.message);
        setIsSearching(false);
        setSearchProgress(null);
      },
    );

    setStreamCancel(cleanup);
    return () => {
      cleanup();
      setStreamCancel(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submittedQuery, submittedSourcesKey]);
}

/** Store-backed replacement for the old TanStack Query useSearch(). */
export function useSearch() {
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

const RANK_FIELDS: Array<{ field: keyof SpeciesRecord; label: string }> = [
  { field: "kingdom", label: "Kingdom" },
  { field: "phylum", label: "Phylum" },
  { field: "class", label: "Class" },
  { field: "order", label: "Order" },
  { field: "family", label: "Family" },
  { field: "subfamily", label: "Subfamily" },
  { field: "genus", label: "Genus" },
  { field: "species", label: "Species" },
];

/**
 * Derives the taxonomy comparison table directly from the live search results
 * stored in Zustand, instead of calling the mock /api/taxonomy endpoint.
 * Returns the same shape as the old TanStack Query hook so TaxonomyView is unchanged.
 */
export function useTaxonomy(): {
  data: TaxonomyResponse | undefined;
  isLoading: boolean;
  isError: boolean;
} {
  const query = useSearchStore((s) => s.submittedQuery);
  const search = useSearch();

  return useMemo(() => {
    if (search.isFetching) {
      return { data: undefined, isLoading: true, isError: false };
    }

    const results = search.data?.results;
    if (!results || results.length === 0) {
      return { data: undefined, isLoading: false, isError: !!search.error };
    }

    // Group records by source, preserving the order they were received.
    const bySource = new Map<string, SpeciesRecord[]>();
    for (const rec of results) {
      if (!bySource.has(rec.api_name)) bySource.set(rec.api_name, []);
      bySource.get(rec.api_name)!.push(rec);
    }

    const rows: TaxonomyRow[] = [];
    for (const [source, recs] of bySource) {
      // Prefer the Accepted row as the canonical reference for this source.
      const ref = recs.find((r) => r.status === "Accepted") ?? recs[0];
      const synonymCount = recs.filter((r) => r.status === "Synonym").length;

      const entry: TaxonomyRow = { source, synonym_count: synonymCount };
      for (const { field, label } of RANK_FIELDS) {
        const val = ref[field];
        entry[label] =
          val != null && String(val).trim() !== "" ? String(val).trim() : null;
      }
      rows.push(entry);
    }

    const presentRanks = RANK_FIELDS.map((r) => r.label).filter((label) =>
      rows.some((row) => row[label] != null),
    );

    const data: TaxonomyResponse = {
      query,
      ranks: presentRanks,
      sources: rows,
      disagreements: [], // TaxonomyView recomputes this from the filtered source set
    };

    return { data, isLoading: false, isError: false };
  }, [search.data, search.isFetching, search.error, query]);
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

  // Normalise to frontend keys so callers can compare with keyForApiName(row.source).
  const queriedSources = (search.data?.sources ?? []).map(keyForApiName);
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
  // Use submittedSources (not selectedSources) so results only change when
  // Search is pressed, making the isFiltering flash visible and meaningful.
  const submittedSources = useSearchStore((s) => s.submittedSources);

  return useMemo(() => {
    const data = search.data;
    if (!data) return { records: [], activeSourceKeys: [] };

    const allowed = new Set(submittedSources);
    // Normalise the queried sources list to keys for comparison
    const queriedKeys = new Set(data.sources.map((s) => keyForApiName(s)));

    const records = data.results.filter((rec) => {
      const key = keyForApiName(sourceOf(rec));
      // keep when explicitly allowed, or when the key is unknown to our registry
      return allowed.has(key) || !queriedKeys.has(key);
    });

    return { records, activeSourceKeys: submittedSources };
  }, [search.data, submittedSources]);
}
