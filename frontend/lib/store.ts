/**
 * Zustand store — replaces the *UI* half of Streamlit's st.session_state.
 *
 * Persisted to sessionStorage via the `persist` middleware so that state
 * survives Next.js HMR reloads (e.g. saving a file in VS Code while the
 * browser is open) and browser tab switches. State is cleared when the
 * tab/window is closed. Transient fields (isSearching, searchProgress, etc.)
 * are intentionally excluded from persistence and always reset to defaults.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { SOURCE_KEYS } from "./sources";
import type { SearchResponse } from "./types";

export type ViewKey = "Overview" | "Relations" | "Timeline" | "Taxonomy" | "Detail";

interface SearchState {
  // ── Search form ───────────────────────────────────────────────
  query: string; // current text-input value
  submittedQuery: string; // last submitted query — drives the data hooks
  submittedSources: string[]; // snapshot of selectedSources at submit time
  selectedSources: string[];

  // ── Live search cache ─────────────────────────────────────────
  cachedQuery: string; // query of last completed search
  cachedSources: string[]; // sources queried in last completed search
  cachedData: SearchResponse | null; // results of last completed search

  // ── Live search progress ──────────────────────────────────────
  isSearching: boolean;
  isFiltering: boolean; // brief flash when re-submitting with only source removals
  searchProgress: { source: string; done: number; total: number } | null;
  searchError: string | null;
  searchSuggestions: string[] | null;
  _cancelStream: (() => void) | null; // close the active EventSource
  _wasCancelled: boolean; // consumed by useLiveSearchEffect to skip the filtering flash on rollback

  // ── Layout ────────────────────────────────────────────────────
  panelOpen: boolean;
  activeView: ViewKey;

  // ── Actions ───────────────────────────────────────────────────
  setQuery: (q: string) => void;
  submit: () => void;
  toggleSource: (key: string) => void;
  setAllSources: (on: boolean) => void;
  setSources: (keys: string[]) => void;
  togglePanel: () => void;
  setActiveView: (v: ViewKey) => void;

  setCachedSearch: (query: string, sources: string[], data: SearchResponse) => void;
  setIsSearching: (v: boolean) => void;
  setIsFiltering: (v: boolean) => void;
  setSearchProgress: (p: { source: string; done: number; total: number } | null) => void;
  setSearchError: (e: string | null) => void;
  setSearchSuggestions: (names: string[] | null) => void;
  setStreamCancel: (fn: (() => void) | null) => void;
  cancelSearch: () => void;
  submitVersion: number; // incremented only by forceResubmit; not persisted
  forceResubmit: () => void;
  _hasHydrated: boolean; // true once sessionStorage has been read; not persisted
  _setHasHydrated: (v: boolean) => void;
  _clearWasCancelled: () => void;
}

/**
 * Global Zustand store for search UI state.
 *
 * Stable slices (query, selected sources, active view, cached results) are
 * persisted to sessionStorage so they survive HMR reloads. Transient fields
 * (isSearching, searchProgress, _cancelStream, etc.) are excluded from
 * persistence and always reset to their defaults on rehydration.
 */
export const useSearchStore = create<SearchState>()(
  persist(
    (set, get) => ({
      query: "",
      submittedQuery: "",
      submittedSources: [],
      selectedSources: [...SOURCE_KEYS],

      cachedQuery: "",
      cachedSources: [],
      cachedData: null,

      isSearching: false,
      isFiltering: false,
      searchProgress: null,
      searchError: null,
      searchSuggestions: null,
      _cancelStream: null,
      _wasCancelled: false,
      submitVersion: 0,
      _hasHydrated: false,

      panelOpen: true,
      activeView: "Overview",

      setQuery: (q) => set({ query: q }),

      /**
       * Snapshot the current query and selectedSources into submittedQuery /
       * submittedSources, which triggers useLiveSearchEffect. No-op when the
       * trimmed query is empty.
       */
      submit: () => {
        const q = get().query.trim();
        if (q) set({ submittedQuery: q, submittedSources: [...get().selectedSources] });
      },

      /** Add ``key`` to selectedSources when absent; remove it when present. */
      toggleSource: (key) =>
        set((s) => ({
          selectedSources: s.selectedSources.includes(key)
            ? s.selectedSources.filter((k) => k !== key)
            : [...s.selectedSources, key],
        })),

      /** Select all known sources (``on=true``) or clear the selection (``on=false``). */
      setAllSources: (on) => set({ selectedSources: on ? [...SOURCE_KEYS] : [] }),

      setSources: (keys) => set({ selectedSources: keys }),

      togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),

      setActiveView: (v) => set({ activeView: v }),

      setCachedSearch: (query, sources, data) =>
        set({ cachedQuery: query, cachedSources: sources, cachedData: data }),

      setIsSearching: (v) => set({ isSearching: v }),

      setIsFiltering: (v) => set({ isFiltering: v }),

      setSearchProgress: (p) => set({ searchProgress: p }),

      setSearchError: (e) => set({ searchError: e }),

      setSearchSuggestions: (names) => set({ searchSuggestions: names }),

      setStreamCancel: (fn) => set({ _cancelStream: fn }),

      /**
       * Abort the active SSE stream and roll back submittedQuery /
       * submittedSources to the last completed search so previous results
       * reappear immediately (or the start page if nothing was ever cached).
       */
      cancelSearch: () => {
        get()._cancelStream?.();
        const { cachedQuery, cachedSources } = get();
        set({
          _cancelStream: null,
          isSearching: false,
          searchProgress: null,
          searchError: null,
          searchSuggestions: null,
          // Roll back submitted state to the last completed search so that
          // previous results reappear (or the start page if nothing was ever cached).
          // cachedQuery/cachedSources/cachedData are intentionally left intact so
          // the effect sees a cache-hit and doesn't auto-restart the old search.
          // _wasCancelled tells the effect to skip the filtering flash on rollback.
          submittedQuery: cachedQuery,
          submittedSources: cachedSources,
          _wasCancelled: true,
        });
      },

      _setHasHydrated: (v) => set({ _hasHydrated: v }),
      _clearWasCancelled: () => set({ _wasCancelled: false }),

      /**
       * Re-run the search even when query and sources haven't changed.
       *
       * Clears cachedQuery so useLiveSearchEffect sees a cache miss and runs a
       * full fetch. Bumps submitVersion so the effect re-fires even if
       * submittedQuery is already equal to the current query.
       */
      forceResubmit: () => {
        const q = get().query.trim();
        if (!q) return;
        // Clear cachedQuery so the effect sees a cache miss and runs a full fetch.
        // submitVersion bump ensures the effect re-runs even though submittedQuery
        // and submittedSources values haven't changed.
        set({
          submittedQuery: q,
          submittedSources: [...get().selectedSources],
          cachedQuery: "",
          cachedSources: [],
          submitVersion: get().submitVersion + 1,
        });
      },
    }),
    {
      name: "mds-search-store",
      storage: createJSONStorage(() => sessionStorage),
      // Mark hydration complete so the UI can show "Reloading…" instead of
      // "Run a search" during the brief async window before storage is read.
      onRehydrateStorage: () => (state) => {
        state?._setHasHydrated(true);
      },
      // Only persist stable data. Transient loading state and non-serializable
      // functions are always reset to defaults on rehydration.
      partialize: (state) => ({
        query: state.query,
        selectedSources: state.selectedSources,
        activeView: state.activeView,
        panelOpen: state.panelOpen,
        submittedQuery: state.submittedQuery,
        submittedSources: state.submittedSources,
        cachedQuery: state.cachedQuery,
        cachedSources: state.cachedSources,
        cachedData: state.cachedData,
      }),
    }
  )
);
