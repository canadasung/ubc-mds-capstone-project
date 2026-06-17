/**
 * Per-cell shading for the Taxonomic view.
 *
 * Instead of turning a whole rank column red when sources disagree, each cell is
 * shaded by how far its value is (character edit distance) from that column's
 * reference value:
 *
 *   - Genus / Species → the SEARCH QUERY is the reference (these are the only
 *     ranks the query names). The query "Amanita muscaria" → genus "Amanita",
 *     species "muscaria".
 *   - every other rank → GBIF's value is the reference (the taxonomic backbone).
 *     If GBIF is not in the visible set, the first visible source is used.
 *
 * A cell that matches the reference stays white. Cells that differ are shaded on
 * a single blue gradient by their edit distance from the reference — the further
 * the value, the darker the blue.
 *
 * All logic here is pure so it can be unit-tested without React.
 */

import { keyForApiName } from "./sources";
import type { TaxonomyRow } from "./types";

export interface CellShade {
  backgroundColor: string;
  color: string;
}

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
 * Bucket an edit distance into a shade level 0–4:
 *   0 → white, 1 → lightest, 2–5 → mid, 6–7 → dark, 8+ → darkest.
 */
export function distanceLevel(d: number): 0 | 1 | 2 | 3 | 4 {
  if (d <= 0) return 0;
  if (d === 1) return 1;
  if (d <= 5) return 2;
  if (d <= 7) return 3;
  return 4;
}

/**
 * Blue palette indexed by shade level 1–4 (level 0 is white = no shade).
 * Text colour is chosen for contrast against each background.
 */
export const SHADE_PALETTE: Record<1 | 2 | 3 | 4, CellShade> = {
  1: { backgroundColor: "#d7e9fb", color: "#1a1a1a" },
  2: { backgroundColor: "#6aa6e0", color: "#ffffff" },
  3: { backgroundColor: "#2f64ad", color: "#ffffff" },
  4: { backgroundColor: "#15356e", color: "#ffffff" },
};

const norm = (s: string): string => s.trim().toLowerCase();

/** Read a rank value off a taxonomy row as a trimmed string ("" when absent). */
export function cellValue(row: TaxonomyRow, rank: string): string {
  const v = row[rank];
  return v == null || v === "" ? "" : String(v);
}

/** Split a normalised query ("Amanita muscaria") into genus + species epithet. */
function queryParts(query: string): { genus: string; species: string } {
  const [genus = "", species = ""] = query.trim().split(/\s+/);
  return { genus, species };
}

/**
 * The reference value a column is compared against (already trimmed, original
 * case). Genus/Species come from the query; other ranks come from GBIF, falling
 * back to the first visible source, then the first non-empty cell.
 *
 * Cells holding the unavailableMarker are skipped so an "unavailable" entry
 * from GBIF does not become the reference that real values are shaded against.
 */
export function columnReference(
  rank: string,
  rows: TaxonomyRow[],
  query: string,
  unavailableMarker?: string,
): string {
  if (rank === "Genus") return queryParts(query).genus;
  if (rank === "Species") return queryParts(query).species;

  const isAvailable = (v: string) => v !== "" && v !== unavailableMarker;

  const gbif = rows.find((r) => keyForApiName(r.source) === "gbif");
  const fromGbif = gbif ? cellValue(gbif, rank) : "";
  if (isAvailable(fromGbif)) return fromGbif;

  for (const r of rows) {
    const v = cellValue(r, rank);
    if (isAvailable(v)) return v;
  }
  return "";
}

/**
 * Compute the shade for every cell in one rank column, keyed by row source.
 * Returns null for a cell when it should stay white (matches the reference, is
 * empty, holds the unavailableMarker, or there is no usable reference).
 */
export function shadeColumn(
  rows: TaxonomyRow[],
  rank: string,
  reference: string,
  unavailableMarker?: string,
): Map<string, CellShade | null> {
  const result = new Map<string, CellShade | null>();
  const refNorm = norm(reference);

  for (const row of rows) {
    const raw = cellValue(row, rank);
    const v = norm(raw);
    if (!raw || raw === unavailableMarker || !refNorm || v === refNorm) {
      result.set(row.source, null); // white
      continue;
    }
    const level = distanceLevel(levenshtein(v, refNorm));
    result.set(row.source, level === 0 ? null : SHADE_PALETTE[level]);
  }
  return result;
}

/**
 * Shade an entire taxonomy table: rank → (source → shade|null).
 */
export function computeShading(
  rows: TaxonomyRow[],
  ranks: string[],
  query: string,
  unavailableMarker?: string,
): Map<string, Map<string, CellShade | null>> {
  const byRank = new Map<string, Map<string, CellShade | null>>();
  for (const rank of ranks) {
    const reference = columnReference(rank, rows, query, unavailableMarker);
    byRank.set(rank, shadeColumn(rows, rank, reference, unavailableMarker));
  }
  return byRank;
}
