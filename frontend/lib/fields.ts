/**
 * Single source of truth for reading fields off a SpeciesRecord.
 *
 * The live FastAPI /api/search emits snake_case CSV columns, while the older
 * Streamlit master views read title-case columns ("Source Name", "GBIF
 * Accepted Status", ...). Isolating the field access here means that if the
 * backend column names ever change, this is the only file to edit.
 */

import type { SpeciesRecord } from "./types";

/** Coerce any value to a trimmed string, returning ``""`` for null/undefined. */
function str(v: unknown): string {
  return v === null || v === undefined ? "" : String(v).trim();
}

/** The source a row belongs to (CSV: `api_name`). */
export function sourceOf(rec: SpeciesRecord): string {
  return str(rec.api_name) || str(rec.source_name);
}

/** "Genus species" binomial. */
export function nameOf(rec: SpeciesRecord): string {
  return `${str(rec.genus)} ${str(rec.species)}`.trim();
}

/** Genus string from the record (CSV: ``genus``). */
export function genusOf(rec: SpeciesRecord): string {
  return str(rec.genus);
}

/** Species epithet string from the record (CSV: ``species``). */
export function speciesOf(rec: SpeciesRecord): string {
  return str(rec.species);
}

/** Outbound link to the source's page for this record (CSV: `api_link`). */
export function linkOf(rec: SpeciesRecord): string | null {
  const v = str(rec.api_link);
  return v ? v : null;
}

/** "Accepted" | "Synonym" | "" (CSV: `status`). */
export function statusOf(rec: SpeciesRecord): string {
  return str(rec.status);
}

/** Taxonomic author string from the record (CSV: ``author``). */
export function authorOf(rec: SpeciesRecord): string {
  return str(rec.author);
}

/** Publication name string from the record (CSV: ``publication_name``). */
export function publicationNameOf(rec: SpeciesRecord): string {
  return str(rec.publication_name);
}

/** Publication year as a number, or null when absent/unparseable. */
export function publicationYearOf(rec: SpeciesRecord): number | null {
  const v = str(rec.publication_year);
  if (!v || v.toLowerCase() === "nan") return null;
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? n : null;
}
