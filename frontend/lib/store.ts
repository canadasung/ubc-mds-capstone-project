/**
 * Zustand store — replaces the *UI* half of Streamlit's st.session_state.
 *
 * Server state (search results, taxonomy) is NOT kept here; that lives in the
 * TanStack Query cache (see lib/hooks.ts). This store holds only synchronous UI
 * state that, in Streamlit, forced a full-script st.rerun() on every change.
 */

import { create } from "zustand";
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
  searchProgress: { source: string; done: number; total: number } | null;
  searchError: string | null;
  searchSuggestions: string[] | null;

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
  setSearchProgress: (p: { source: string; done: number; total: number } | null) => void;
  setSearchError: (e: string | null) => void;
  setSearchSuggestions: (names: string[] | null) => void;
}

export const useSearchStore = create<SearchState>((set, get) => ({
  query: "",
  submittedQuery: "",
  submittedSources: [],
  selectedSources: [...SOURCE_KEYS],

  cachedQuery: "",
  cachedSources: [],
  cachedData: null,

  isSearching: false,
  searchProgress: null,
  searchError: null,
  searchSuggestions: null,

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

  setSearchProgress: (p) => set({ searchProgress: p }),

  setSearchError: (e) => set({ searchError: e }),

  setSearchSuggestions: (names) => set({ searchSuggestions: names }),
}));
