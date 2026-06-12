/**
 * TypeScript mirrors of the FastAPI JSON contract (backend_api/routers/*.py).
 * One flat record == one row of the underlying sample CSV (snake_case columns).
 */

export interface SpeciesRecord {
  api_name: string; // source the row came from, e.g. "GBIF"
  kingdom: string | null;
  phylum: string | null;
  class: string | null;
  family: string | null;
  subfamily: string | null;
  genus: string | null;
  species: string | null;
  api_internal_id: string | number | null;
  author: string | null;
  publication_name: string | null;
  publication_year: number | string | null;
  api_link: string | null;
  status: string | null; // "Accepted" | "Synonym" | ...
  source_name: string | null;
  // tolerate extra/unknown columns from the backend
  [key: string]: string | number | null | undefined;
}

/** GET /api/search */
export interface SearchResponse {
  query: string;
  sources: string[]; // source KEYS that were queried, e.g. ["gbif", "col"]
  results: SpeciesRecord[];
}

/** GET /api/sources */
export interface SourcesResponse {
  sources: string[];
}

/** One row of GET /api/taxonomy "sources". Rank keys are title-case. */
export interface TaxonomyRow {
  source: string;
  synonym_count: number;
  [rank: string]: string | number | null;
}

/** GET /api/taxonomy */
export interface TaxonomyResponse {
  query: string;
  ranks: string[];
  sources: TaxonomyRow[];
  disagreements: string[];
}

/** Body of a 404 from /api/search or /api/taxonomy. */
export interface NotFoundDetail {
  message: string;
  available?: string[];
}

/** Thrown by the fetch client on non-2xx responses. */
export class ApiError extends Error {
  status: number;
  detail?: NotFoundDetail | string;
  /** Convenience: "Did you mean?" suggestions parsed from a 404 body. */
  available?: string[];

  constructor(
    status: number,
    message: string,
    detail?: NotFoundDetail | string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    if (detail && typeof detail === "object" && Array.isArray(detail.available)) {
      this.available = detail.available;
    }
  }
}
