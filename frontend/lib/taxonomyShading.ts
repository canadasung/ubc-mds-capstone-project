/**
 * Per-cell shading for the Taxonomic view.
 *
 * Only the higher ranks — Kingdom, Phylum, Class, Order, Family, Subfamily — are shaded.
 * Genus and Species are never shaded (they're shown as plain text).
 *
 * For the shaded ranks a single source is treated as the "truth" backbone
 * (GBIF by default, but user-selectable). Each cell is coloured by how far its
 * value is (character edit distance) from the backbone's value for that rank:
 *
 *   - the backbone's own cell, and any source whose value MATCHES it, are shown
 *     in a very light blue.
 *   - cells that DIFFER are shown in a darker shade of blue, the further the
 *     value the darker the blue.
 *   - empty cells, and every cell in an unshaded rank, stay white.
 *
 * All logic here is pure so it can be unit-tested without React.
 */

import { keyForApiName } from "./sources";
import type { TaxonomyRow } from "./types";

export interface CellShade {
  backgroundColor: string;
  color: string;
}

/** Ranks that get shaded. Genus/Species are intentionally excluded. */
export const SHADED_RANKS: ReadonlySet<string> = new Set([
  "Kingdom",
  "Phylum",
  "Class",
  "Order",
  "Family",
  "Subfamily",
]);

/** Default backbone source key (the taxonomic "truth" value). */
export const DEFAULT_BACKBONE = "gbif";

/** Levenshtein edit distance between two strings (insert/delete/substitute). */
export function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;

  // single-row DP: prev[j] holds the distance for the previous source char
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    let prevDiag = prev[0]; // cost[i-1][j-1]
    prev[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      const cur = Math.min(
        prev[j] + 1, // deletion
        prev[j - 1] + 1, // insertion
        prevDiag + cost, // substitution
      );
      prevDiag = prev[j];
      prev[j] = cur;
    }
  }
  return prev[b.length];
}

/**
 * Bucket a (non-zero) edit distance into a difference level 1–4:
 *   1 → 1, 2 → 2–5, 3 → 6–7, 4 → 8+.
 */
export function distanceLevel(d: number): 1 | 2 | 3 | 4 {
  if (d <= 1) return 1;
  if (d <= 5) return 2;
  if (d <= 7) return 3;
  return 4;
}

/**
 * The very light blue used for the backbone cell and for any source that
 * matches it (edit distance 0).
 */
export const MATCH_SHADE: CellShade = {
  backgroundColor: "#eef5fd",
  color: "#1a1a1a",
};

/**
 * Blue palette for cells that DIFFER from the backbone, indexed by difference
 * level 1–4. All shades are darker than MATCH_SHADE so a distance-1 difference
 * is still distinguishable from a match. Text colour is chosen for contrast.
 */
export const DIFF_PALETTE: Record<1 | 2 | 3 | 4, CellShade> = {
  1: { backgroundColor: "#9dc3ee", color: "#1a1a1a" },
  2: { backgroundColor: "#5d9add", color: "#ffffff" },
  3: { backgroundColor: "#2f64ad", color: "#ffffff" },
  4: { backgroundColor: "#15356e", color: "#ffffff" },
};

const norm = (s: string): string => s.trim().toLowerCase();

/** Read a rank value off a taxonomy row as a trimmed string ("" when absent). */
export function cellValue(row: TaxonomyRow, rank: string): string {
  const v = row[rank];
  return v == null || v === "" ? "" : String(v);
}

/**
 * The reference value a shaded column is compared against (trimmed, original
 * case): the backbone source's value, falling back to the first visible source
 * with a non-empty value when the backbone has none.
 */
export function columnReference(
  rank: string,
  rows: TaxonomyRow[],
  backbone: string,
  unavailMarker = "N/A",
): string {
  if (!SHADED_RANKS.has(rank)) return "";

  const isReal = (v: string) => v !== "" && v !== unavailMarker;

  const backboneRow = rows.find((r) => keyForApiName(r.source) === backbone);
  const fromBackbone = backboneRow ? cellValue(backboneRow, rank) : "";
  if (isReal(fromBackbone)) return fromBackbone;

  for (const r of rows) {
    const v = cellValue(r, rank);
    if (isReal(v)) return v;
  }
  return "";
}

/**
 * Compute the shade for every cell in one rank column, keyed by row source.
 * Returns null for a cell when it should stay white (unshaded rank, empty cell,
 * or no usable reference). A cell that matches the reference gets MATCH_SHADE;
 * a cell that differs gets DIFF_PALETTE keyed by its edit distance.
 */
export function shadeColumn(
  rows: TaxonomyRow[],
  rank: string,
  reference: string,
  unavailMarker = "N/A",
): Map<string, CellShade | null> {
  const result = new Map<string, CellShade | null>();
  const refNorm = norm(reference);
  const shaded = SHADED_RANKS.has(rank) && refNorm !== "";

  for (const row of rows) {
    const raw = cellValue(row, rank);
    if (!shaded || !raw || raw === unavailMarker) {
      result.set(row.source, null); // white
      continue;
    }
    const v = norm(raw);
    if (v === refNorm) {
      result.set(row.source, MATCH_SHADE); // backbone + matches → light blue
      continue;
    }
    result.set(row.source, DIFF_PALETTE[distanceLevel(levenshtein(v, refNorm))]);
  }
  return result;
}

/**
 * Shade an entire taxonomy table: rank → (source → shade|null).
 *
 * @param backbone source key treated as the truth value (default GBIF).
 */
export function computeShading(
  rows: TaxonomyRow[],
  ranks: string[],
  backbone: string = DEFAULT_BACKBONE,
  unavailMarker = "N/A",
): Map<string, Map<string, CellShade | null>> {
  const byRank = new Map<string, Map<string, CellShade | null>>();
  for (const rank of ranks) {
    const reference = columnReference(rank, rows, backbone, unavailMarker);
    byRank.set(rank, shadeColumn(rows, rank, reference, unavailMarker));
  }
  return byRank;
}
