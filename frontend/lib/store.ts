/**
 * Zustand store — replaces the *UI* half of Streamlit's st.session_state.
 *
 * Server state (search results, taxonomy) is NOT kept here; that lives in the
 * TanStack Query cache (see lib/hooks.ts). This store holds only synchronous UI
 * state that, in Streamlit, forced a full-script st.rerun() on every change.
 */

import { create } from "zustand";
import { SOURCE_KEYS } from "./sources";

export type ViewKey = "Table" | "Timeline" | "Relations" | "Taxonomic" | "Debug";

interface SearchState {
  // ── Search form ───────────────────────────────────────────────
  query: string; // current text-input value
  submittedQuery: string; // last submitted query — drives the data hooks
  useRouting: boolean; // "Choose databases based on kingdom"
  selectedSources: string[]; // manual selection (used when useRouting === false)

  // ── Layout ────────────────────────────────────────────────────
  panelOpen: boolean;
  activeView: ViewKey;
  debug: boolean;

  // ── Actions ───────────────────────────────────────────────────
  setQuery: (q: string) => void;
  submit: () => void;
  setUseRouting: (v: boolean) => void;
  toggleSource: (key: string) => void;
  setAllSources: (on: boolean) => void;
  togglePanel: () => void;
  setActiveView: (v: ViewKey) => void;
  setDebug: (v: boolean) => void;
}

export const useSearchStore = create<SearchState>((set, get) => ({
  query: "",
  submittedQuery: "",
  useRouting: true,
  selectedSources: [...SOURCE_KEYS], // all on by default (mirrors value=True)

  panelOpen: true,
  activeView: "Table",
  debug: false,

  setQuery: (q) => set({ query: q }),

  submit: () => {
    const q = get().query.trim();
    if (q) set({ submittedQuery: q });
  },

  setUseRouting: (v) => set({ useRouting: v }),

  toggleSource: (key) =>
    set((s) => ({
      selectedSources: s.selectedSources.includes(key)
        ? s.selectedSources.filter((k) => k !== key)
        : [...s.selectedSources, key],
    })),

  setAllSources: (on) => set({ selectedSources: on ? [...SOURCE_KEYS] : [] }),

  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),

  setActiveView: (v) => set({ activeView: v }),

  setDebug: (v) =>
    set((s) => ({
      debug: v,
      // keep activeView valid when Debug is turned off
      activeView: !v && s.activeView === "Debug" ? "Table" : s.activeView,
    })),
}));
