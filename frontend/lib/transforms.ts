/**
 * Pure transforms from SpeciesRecord[] into view-ready shapes. These port the
 * data-prep logic from the Streamlit views:
 *   - buildPresenceTable  ← view_table.py
 *   - buildNodeGraph      ← view_node.py
 *   - buildTimeline       ← view_timeline.py
 *
 * The Taxonomic view does NOT transform here — it consumes /api/taxonomy
 * directly, keeping the disagreement logic on the backend.
 */

import {
  authorOf,
  linkOf,
  nameOf,
  publicationNameOf,
  publicationYearOf,
  sourceOf,
  statusOf,
} from "./fields";
import { fullForLabel, keyForApiName, labelForKey } from "./sources";
import type { SpeciesRecord } from "./types";

function normalize(s: string): string {
  return s.trim().replace(/\s+/g, " ").toLowerCase();
}

function sourceLabel(rec: SpeciesRecord): string {
  return labelForKey(keyForApiName(sourceOf(rec)));
}

// ── Table view ────────────────────────────────────────────────────────────

export interface PresenceRow {
  name: string;
  isQuery: boolean;
  /** sourceLabel → url (string), null (present, no link), or undefined (absent) */
  cells: Record<string, string | null | undefined>;
  count: number;
}

export interface PresenceTable {
  sources: string[]; // ordered source labels (columns)
  rows: PresenceRow[];
}

export function buildPresenceTable(
  records: SpeciesRecord[],
  query: string,
): PresenceTable {
  const queryNorm = normalize(query);
  const sources: string[] = []; // first-seen order
  const presence = new Map<string, Map<string, string | null>>();

  for (const rec of records) {
    const name = nameOf(rec);
    if (!name) continue;
    const src = sourceLabel(rec);
    const url = linkOf(rec);

    if (!sources.includes(src)) sources.push(src);
    if (!presence.has(name)) presence.set(name, new Map());

    const cells = presence.get(name)!;
    // First non-null link for a (name, source) wins; accepted rows precede
    // synonyms in the data so the canonical link is preferred.
    if (!cells.has(src) || (cells.get(src) == null && url != null)) {
      cells.set(src, url);
    }
  }

  const rows: PresenceRow[] = [];
  for (const [name, cells] of presence) {
    const cellObj: Record<string, string | null | undefined> = {};
    let count = 0;
    for (const src of sources) {
      if (cells.has(src)) {
        cellObj[src] = cells.get(src);
        count += 1;
      }
    }
    rows.push({ name, isQuery: normalize(name) === queryNorm, cells: cellObj, count });
  }

  rows.sort((a, b) => {
    if (a.isQuery !== b.isQuery) return a.isQuery ? -1 : 1; // query first
    return b.count - a.count; // then most-recognized
  });

  return { sources, rows };
}

// ── Node view ─────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  kind: "query" | "source" | "name";
  label: string;
  /** Official long name for source nodes, shown on hover. */
  full?: string;
  url: string | null;
  x: number;
  y: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface NodeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const ROW_HEIGHT = 150;
const SYN_X_OFFSET = 280;
const SYN_X_SPACING = 200;

/** source label → search-page URL template (ported from view_node.py). */
const SOURCE_URL_TEMPLATES: Record<string, string | undefined> = {
  GBIF: "https://www.gbif.org/search?q={q}",
  GenBank: "https://www.ncbi.nlm.nih.gov/search/all/?term={q}",
  MyCoPortal: "https://mycoportal.org/portal/taxa/index.php?taxon={q}",
  "Bryophyte Portal": "https://bryophyteportal.org/portal/taxa/index.php?taxon={q}",
  "Macroalgae Portal": "https://macroalgae.org/portal/taxa/index.php?taxon={q}",
};

export function buildNodeGraph(
  records: SpeciesRecord[],
  query: string,
): NodeGraph {
  // group by source label, preserving first-seen order
  const grouped = new Map<string, SpeciesRecord[]>();
  for (const rec of records) {
    const src = sourceLabel(rec);
    if (!grouped.has(src)) grouped.set(src, []);
    grouped.get(src)!.push(rec);
  }

  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const total = grouped.size;
  const queryY = (ROW_HEIGHT * (total + 1)) / 2;

  nodes.push({
    id: "center",
    kind: "query",
    label: query || "?",
    url: null,
    x: -SYN_X_OFFSET,
    y: queryY,
  });

  let rowIdx = 0;
  for (const [src, group] of grouped) {
    rowIdx += 1;
    const y = ROW_HEIGHT * rowIdx;
    const template = SOURCE_URL_TEMPLATES[src];
    const dbUrl = template
      ? template.replace("{q}", encodeURIComponent(query))
      : null;

    const srcId = `src:${src}`;
    nodes.push({
      id: srcId,
      kind: "source",
      label: `${src}\n${group.length} name${group.length === 1 ? "" : "s"} found`,
      full: fullForLabel(src),
      url: dbUrl,
      x: 0,
      y,
    });
    edges.push({ id: `e:center-${srcId}`, source: "center", target: srcId });

    group.forEach((rec, j) => {
      const name = nameOf(rec);
      const nodeId = `${srcId}|${name}|${j}`;
      nodes.push({
        id: nodeId,
        kind: "name",
        label: name,
        url: linkOf(rec),
        x: SYN_X_OFFSET + SYN_X_SPACING * j,
        y,
      });
      edges.push({ id: `e:${srcId}-${j}`, source: srcId, target: nodeId });
    });
  }

  return { nodes, edges };
}

// ── Timeline view ───────────────────────────────────────────────────────────

export interface TimelineEntry {
  name: string;
  author: string;
  publicationName: string;
  source: string;
  url: string | null;
  status: string;
  year: number | null;
}

export interface TimelineData {
  dated: TimelineEntry[];
  undated: TimelineEntry[];
  sourceColors: Record<string, string>;
}

/** Evenly-spaced HSL hue per source (ported from _source_accent). */
function sourceAccent(index: number, total: number): string {
  const h = (index / Math.max(total, 1)) * 360;
  return `hsl(${h.toFixed(0)}, 60%, 45%)`;
}

export function buildTimeline(records: SpeciesRecord[]): TimelineData {
  const dated: TimelineEntry[] = [];
  const undated: TimelineEntry[] = [];

  for (const rec of records) {
    const entry: TimelineEntry = {
      name: nameOf(rec),
      author: authorOf(rec) || "—",
      publicationName: publicationNameOf(rec) || "—",
      source: sourceLabel(rec),
      url: linkOf(rec),
      status: statusOf(rec) || "—",
      year: publicationYearOf(rec),
    };
    (entry.year != null ? dated : undated).push(entry);
  }

  const allSources = Array.from(
    new Set([...dated, ...undated].map((e) => e.source)),
  ).sort();
  const sourceColors: Record<string, string> = {};
  allSources.forEach((src, i) => {
    sourceColors[src] = sourceAccent(i, allSources.length);
  });

  return { dated, undated, sourceColors };
}
