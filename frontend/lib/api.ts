/**
 * Thin fetch client for the FastAPI backend. The only place that knows the
 * base URL and the endpoint shapes.
 */

import {
  ApiError,
  type SearchResponse,
  type SourcesResponse,
  type SuggestResponse,
  type TaxonomyResponse,
  type NotFoundDetail,
} from "./types";
import { backendNameForKey } from "./sources";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Fetch a JSON endpoint and return the parsed body.
 *
 * Throws ``ApiError`` on network failure or any non-2xx status, extracting
 * the ``detail`` field from FastAPI error bodies when present.
 *
 * Parameters
 * ----------
 * path : string
 *     Absolute path appended to BASE_URL (e.g. ``"/api/sources"``).
 *
 * Returns
 * -------
 * Promise<T>
 *     Parsed response body cast to T.
 */
async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
    });
  } catch (e) {
    throw new ApiError(
      0,
      `Could not reach the API at ${BASE_URL}. Is the FastAPI server running?`,
    );
  }

  if (!res.ok) {
    let detail: NotFoundDetail | string | undefined;
    try {
      const body = await res.json();
      detail = body?.detail ?? body;
    } catch {
      detail = res.statusText;
    }
    const message =
      typeof detail === "object" && detail?.message
        ? detail.message
        : typeof detail === "string"
          ? detail
          : `Request failed (${res.status})`;
    throw new ApiError(res.status, message, detail);
  }

  return (await res.json()) as T;
}

/** Fetch the list of available source keys from ``/api/sources``. */
export function getSources(): Promise<SourcesResponse> {
  return getJson<SourcesResponse>("/api/sources");
}

/**
 * Fetch all-source search results for a query from ``/api/search``.
 *
 * Parameters
 * ----------
 * query : string
 *     Species name to search.
 * mock : boolean
 *     When true the backend returns sample CSV data instead of live API calls.
 */
export function getSearch(
  query: string,
  mock = true,
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    query,
    use_routing: "false",
    mock: String(mock),
  });
  return getJson<SearchResponse>(`/api/search?${params.toString()}`);
}

/**
 * Fetch the per-source taxonomy comparison for a query from ``/api/taxonomy``.
 *
 * Parameters
 * ----------
 * query : string
 *     Species name to compare.
 * mock : boolean
 *     When true the backend returns sample data instead of live API calls.
 */
export function getTaxonomy(
  query: string,
  mock = true,
): Promise<TaxonomyResponse> {
  const params = new URLSearchParams({ query, mock: String(mock) });
  return getJson<TaxonomyResponse>(`/api/taxonomy?${params.toString()}`);
}

/** Ask the backend router which sources are recommended for this species. */
export function suggest(query: string): Promise<SuggestResponse> {
  const params = new URLSearchParams({ query });
  return getJson<SuggestResponse>(`/api/suggest?${params.toString()}`);
}

/**
 * Open a Server-Sent Events stream for a live search.
 *
 * Converts frontend source keys to backend display names before sending.
 * Returns a cleanup function that closes the EventSource.
 */
export function openSearchStream(
  query: string,
  sourceKeys: string[],
  onProgress: (source: string, done: number, total: number) => void,
  onResult: (data: SearchResponse) => void,
  onSuggestions: (names: string[]) => void,
  onSourceError: (source: string, message: string) => void,
  onError: (e: Error) => void,
): () => void {
  const backendNames = sourceKeys
    .map(backendNameForKey)
    .filter((n): n is string => n !== undefined);

  const params = new URLSearchParams({
    query,
    sources: backendNames.join(","),
  });

  const es = new EventSource(`${BASE_URL}/api/search/stream?${params.toString()}`);

  es.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data) as {
        type: string;
        source?: string;
        done?: number;
        total?: number;
        data?: SearchResponse;
        names?: string[];
        message?: string;
      };
      if (msg.type === "progress") {
        onProgress(msg.source ?? "", msg.done ?? 0, msg.total ?? 0);
      } else if (msg.type === "source_error") {
        onSourceError(msg.source ?? "", msg.message ?? "Unknown error");
      } else if (msg.type === "result" && msg.data) {
        onResult(msg.data);
        es.close();
      } else if (msg.type === "suggestions") {
        onSuggestions(msg.names ?? []);
        es.close();
      } else if (msg.type === "error") {
        onError(new Error(msg.message ?? "Unknown stream error"));
        es.close();
      }
    } catch {
      onError(new Error("Failed to parse stream event"));
      es.close();
    }
  };

  es.onerror = () => {
    onError(new Error("Search stream connection failed. Is the FastAPI server running?"));
    es.close();
  };

  return () => es.close();
}
