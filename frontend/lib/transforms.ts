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
  genusOf,
  linkOf,
  nameOf,
  publicationNameOf,
  publicationYearOf,
  sourceOf,
  speciesOf,
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
  kind: "source" | "genus" | "name";
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


// ── Relations view ────────────────────────────────────────────────────────

const REL_ROW_HEIGHT = 44;
const REL_GROUP_GAP = 56;
const REL_SOURCE_X = 0;
const REL_GENUS_X = 280;
const REL_NAME_X = 560;

/**
 * Builds a three-level tree for the Relations view:
 *   [Source]  →  [Genus]  →  [species binomial]
 *
 * Species are deduplicated within each (source, genus) pair. Each level is
 * vertically centred on the leaves it owns.
 */
export function buildRelationsGraph(records: SpeciesRecord[]): NodeGraph {
  const bySource = new Map<string, SpeciesRecord[]>();
  for (const rec of records) {
    const src = sourceLabel(rec);
    if (!bySource.has(src)) bySource.set(src, []);
    bySource.get(src)!.push(rec);
  }

  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  let currentY = 0;

  for (const [src, srcRecords] of bySource) {
    const srcId = `src:${src}`;
    const sourceStartY = currentY;
    let totalSpecies = 0;

    // Group by genus within this source, preserving first-seen order
    const byGenus = new Map<string, SpeciesRecord[]>();
    for (const rec of srcRecords) {
      const g = genusOf(rec) || "Unknown";
      if (!byGenus.has(g)) byGenus.set(g, []);
      byGenus.get(g)!.push(rec);
    }

    for (const [genus, genusRecs] of byGenus) {
      const genusId = `${srcId}|g:${genus}`;
      const genusStartY = currentY;

      // Deduplicate species within this (source, genus) pair
      const seen = new Set<string>();
      const species: Array<{ epithet: string; full: string; url: string | null }> = [];
      for (const rec of genusRecs) {
        const full = nameOf(rec);
        if (!seen.has(full)) {
          seen.add(full);
          species.push({ epithet: speciesOf(rec) || full, full, url: linkOf(rec) });
        }
      }

      species.forEach((s, j) => {
        const nodeId = `${genusId}|${j}`;
        nodes.push({ id: nodeId, kind: "name", label: s.epithet, full: s.full, url: s.url, x: REL_NAME_X, y: currentY + j * REL_ROW_HEIGHT });
        edges.push({ id: `e:${genusId}-${j}`, source: genusId, target: nodeId });
      });

      nodes.push({
        id: genusId,
        kind: "genus",
        label: genus,
        url: null,
        x: REL_GENUS_X,
        y: genusStartY + ((species.length - 1) / 2) * REL_ROW_HEIGHT,
      });
      edges.push({ id: `e:${srcId}-${genusId}`, source: srcId, target: genusId });

      currentY += species.length * REL_ROW_HEIGHT;
      totalSpecies += species.length;
    }

    nodes.push({
      id: srcId,
      kind: "source",
      label: `${src}\n(${totalSpecies})`,
      full: fullForLabel(src),
      url: null,
      x: REL_SOURCE_X,
      y: sourceStartY + ((totalSpecies - 1) / 2) * REL_ROW_HEIGHT,
    });

    currentY += REL_GROUP_GAP;
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

export interface YearGroup {
  year: number;
  /** Records published this year with status "Accepted". */
  accepted: TimelineEntry[];
  /** Records published this year that are not accepted (synonyms or unknown). */
  synonyms: TimelineEntry[];
  /** True when at least one record published this year is accepted. */
  isAccepted: boolean;
  /** Representative source label for the year, used for the axis dot color. */
  source: string;
  /** Total number of records published this year. */
  count: number;
}

/**
 * Collapse dated timeline entries into one group per publication year.
 *
 * Records sharing a year are merged into a single ``YearGroup`` whose
 * ``accepted`` and ``synonyms`` lists partition them by status. A group counts
 * as accepted when at least one of its records is accepted, so a year holding
 * both accepted and synonym records is treated as accepted.
 *
 * Parameters
 * ----------
 * dated : TimelineEntry[]
 *     Entries that have a publication year.
 *
 * Returns
 * -------
 * YearGroup[]
 *     One group per distinct year, ordered oldest to newest.
 */
export function groupTimelineByYear(dated: TimelineEntry[]): YearGroup[] {
  const byYear = new Map<number, TimelineEntry[]>();
  for (const e of dated) {
    if (e.year == null) continue;
    const list = byYear.get(e.year);
    if (list) list.push(e);
    else byYear.set(e.year, [e]);
  }

  const groups: YearGroup[] = [];
  for (const [year, items] of byYear) {
    const accepted = items.filter((e) => e.status === "Accepted");
    const synonyms = items.filter((e) => e.status !== "Accepted");
    const representative = accepted[0] ?? synonyms[0];
    groups.push({
      year,
      accepted,
      synonyms,
      isAccepted: accepted.length > 0,
      source: representative.source,
      count: items.length,
    });
  }

  groups.sort((a, b) => a.year - b.year);
  return groups;
}
