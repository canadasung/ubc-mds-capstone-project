/**
 * Thin fetch client for the FastAPI backend. The only place that knows the
 * base URL and the endpoint shapes.
 */

import {
  ApiError,
  type SearchResponse,
  type SourcesResponse,
  type TaxonomyResponse,
  type NotFoundDetail,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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

export function getSources(): Promise<SourcesResponse> {
  return getJson<SourcesResponse>("/api/sources");
}

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

export function getTaxonomy(
  query: string,
  mock = true,
): Promise<TaxonomyResponse> {
  const params = new URLSearchParams({ query, mock: String(mock) });
  return getJson<TaxonomyResponse>(`/api/taxonomy?${params.toString()}`);
}
