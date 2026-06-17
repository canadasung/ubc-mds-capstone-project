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

export type ViewKey = "Overview" | "Detail" | "Relations" | "Timeline" | "Taxonomy";

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
}

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
      submitVersion: 0,
      _hasHydrated: false,

      panelOpen: true,
      activeView: "Overview",

      setQuery: (q) => set({ query: q }),

      submit: () => {
        const q = get().query.trim();
        if (q) set({ submittedQuery: q, submittedSources: [...get().selectedSources] });
      },

      toggleSource: (key) =>
        set((s) => ({
          selectedSources: s.selectedSources.includes(key)
            ? s.selectedSources.filter((k) => k !== key)
            : [...s.selectedSources, key],
        })),

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

      cancelSearch: () => {
        get()._cancelStream?.();
        set({ _cancelStream: null, isSearching: false, searchProgress: null });
      },

      _setHasHydrated: (v) => set({ _hasHydrated: v }),

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
