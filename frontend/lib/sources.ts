/**
 * Source registry — ported from prototype_master.py (_API_LABELS) and
 * prototype_pipe.py (the three Advanced-filter groups).
 *
 * `key`     — the identifier the FastAPI backend uses (e.g. "gbif").
 * `label`   — human-readable name shown in the UI.
 * `apiName` — the value that appears in a record's `api_name` column, used to
 *             map a CSV row back to its source key (CSV uses display-ish names).
 */

export type SourceGroup = "backbone" | "symbiota" | "independent";

export interface SourceDef {
  key: string;
  label: string;
  group: SourceGroup;
}

export const SOURCES: SourceDef[] = [
  { key: "gbif", label: "GBIF", group: "backbone" },
  { key: "symbiota_mycoportal", label: "MyCoPortal", group: "symbiota" },
  { key: "symbiota_lichen", label: "Lichen Portal", group: "symbiota" },
  { key: "symbiota_bryophyte", label: "Bryophyte Portal", group: "symbiota" },
  { key: "symbiota_sernec", label: "SERNEC", group: "symbiota" },
  { key: "symbiota_cch2", label: "CCH2", group: "symbiota" },
  { key: "symbiota_nansh", label: "NANSH", group: "symbiota" },
  { key: "symbiota_swbiodiversity", label: "SW Biodiversity", group: "symbiota" },
  { key: "symbiota_macroalgae", label: "Macroalgae Portal", group: "symbiota" },
  { key: "symbiota_pterido", label: "Pteridophyte Portal", group: "symbiota" },
  { key: "symbiota_neherbaria", label: "NE Herbaria", group: "symbiota" },
  { key: "symbiota_midatlantic", label: "Mid-Atlantic Herbaria", group: "symbiota" },
  { key: "col", label: "Catalogue of Life", group: "independent" },
  { key: "tropicos", label: "Tropicos", group: "independent" },
  { key: "index_fungorum", label: "Index Fungorum", group: "independent" },
  { key: "genbank", label: "GenBank", group: "independent" },
  { key: "mushroomobs", label: "Mushroom Observer", group: "independent" },
];

export const SOURCE_KEYS: string[] = SOURCES.map((s) => s.key);

export const GROUP_LABELS: Record<SourceGroup, string> = {
  backbone: "🌍 Global Backbone",
  symbiota: "🌿 Symbiota Portals",
  independent: "🔬 Independent APIs",
};

const KEY_TO_DEF = new Map(SOURCES.map((s) => [s.key, s]));
const LABEL_TO_KEY = new Map(
  SOURCES.map((s) => [s.label.toLowerCase(), s.key]),
);

export function labelForKey(key: string): string {
  return KEY_TO_DEF.get(key)?.label ?? key;
}

export function groupOf(key: string): SourceGroup | undefined {
  return KEY_TO_DEF.get(key)?.group;
}

/**
 * Map a record's `api_name` (e.g. "GBIF", "Index Fungorum") back to a source
 * key (e.g. "gbif", "index_fungorum"). Falls back to a lowercased/underscored
 * form so unknown sources still produce a stable key rather than being dropped.
 */
export function keyForApiName(apiName: string): string {
  const lower = (apiName ?? "").trim().toLowerCase();
  if (LABEL_TO_KEY.has(lower)) return LABEL_TO_KEY.get(lower)!;
  if (KEY_TO_DEF.has(lower)) return lower;
  return lower.replace(/\s+/g, "_");
}
