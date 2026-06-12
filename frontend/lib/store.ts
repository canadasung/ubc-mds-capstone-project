/**
 * Zustand store — replaces the *UI* half of Streamlit's st.session_state.
 *
 * Server state (search results, taxonomy) is NOT kept here; that lives in the
 * TanStack Query cache (see lib/hooks.ts). This store holds only synchronous UI
 * state that, in Streamlit, forced a full-script st.rerun() on every change.
 */

import { create } from "zustand";
import { SOURCE_KEYS } from "./sources";

export type ViewKey = "Overview" | "Detail" | "Relations" | "Timeline" | "Taxonomy";

interface SearchState {
  // ── Search form ───────────────────────────────────────────────
  query: string; // current text-input value
  submittedQuery: string; // last submitted query — drives the data hooks
  selectedSources: string[];

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
}

export const useSearchStore = create<SearchState>((set, get) => ({
  query: "",
  submittedQuery: "",
  selectedSources: [...SOURCE_KEYS],

  panelOpen: true,
  activeView: "Overview",

  setQuery: (q) => set({ query: q }),

  submit: () => {
    const q = get().query.trim();
    if (q) set({ submittedQuery: q });
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
}));
