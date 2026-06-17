/**
 * Source registry — ported from prototype_master.py (_API_LABELS) and
 * prototype_pipe.py (the three Advanced-filter groups).
 *
 * `key`     — the identifier the FastAPI backend uses (e.g. "gbif").
 * `label`   — short, human-readable name shown in narrow spots (table column
 *             headers, node graph). Cryptic acronyms (SERNEC, CCH2, …) and
 *             abbreviations (SW, NE) are expanded; already-readable names are
 *             left as-is.
 * `full`    — optional official long name, surfaced on hover (tooltip/title)
 *             where there is room. Falls back to `label` when absent.
 * `aliases` — extra strings that may appear in a record's `api_name` column,
 *             so `keyForApiName` still resolves if the backend ever emits the
 *             old short codes instead of the key.
 */

export type SourceGroup = "backbone" | "symbiota" | "independent";

export interface SourceDef {
  key: string;
  label: string;
  /** Display name used by the backend _PORTAL_REGISTRY, e.g. "GBIF", "CCH2". */
  backendName: string;
  group: SourceGroup;
  full?: string;
  aliases?: string[];
}

export const SOURCES: SourceDef[] = [
  { key: "gbif", label: "GBIF", backendName: "GBIF", group: "backbone", full: "Global Biodiversity Information Facility" },
  { key: "symbiota_mycoportal", label: "MyCoPortal", backendName: "MyCoPortal", group: "symbiota", full: "Mycology Collections Portal" },
  { key: "symbiota_lichen", label: "Lichen Portal", backendName: "Lichen Portal", group: "symbiota", full: "Consortium of Lichen Herbaria" },
  { key: "symbiota_bryophyte", label: "Bryophyte Portal", backendName: "Bryophyte Portal", group: "symbiota", full: "Consortium of North American Bryophyte Herbaria" },
  { key: "symbiota_sernec", label: "Southeast Herbaria", backendName: "SERNEC", group: "symbiota", full: "SouthEast Regional Network of Expertise and Collections (SERNEC)", aliases: ["sernec"] },
  { key: "symbiota_cch2", label: "California Herbaria", backendName: "CCH2", group: "symbiota", full: "Consortium of California Herbaria (CCH2)", aliases: ["cch2"] },
  { key: "symbiota_nansh", label: "Small Herbaria Network", backendName: "NANSH", group: "symbiota", full: "North American Network of Small Herbaria (NANSH)", aliases: ["nansh"] },
  { key: "symbiota_swbiodiversity", label: "Southwest Biodiversity", backendName: "swbiodiversity", group: "symbiota", full: "Southwest Biodiversity – SEINet AZ/NM Node", aliases: ["sw biodiversity"] },
  { key: "symbiota_macroalgae", label: "Macroalgae Portal", backendName: "Algae Herbarium Portal", group: "symbiota", full: "Macroalgae Herbarium Consortium" },
  { key: "symbiota_pterido", label: "Pteridophyte Portal", backendName: "Pterido Portal", group: "symbiota", full: "Pteridophyte Collections Consortium" },
  { key: "symbiota_neherbaria", label: "Northeast Herbaria", backendName: "CNH", group: "symbiota", full: "Consortium of Northeastern Herbaria", aliases: ["ne herbaria"] },
  { key: "symbiota_midatlantic", label: "Mid-Atlantic Herbaria", backendName: "Mid-Atlantic Herbaria Consortium", group: "symbiota" },
  { key: "col", label: "Catalogue of Life", backendName: "COL", group: "independent" },
  { key: "tropicos", label: "Tropicos", backendName: "Tropicos", group: "independent" },
  { key: "index_fungorum", label: "Index Fungorum", backendName: "Index Fungorum", group: "independent" },
  { key: "genbank", label: "GenBank", backendName: "GenBank", group: "independent" },
  { key: "mushroomobs", label: "Mushroom Observer", backendName: "Mushroom Observer", group: "independent" },
];

export const SOURCE_KEYS: string[] = SOURCES.map((s) => s.key);

export const GROUP_LABELS: Record<SourceGroup, string> = {
  backbone: "Global Backbone",
  symbiota: "Symbiota Portals",
  independent: "Independent APIs",
};

const KEY_TO_DEF = new Map(SOURCES.map((s) => [s.key, s]));
const LABEL_TO_KEY = new Map<string, string>();
for (const s of SOURCES) {
  LABEL_TO_KEY.set(s.label.toLowerCase(), s.key);
  for (const a of s.aliases ?? []) LABEL_TO_KEY.set(a.toLowerCase(), s.key);
}
// short label (lowercased) → full official name, for tooltips where only the
// display label string is available (e.g. the Table view column headers).
const LABEL_TO_FULL = new Map(
  SOURCES.map((s) => [s.label.toLowerCase(), s.full ?? s.label]),
);

export function labelForKey(key: string): string {
  return KEY_TO_DEF.get(key)?.label ?? key;
}

/** Official long name for a key, falling back to the short label. */
export function fullLabelForKey(key: string): string {
  const def = KEY_TO_DEF.get(key);
  return def?.full ?? def?.label ?? key;
}

/** Official long name given a short display label (falls back to the label). */
export function fullForLabel(label: string): string {
  return LABEL_TO_FULL.get(label.toLowerCase()) ?? label;
}

export function groupOf(key: string): SourceGroup | undefined {
  return KEY_TO_DEF.get(key)?.group;
}

/** Backend portal registry name for a source key (undefined if not found). */
export function backendNameForKey(key: string): string | undefined {
  return KEY_TO_DEF.get(key)?.backendName;
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
