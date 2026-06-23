"use client";

/**
 * Timeline view for species name records.
 *
 * Renders dated taxonomy entries on a CSS timeline, oriented either horizontally
 * (a proportional time axis running left to right) or vertically, sharing one
 * card component. Records that share a publication year are combined into a
 * single card for that year, headed by the name and year and listing one labeled
 * block per record (API, status, author, source). A year card is treated as
 * accepted when any of its records is accepted: accepted years display square
 * (green), synonym-only years rounded (purple), and mixed years a split
 * square-over-rounded border. Axis dots are uniform black circles and do not
 * encode source or status. Undated entries appear in a collapsible table below
 * either view.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  Alert,
  Anchor,
  Button,
  Collapse,
  Group,
  SegmentedControl,
  Table,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";

import { useFilteredRecords } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import {
  buildTimeline,
  groupTimelineByYear,
  type TimelineEntry,
  type YearGroup,
} from "@/lib/transforms";

/** Accent color for accepted names (status text and card border), both views. */
const COLOR_ACCEPTED = "#2f9e44";
/** Accent color for synonym and unknown-status names, both views. */
const COLOR_SYNONYM = "#9c36b5";
/** Link color, kept distinct from the accepted-name color so links stand out. */
const COLOR_LINK = "#1c7ed6";

/**
 * Text color for a record status: green for accepted, purple for synonym, gray
 * for anything else (unknown or unavailable).
 *
 * Parameters
 * ----------
 * status : string
 *     A record's status value, e.g. "Accepted" or "Synonym".
 *
 * Returns
 * -------
 * string
 *     A CSS color string.
 */
function statusColor(status: string): string {
  if (status === "Accepted") return COLOR_ACCEPTED;
  if (status === "Synonym") return COLOR_SYNONYM;
  return "#888";
}

/** Extra horizontal margin in pixels past the first/last card on the axis. */
const END_PAD_PX = 20;
/** Estimated rendered height in pixels of a collapsed card (either view). */
const COLLAPSED_CARD_HEIGHT_PX = 64;
/**
 * Target text width in pixels of an expanded card box. Card text is wrapped to
 * fit this width so the box stays a predictable size and does not clip.
 */
const CARD_WIDTH_EXPANDED = 300;
/** Approximate monospace character advance at the card font size, in pixels. */
const CARD_CHAR_PX = 7.8;
/**
 * Approximate characters per wrapped line in an expanded card, derived from the
 * target card width. The browser wraps the card text itself; this value lets the
 * layout estimate how many lines a field wraps to, and therefore each card's
 * height, before it is rendered.
 */
const CARD_WRAP_CHARS = Math.floor((CARD_WIDTH_EXPANDED - 24) / CARD_CHAR_PX);

/** Minimum zoom level for the timeline scale control. */
const ZOOM_MIN = 0.4;
/** Maximum zoom level for the timeline scale control. */
const ZOOM_MAX = 2.4;
/** Zoom increment per click of the scale control. */
const ZOOM_STEP = 0.2;
/** Fixed height in pixels of the zoomable timeline canvas. */
const CANVAS_HEIGHT = 720;
/**
 * Length in pixels of the vertical-view axis (how far the years are spread out).
 * Increase to make the axis longer; the canvas scrolls when this exceeds
 * CANVAS_HEIGHT. Adjust this value to taste.
 */
const VERTICAL_AXIS_HEIGHT = 1000;
/** Natural content width in pixels of the vertical view (cards on both sides). */
const VERTICAL_WIDTH = 760;
/** Vertical pixel gap between stacked lanes in the horizontal view. */
const LANE_GAP_PX = 18;
/** Minimum horizontal gap (pixels) between two cards sharing a lane (horizontal). */
const LANE_X_GAP_PX = 12;
/** Horizontal pixel gap between stacked card columns in the vertical view. */
const COLUMN_GAP_PX = 16;
/** Minimum vertical gap (pixels) between two cards sharing a column (vertical). */
const COLUMN_Y_GAP_PX = 12;

/**
 * Word-wrap plain text to a maximum line length.
 *
 * Words are kept whole where possible; a single word longer than the limit is
 * hard-broken. Used to estimate how many lines a field will wrap to, which feeds
 * each card's height estimate for the layout.
 *
 * Parameters
 * ----------
 * text : string
 *     The plain text to wrap.
 * maxChars : number
 *     Maximum number of characters per line.
 *
 * Returns
 * -------
 * string[]
 *     The wrapped lines (at least one, possibly empty).
 */
function wrapLines(text: string, maxChars: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (let word of words) {
    while (word.length > maxChars) {
      if (current) {
        lines.push(current);
        current = "";
      }
      lines.push(word.slice(0, maxChars));
      word = word.slice(maxChars);
    }
    if (!current) current = word;
    else if (current.length + 1 + word.length <= maxChars) current += " " + word;
    else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines.length ? lines : [""];
}

/**
 * Count the rendered text lines of a single record block.
 *
 * API and Status occupy one line each; Author and Source wrap to the card width.
 *
 * Parameters
 * ----------
 * e : TimelineEntry
 *     The record whose lines are counted.
 * maxChars : number
 *     Maximum number of characters per wrapped line, matching the rendered card.
 *
 * Returns
 * -------
 * number
 *     The number of text lines the record occupies.
 */
function recordLineCount(e: TimelineEntry, maxChars: number): number {
  return (
    2 +
    wrapLines(`Author: ${e.author}`, maxChars).length +
    wrapLines(`Source: ${e.publicationName}`, maxChars).length
  );
}

/**
 * Estimate the rendered pixel height of an expanded year card.
 *
 * Counts the header line plus, for each record, a separating blank line and its
 * labeled field lines. The estimate drives the lane and column spacing in both
 * views (and the views' end padding) so expanded cards neither overlap each
 * other nor clip at the canvas edge.
 *
 * Parameters
 * ----------
 * group : YearGroup
 *     The year group whose expanded card height is estimated.
 * maxChars : number
 *     Maximum number of characters per wrapped line, matching the rendered card.
 *
 * Returns
 * -------
 * number
 *     Estimated card height in pixels.
 */
function estimateExpandedCardPx(group: YearGroup, maxChars: number): number {
  const LINE_PX = 18;
  let lines = 1; // header
  for (const e of [...group.accepted, ...group.synonyms]) {
    lines += 1 + recordLineCount(e, maxChars); // separating gap + the record
  }
  return lines * LINE_PX + 24;
}

/**
 * Estimate the rendered pixel width of a collapsed year card.
 *
 * A collapsed card shows the representative name (genus and epithet stacked) and
 * an optional "+N more" line, centered; its width is the longest of those lines,
 * clamped to the card's min and max width. The estimate feeds the horizontal
 * lane packing and end padding so collapsed cards reserve the right room.
 *
 * Parameters
 * ----------
 * group : YearGroup
 *     The year group whose collapsed card width is estimated.
 *
 * Returns
 * -------
 * number
 *     Estimated card width in pixels.
 */
function estimateCollapsedCardWidthPx(group: YearGroup): number {
  const representative = group.accepted[0] ?? group.synonyms[0];
  const parts = representative.name.trim().split(/\s+/);
  const moreChars = group.count > 1 ? `+${group.count - 1} more`.length : 0;
  const longest = Math.max(moreChars, ...parts.map((p) => p.length));
  return Math.min(260, Math.max(120, Math.round(longest * CARD_CHAR_PX + 28)));
}

/**
 * Greedily assign each item to a lane on its side so items sharing a lane never
 * overlap along the axis.
 *
 * Each item keeps the side given by its index parity (even -> side 0, odd ->
 * side 1). Within a side, an item that would overlap the previous item in lane 0
 * is pushed out to lane 1, then lane 2, and so on, so only clustered items move
 * away from the axis while spread-out items stay close. Items must be ordered by
 * ascending center.
 *
 * Parameters
 * ----------
 * centers : number[]
 *     Pixel center of each item along the axis (the card's x for horizontal, its
 *     y for vertical).
 * halves : number[]
 *     Half-size of each item along the axis in pixels (half width for horizontal,
 *     half height for vertical).
 * gap : number
 *     Minimum empty space in pixels between two items sharing a lane.
 *
 * Returns
 * -------
 * { side: number; lane: number }[]
 *     The side (0 or 1) and lane index (0 = closest to the axis) for each item.
 */
function assignLanes(
  centers: number[],
  halves: number[],
  gap: number,
): { side: number; lane: number }[] {
  const laneEnds: [number[], number[]] = [[], []];
  return centers.map((center, i) => {
    const side = i % 2;
    const lanes = laneEnds[side];
    const start = center - halves[i];
    let lane = lanes.findIndex((end) => end + gap <= start);
    if (lane === -1) {
      lane = lanes.length;
      lanes.push(0);
    }
    lanes[lane] = center + halves[i];
    return { side, lane };
  });
}

// ---- Shared timeline card sub-components ----------------------------------

/**
 * Small external-link glyph rendered inline after a link's text.
 *
 * Drawn as an inline SVG so it needs no icon dependency and inherits the link
 * color through ``currentColor``.
 *
 * Returns
 * -------
 * JSX.Element
 *     An SVG external-link icon.
 */
function ExternalLinkIcon() {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ marginLeft: 3, verticalAlign: "-1px" }}
      aria-hidden
    >
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

/**
 * Render one record as a block of labeled fields in a year card.
 *
 * Shows API (the source database, a link when available), Status (colored by
 * accepted/synonym), Author, and Source (the publication), each on its own line.
 *
 * Parameters
 * ----------
 * entry : TimelineEntry
 *     The record to render.
 * first : boolean, optional
 *     When true, drops the top margin so the block sits flush with the top of
 *     its section (used for the first record after a section separator).
 */
function RecordBlock({ entry, first }: { entry: TimelineEntry; first?: boolean }) {
  const label = (text: string) => <span style={{ color: "#888" }}>{text}</span>;
  return (
    <div style={{ marginTop: first ? 0 : 8 }}>
      <div>
        {label("API:")}{" "}
        {entry.url ? (
          <a
            href={entry.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: COLOR_LINK }}
            onClick={(e) => e.stopPropagation()}
          >
            <span style={{ textDecoration: "underline" }}>{entry.source}</span>
            <ExternalLinkIcon />
          </a>
        ) : (
          entry.source
        )}
      </div>
      <div>
        {label("Status:")}{" "}
        <span style={{ color: statusColor(entry.status) }}>{entry.status}</span>
      </div>
      <div>
        {label("Author:")} {entry.author}
      </div>
      <div>
        {label("Source:")} {entry.publicationName}
      </div>
    </div>
  );
}

interface TimelineCardProps {
  /** Year group rendered by the card. */
  group: YearGroup;
  /** Whether the card is currently in the expanded state. */
  isOpen: boolean;
  /** Callback invoked when the user clicks the card. */
  onToggle: () => void;
}

/**
 * Clickable year card shared by the horizontal and vertical timeline views.
 *
 * An accepted-only year gets a square green border; a synonym-only year gets a
 * rounded purple border. A year holding both is split into a green square-topped
 * accepted section over a purple rounded-bottom synonym section: when expanded,
 * the border changes from green to purple at the real accepted/synonym boundary,
 * so the green border stops there rather than half-way; when collapsed it falls
 * back to a half-and-half gradient border. Clicking toggles between a compact
 * representative-name display and an expanded view with a "Name, Year" header
 * followed by one labeled block per record (API, status, author, source).
 *
 * Parameters
 * ----------
 * group : YearGroup
 *     The year group providing the records to display.
 * isOpen : boolean
 *     True when the card should render in the expanded state.
 * onToggle : () => void
 *     Callback invoked on click to toggle the expanded state.
 */
function TimelineCard({ group, isOpen, onToggle }: TimelineCardProps) {
  const hasAccepted = group.accepted.length > 0;
  const hasSynonym = group.synonyms.length > 0;
  const representative = group.accepted[0] ?? group.synonyms[0];
  const nameParts = representative.name.trim().split(/\s+/);

  const baseStyle: CSSProperties = {
    cursor: "pointer",
    fontFamily: "Courier New, monospace",
    fontSize: 13,
    color: "#333",
    maxWidth: isOpen ? 300 : 260,
    minWidth: 120,
    textAlign: isOpen ? "left" : "center",
    userSelect: "none",
    lineHeight: 1.5,
  };

  // Mixed and expanded: render two bordered sections, accepted (green, square
  // top, no bottom border) over synonyms (purple, rounded bottom, no top border).
  // The side borders change from green to purple at the accepted/synonym boundary
  // with no line across it, instead of a fixed half-way split.
  if (hasAccepted && hasSynonym && isOpen) {
    return (
      <div onClick={onToggle} style={baseStyle}>
        <div
          style={{
            borderTop: `2px solid ${COLOR_ACCEPTED}`,
            borderLeft: `2px solid ${COLOR_ACCEPTED}`,
            borderRight: `2px solid ${COLOR_ACCEPTED}`,
            borderRadius: 0,
            padding: "10px 14px",
            backgroundColor: "white",
          }}
        >
          <div style={{ fontWeight: "bold", fontSize: 15, marginBottom: 4 }}>
            {representative.name}, {group.year}
          </div>
          {group.accepted.map((e, i) => (
            <RecordBlock key={`a-${e.source}-${i}`} entry={e} />
          ))}
        </div>
        <div
          style={{
            borderLeft: `2px solid ${COLOR_SYNONYM}`,
            borderRight: `2px solid ${COLOR_SYNONYM}`,
            borderBottom: `2px solid ${COLOR_SYNONYM}`,
            borderRadius: "0 0 10px 10px",
            padding: "10px 14px",
            backgroundColor: "white",
          }}
        >
          {group.synonyms.map((e, i) => (
            <RecordBlock key={`s-${e.source}-${i}`} entry={e} first={i === 0} />
          ))}
        </div>
      </div>
    );
  }

  // Border reflects the record statuses. A mixed year uses a gradient border
  // (green top, purple bottom) with square top corners and rounded bottom
  // corners; the two-background trick lets the radius clip the border gradient.
  let borderStyle: CSSProperties;
  if (hasAccepted && hasSynonym) {
    borderStyle = {
      border: "2px solid transparent",
      borderRadius: "0 0 10px 10px",
      background:
        "linear-gradient(#fff, #fff) padding-box, " +
        `linear-gradient(to bottom, ${COLOR_ACCEPTED} 50%, ${COLOR_SYNONYM} 50%) border-box`,
    };
  } else if (hasAccepted) {
    borderStyle = { border: `2px solid ${COLOR_ACCEPTED}`, borderRadius: 0, backgroundColor: "white" };
  } else {
    borderStyle = { border: `2px solid ${COLOR_SYNONYM}`, borderRadius: 10, backgroundColor: "white" };
  }

  return (
    <div
      onClick={onToggle}
      style={{
        ...baseStyle,
        ...borderStyle,
        padding: isOpen ? "10px 14px" : "6px 10px",
      }}
    >
      {isOpen ? (
        <div>
          <div style={{ fontWeight: "bold", fontSize: 15, marginBottom: 4 }}>
            {representative.name}, {group.year}
          </div>
          {[...group.accepted, ...group.synonyms].map((e, i) => (
            <RecordBlock key={`${e.source}-${i}`} entry={e} />
          ))}
        </div>
      ) : (
        <div style={{ fontWeight: "bold" }}>
          {nameParts.length > 1 ? (
            <>
              {nameParts[0]}
              <br />
              {nameParts.slice(1).join(" ")}
            </>
          ) : (
            representative.name
          )}
          {group.count > 1 && (
            <div style={{ color: "#888", fontWeight: "normal", fontSize: 11 }}>
              +{group.count - 1} more
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** A single laid-out vertical card with its axis position and side/column. */
interface VerticalItem {
  /** Canonical group index. */
  ci: number;
  /** Pixel offset from the top of the axis to the card's center. */
  top: number;
  /** True when the card sits on the left of the axis. */
  isLeft: boolean;
  /** Horizontal distance in pixels from the axis to the card's near edge. */
  dist: number;
}

/** The computed vertical-view layout: laid-out items and the canvas extent. */
interface VerticalLayout {
  items: VerticalItem[];
  /** Total height of the axis area in pixels. */
  totalHeight: number;
  /** Total width needed to hold the farthest columns on both sides. */
  totalWidth: number;
}

/**
 * Compute the absolute layout for the vertical timeline.
 *
 * Cards sit at their publication year along a proportional axis and alternate
 * left and right. When two same-side cards would overlap vertically, the later
 * one is pushed to a farther column (greedy lane packing) so clustered cards
 * spread sideways instead of overlapping. The total width grows only when extra
 * columns are needed. The top and bottom padding grow to cover any expanded
 * card that reaches past the first or last dot, so the axis lengthens (and the
 * canvas scrolls) on expand rather than clipping a card at the canvas edge.
 *
 * Parameters
 * ----------
 * groups : YearGroup[]
 *     Year groups, oldest to newest.
 * order : number[]
 *     Canonical group indices in display order (top to bottom).
 * expanded : Set<number>
 *     Set of group indices whose cards are in the expanded state.
 *
 * Returns
 * -------
 * VerticalLayout
 *     The laid-out items plus the total height and width of the canvas.
 */
function computeVerticalLayout(
  groups: YearGroup[],
  order: number[],
  expanded: Set<number>,
): VerticalLayout {
  const CENTER_WIDTH = 64;
  const CARD_W = 300;
  const columnStep = CARD_W + COLUMN_GAP_PX;
  const n = order.length;
  if (n === 0) {
    return { items: [], totalHeight: 0, totalWidth: VERTICAL_WIDTH };
  }

  const years = order.map((ci) => groups[ci].year);
  const heights = order.map((ci) =>
    expanded.has(ci) ? estimateExpandedCardPx(groups[ci], CARD_WRAP_CHARS) : COLLAPSED_CARD_HEIGHT_PX,
  );

  // Proportional axis: years keep their spacing, set so the span fills
  // VERTICAL_AXIS_HEIGHT at the base padding.
  const span = Math.max(1, Math.abs(years[n - 1] - years[0]));
  const baseTopPad = Math.max(28, heights[0] / 2 + 8);
  const baseBottomPad = Math.max(28, heights[n - 1] / 2 + 8);
  const usable = Math.max(40, VERTICAL_AXIS_HEIGHT - baseTopPad - baseBottomPad);
  const pxPerYear = usable / span;
  const off = years.map((y) => Math.abs(y - years[0]) * pxPerYear);

  // Cards are centered on their year dot, so a tall expanded card can reach past
  // the first/last dot. Grow the end padding to cover each card's overhang
  // beyond its dot, which lengthens the axis (and scrolls) when cards expand
  // instead of clipping a card against the top or bottom of the canvas.
  const OVERHANG_MARGIN = 8;
  let topPad = baseTopPad;
  let bottomPad = baseBottomPad;
  for (let d = 0; d < n; d++) {
    topPad = Math.max(topPad, OVERHANG_MARGIN + heights[d] / 2 - off[d]);
    bottomPad = Math.max(bottomPad, OVERHANG_MARGIN + heights[d] / 2 - (off[n - 1] - off[d]));
  }
  const totalHeight = topPad + off[n - 1] + bottomPad;
  const tops = off.map((o) => topPad + o);

  // Column packing: same-side cards that would overlap vertically move to a
  // farther column (lane) instead of overlapping.
  const laneOf = assignLanes(
    tops,
    heights.map((h) => h / 2),
    COLUMN_Y_GAP_PX,
  );
  const maxLane = Math.max(0, ...laneOf.map((l) => l.lane));

  const items: VerticalItem[] = order.map((ci, d) => ({
    ci,
    top: tops[d],
    isLeft: laneOf[d].side === 0,
    dist: CENTER_WIDTH + laneOf[d].lane * columnStep,
  }));
  const totalWidth = 2 * (CENTER_WIDTH + maxLane * columnStep + CARD_W) + 24;

  return { items, totalHeight, totalWidth };
}

interface VerticalTimelineProps {
  /** Precomputed layout (positions, sides, columns, canvas extent). */
  layout: VerticalLayout;
  /** Year groups (indexed by the items' canonical indices). */
  groups: YearGroup[];
  /** Indices (into groups) of currently expanded cards. */
  expanded: Set<number>;
  /** Callback to toggle the expanded state of the card at the given index. */
  onToggle: (i: number) => void;
}

/**
 * Vertical CSS timeline for year-grouped taxonomy entries.
 *
 * Renders the cards from a precomputed layout. Cards sit by publication year
 * along a central vertical axis (a proportional time scale, matching the
 * horizontal view), alternating left and right, with clustered cards spread into
 * farther columns so they do not overlap. Each year has a black dot and a year
 * label. Accepted-only years use square cards, synonym-only years rounded cards,
 * and mixed years a split square-over-rounded card.
 *
 * Parameters
 * ----------
 * layout : VerticalLayout
 *     Precomputed item positions and canvas extent from computeVerticalLayout.
 * groups : YearGroup[]
 *     Year groups, indexed by each item's canonical index.
 * expanded : Set<number>
 *     Set of group indices whose cards are in the expanded state.
 * onToggle : (i: number) => void
 *     Callback invoked with the card index to toggle its expanded state.
 */
function VerticalTimeline({ layout, groups, expanded, onToggle }: VerticalTimelineProps) {
  const { items, totalHeight } = layout;

  return (
    <div style={{ position: "relative", height: totalHeight }}>
      {/* Central vertical axis line */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          left: "50%",
          transform: "translateX(-50%)",
          top: 0,
          bottom: 0,
          width: 2,
          backgroundColor: "#bdc3c7",
          zIndex: 0,
        }}
      />
      {/* End caps marking where the timeline starts and ends */}
      {(["top", "bottom"] as const).map((edge) => (
        <div
          key={edge}
          aria-hidden
          style={{
            position: "absolute",
            left: "50%",
            [edge]: 0,
            transform: "translateX(-50%)",
            width: 16,
            height: 3,
            backgroundColor: "#868e96",
            zIndex: 0,
          }}
        />
      ))}

      {items.map((item) => {
        const { ci } = item;
        const group = groups[ci];
        const isLeft = item.isLeft;
        const isOpen = expanded.has(ci);
        const top = item.top;
        const cardEdge = `calc(50% + ${item.dist}px)`;

        return (
          <div key={`year-${group.year}-${ci}`}>
            {/* Dashed connector from the central axis to this card's near edge */}
            <div
              aria-hidden
              style={{
                position: "absolute",
                top,
                left: isLeft ? undefined : "50%",
                right: isLeft ? "50%" : undefined,
                width: item.dist,
                borderTop: "1px dashed #bdc3c7",
                zIndex: 0,
              }}
            />

            {/* Card, vertically centered on its year position */}
            <div
              style={{
                position: "absolute",
                top,
                transform: "translateY(-50%)",
                left: isLeft ? undefined : cardEdge,
                right: isLeft ? cardEdge : undefined,
                zIndex: 1,
              }}
            >
              <TimelineCard group={group} isOpen={isOpen} onToggle={() => onToggle(ci)} />
            </div>

            {/* Year label, on the card's side next to the dot */}
            <div
              style={{
                position: "absolute",
                top,
                transform: "translateY(-50%)",
                left: isLeft ? undefined : "calc(50% + 10px)",
                right: isLeft ? "calc(50% + 10px)" : undefined,
                fontFamily: "Courier New, monospace",
                fontWeight: "bold",
                fontSize: 11,
                lineHeight: 1,
                color: "#333",
                backgroundColor: "rgba(255,255,255,0.85)",
                padding: "1px 3px",
                whiteSpace: "nowrap",
                zIndex: 2,
              }}
            >
              {group.year}
            </div>

            {/* Axis dot at the year position */}
            <div
              aria-hidden
              style={{
                position: "absolute",
                top,
                left: "50%",
                transform: "translate(-50%, -50%)",
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: "#000",
                boxShadow: "0 0 0 2px white",
                zIndex: 3,
              }}
            />
          </div>
        );
      })}
    </div>
  );
}

/** A single laid-out horizontal card with its axis position and lane. */
interface HorizontalItem {
  /** Canonical group index. */
  ci: number;
  /** Pixel offset from the left edge to the card's horizontal center (its dot). */
  centerX: number;
  /** True when the card sits above the axis. */
  isTop: boolean;
  /** Vertical distance in pixels from the axis to the card's near edge. */
  dist: number;
}

/** The computed horizontal-view layout: laid-out items and the canvas extent. */
interface HorizontalLayout {
  items: HorizontalItem[];
  /** Pixel offset from the top to the horizontal axis line. */
  axisY: number;
  /** Total width of the axis area in pixels. */
  totalWidth: number;
  /** Total height needed to hold the farthest lanes on both sides. */
  totalHeight: number;
}

/**
 * Compute the absolute layout for the horizontal timeline.
 *
 * Cards sit at their publication year along a proportional axis whose length is
 * fixed to the canvas width, so the whole span fits the view at zoom one. Cards
 * alternate above and below the axis; when two same-side cards would overlap
 * horizontally, the later one is pushed to a farther lane (greedy lane packing)
 * so clustered cards stack outward instead of overlapping, and the canvas grows
 * taller. The left and right padding grow to cover any wide card that reaches
 * past the first or last dot. The axis is centered vertically so both sides get
 * equal room.
 *
 * Parameters
 * ----------
 * groups : YearGroup[]
 *     Year groups, oldest to newest.
 * order : number[]
 *     Canonical group indices in display order (left to right).
 * expanded : Set<number>
 *     Set of group indices whose cards are in the expanded state.
 * canvasWidth : number
 *     Width of the scrollable canvas; the axis length is fixed to it.
 *
 * Returns
 * -------
 * HorizontalLayout
 *     The laid-out items plus the axis position and the canvas extent.
 */
function computeHorizontalLayout(
  groups: YearGroup[],
  order: number[],
  expanded: Set<number>,
  canvasWidth: number,
): HorizontalLayout {
  const AXIS_GAP = 30; // axis-to-near-edge distance for the innermost lane
  const MARGIN = 14; // breathing room above the top lane and below the bottom lane
  const n = order.length;
  if (n === 0) {
    return { items: [], axisY: MARGIN, totalWidth: canvasWidth, totalHeight: CANVAS_HEIGHT };
  }

  const years = order.map((ci) => groups[ci].year);
  const widths = order.map((ci) =>
    expanded.has(ci) ? CARD_WIDTH_EXPANDED + 28 : estimateCollapsedCardWidthPx(groups[ci]),
  );
  const heights = order.map((ci) =>
    expanded.has(ci) ? estimateExpandedCardPx(groups[ci], CARD_WRAP_CHARS) : COLLAPSED_CARD_HEIGHT_PX,
  );

  // Proportional axis fixed to the canvas width: years keep their spacing and
  // the whole span fits at zoom one. The base padding reserves the end cards'
  // half-widths so they do not clip.
  const span = Math.max(1, Math.abs(years[n - 1] - years[0]));
  const baseLeft = Math.max(28, widths[0] / 2 + END_PAD_PX);
  const baseRight = Math.max(28, widths[n - 1] / 2 + END_PAD_PX);
  const usable = Math.max(60, canvasWidth - baseLeft - baseRight);
  const pxPerYear = usable / span;
  const offx = years.map((y) => Math.abs(y - years[0]) * pxPerYear);

  // Cards are centered on their year dot, so a wide card can reach past the
  // first or last dot. Grow the end padding to cover each card's overhang; the
  // content then scrolls horizontally rather than clipping a card.
  let leftPad = baseLeft;
  let rightPad = baseRight;
  for (let d = 0; d < n; d++) {
    leftPad = Math.max(leftPad, END_PAD_PX + widths[d] / 2 - offx[d]);
    rightPad = Math.max(rightPad, END_PAD_PX + widths[d] / 2 - (offx[n - 1] - offx[d]));
  }
  const totalWidth = leftPad + offx[n - 1] + rightPad;
  const centers = offx.map((o) => leftPad + o);

  // Lane packing: same-side cards that would overlap horizontally move to a
  // farther lane (one tallest-card step out) instead of overlapping.
  const laneOf = assignLanes(centers, widths.map((w) => w / 2), LANE_X_GAP_PX);
  const rowStep = Math.max(60, ...heights) + LANE_GAP_PX;
  const dists = laneOf.map((l) => AXIS_GAP + l.lane * rowStep);

  // Symmetric vertical extent so the axis stays centered (both sides reserve the
  // larger of the two far edges).
  let above = AXIS_GAP;
  let below = AXIS_GAP;
  for (let d = 0; d < n; d++) {
    const ext = dists[d] + heights[d];
    if (laneOf[d].side === 0) above = Math.max(above, ext);
    else below = Math.max(below, ext);
  }
  const half = Math.max(above, below);
  const axisY = half + MARGIN;
  const totalHeight = 2 * half + 2 * MARGIN;

  const items: HorizontalItem[] = order.map((ci, d) => ({
    ci,
    centerX: centers[d],
    isTop: laneOf[d].side === 0,
    dist: dists[d],
  }));

  return { items, axisY, totalWidth, totalHeight };
}

interface HorizontalTimelineProps {
  /** Precomputed layout (positions, lanes, axis, canvas extent). */
  layout: HorizontalLayout;
  /** Year groups (indexed by the items' canonical indices). */
  groups: YearGroup[];
  /** Indices (into groups) of currently expanded cards. */
  expanded: Set<number>;
  /** Callback to toggle the expanded state of the card at the given index. */
  onToggle: (i: number) => void;
}

/**
 * Horizontal CSS timeline for year-grouped taxonomy entries.
 *
 * Renders the cards from a precomputed layout. Cards sit by publication year
 * along a central horizontal axis (a proportional time scale, matching the
 * vertical view), alternating above and below, with clustered cards stacked into
 * farther lanes so they do not overlap. Each year has a black dot and a year
 * label. Accepted-only years use square cards, synonym-only years rounded cards,
 * and mixed years a split square-over-rounded card.
 *
 * Parameters
 * ----------
 * layout : HorizontalLayout
 *     Precomputed item positions and canvas extent from computeHorizontalLayout.
 * groups : YearGroup[]
 *     Year groups, indexed by each item's canonical index.
 * expanded : Set<number>
 *     Set of group indices whose cards are in the expanded state.
 * onToggle : (i: number) => void
 *     Callback invoked with the card index to toggle its expanded state.
 */
function HorizontalTimeline({ layout, groups, expanded, onToggle }: HorizontalTimelineProps) {
  const { items, axisY, totalWidth, totalHeight } = layout;

  return (
    <div style={{ position: "relative", width: totalWidth, height: totalHeight }}>
      {/* Central horizontal axis line */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          top: axisY,
          left: 0,
          right: 0,
          height: 2,
          transform: "translateY(-50%)",
          backgroundColor: "#bdc3c7",
          zIndex: 0,
        }}
      />
      {/* End caps marking where the timeline starts and ends */}
      {(["left", "right"] as const).map((edge) => (
        <div
          key={edge}
          aria-hidden
          style={{
            position: "absolute",
            top: axisY,
            [edge]: 0,
            transform: "translateY(-50%)",
            width: 3,
            height: 26,
            backgroundColor: "#868e96",
            zIndex: 0,
          }}
        />
      ))}

      {items.map((item) => {
        const { ci } = item;
        const group = groups[ci];
        const isOpen = expanded.has(ci);
        const isTop = item.isTop;
        const cx = item.centerX;
        const nearEdge = isTop ? axisY - item.dist : axisY + item.dist;

        return (
          <div key={`year-${group.year}-${ci}`}>
            {/* Dashed connector from the central axis to this card's near edge */}
            <div
              aria-hidden
              style={{
                position: "absolute",
                left: cx,
                top: isTop ? nearEdge : axisY,
                transform: "translateX(-50%)",
                height: item.dist,
                borderLeft: "1px dashed #bdc3c7",
                zIndex: 0,
              }}
            />

            {/* Card, horizontally centered on its year position */}
            <div
              style={{
                position: "absolute",
                left: cx,
                transform: "translateX(-50%)",
                ...(isTop ? { bottom: totalHeight - nearEdge } : { top: nearEdge }),
                zIndex: 1,
              }}
            >
              <TimelineCard group={group} isOpen={isOpen} onToggle={() => onToggle(ci)} />
            </div>

            {/* Year label, on the card's side next to the dot */}
            <div
              style={{
                position: "absolute",
                left: cx,
                top: isTop ? axisY - 14 : axisY + 14,
                transform: "translate(-50%, -50%)",
                fontFamily: "Courier New, monospace",
                fontWeight: "bold",
                fontSize: 11,
                lineHeight: 1,
                color: "#333",
                backgroundColor: "rgba(255,255,255,0.85)",
                padding: "1px 3px",
                whiteSpace: "nowrap",
                zIndex: 2,
              }}
            >
              {group.year}
            </div>

            {/* Axis dot at the year position */}
            <div
              aria-hidden
              style={{
                position: "absolute",
                left: cx,
                top: axisY,
                transform: "translate(-50%, -50%)",
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: "#000",
                boxShadow: "0 0 0 2px white",
                zIndex: 3,
              }}
            />
          </div>
        );
      })}
    </div>
  );
}

/** Columns the undated-entries table can be sorted by. */
type UndatedSortKey = "name" | "author" | "source" | "status";

/** Header label and sort key for each undated-entries table column. */
const UNDATED_COLUMNS: { label: string; key: UndatedSortKey }[] = [
  { label: "Species Name", key: "name" },
  { label: "Author", key: "author" },
  { label: "API Name", key: "source" },
  { label: "Status", key: "status" },
];

/**
 * Small triangular caret indicating a column's sort direction.
 *
 * Parameters
 * ----------
 * dir : "asc", "desc", or null
 *     Active sort direction for the column, or null when the column is not the
 *     current sort key.
 *
 * Returns
 * -------
 * JSX.Element
 *     An upward caret for ascending, a downward caret for descending, or a
 *     dimmed downward caret when the column is not sorted.
 */
function SortCaret({ dir }: { dir: "asc" | "desc" | null }) {
  const base = {
    display: "inline-block",
    width: 0,
    height: 0,
    borderLeft: "4px solid transparent",
    borderRight: "4px solid transparent",
    marginLeft: 4,
  } as const;
  if (dir === "asc") {
    return <span style={{ ...base, borderBottom: "5px solid currentColor" }} />;
  }
  if (dir === "desc") {
    return <span style={{ ...base, borderTop: "5px solid currentColor" }} />;
  }
  return <span style={{ ...base, borderTop: "5px solid currentColor", opacity: 0.25 }} />;
}

/**
 * Small "fit / reset" glyph (four corner brackets) for the zoom control.
 *
 * Drawn as an inline SVG so it needs no icon dependency.
 *
 * Returns
 * -------
 * JSX.Element
 *     An SVG corners icon.
 */
function FitIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M4 9V5a1 1 0 0 1 1-1h4" />
      <path d="M20 9V5a1 1 0 0 0-1-1h-4" />
      <path d="M4 15v4a1 1 0 0 0 1 1h4" />
      <path d="M20 15v4a1 1 0 0 1-1 1h-4" />
    </svg>
  );
}

interface ZoomControlsProps {
  /** Increase the zoom level. */
  onZoomIn: () => void;
  /** Decrease the zoom level. */
  onZoomOut: () => void;
  /** Reset the zoom level to 1. */
  onReset: () => void;
}

/**
 * Floating zoom control for the timeline canvas: zoom in, zoom out, reset.
 *
 * Rendered as a stacked group of bordered buttons, mirroring the control in the
 * Relations view.
 *
 * Parameters
 * ----------
 * onZoomIn : () => void
 *     Handler for the zoom-in button.
 * onZoomOut : () => void
 *     Handler for the zoom-out button.
 * onReset : () => void
 *     Handler for the reset button.
 */
function ZoomControls({ onZoomIn, onZoomOut, onReset }: ZoomControlsProps) {
  const cell: CSSProperties = {
    width: 34,
    height: 34,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#fff",
    color: "#495057",
    cursor: "pointer",
    fontSize: 20,
    lineHeight: 1,
  };
  const divider = <div style={{ height: 1, background: "#dee2e6" }} />;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        border: "1px solid #ced4da",
        borderRadius: 6,
        overflow: "hidden",
        background: "#fff",
        boxShadow: "0 1px 4px rgba(0,0,0,0.18)",
      }}
    >
      <UnstyledButton style={cell} onClick={onZoomIn} aria-label="Zoom in">
        +
      </UnstyledButton>
      {divider}
      <UnstyledButton style={cell} onClick={onZoomOut} aria-label="Zoom out">
        −
      </UnstyledButton>
      {divider}
      <UnstyledButton style={{ ...cell, fontSize: 14 }} onClick={onReset} aria-label="Reset zoom">
        <FitIcon />
      </UnstyledButton>
    </div>
  );
}

// ---- Main component -------------------------------------------------------

/**
 * Timeline view component for species name records.
 *
 * Combines records that share a publication year into one card per year, shown
 * as a CSS timeline oriented either horizontally (a proportional time axis) or
 * vertically, via a segmented toggle. Each card has a "Name, Year" header and
 * one labeled block per record (API, status, author, source). A year is treated
 * as accepted when any record is accepted, which drives the card shape and
 * border color: square green for accepted, rounded purple for synonym, and a
 * split border for a year holding both. Controls cover year order, expand or
 * collapse all, and a zoom scale. Undated entries appear in a collapsible table
 * below either view.
 */
export function TimelineView() {
  const { records } = useFilteredRecords();
  const query = useSearchStore((s) => s.submittedQuery);
  const [undatedOpen, undated] = useDisclosure(false);
  const [orientation, setOrientation] = useState<"horizontal" | "vertical">("horizontal");
  const [yearOrder, setYearOrder] = useState<"asc" | "desc">("asc");

  // Scale control for the timeline canvas. The content is scaled with a CSS
  // transform (applied below); the canvas reserves the scaled size so it scrolls
  // correctly at any zoom.
  const [zoom, setZoom] = useState(1);
  const zoomIn = useCallback(
    () => setZoom((z) => Math.min(ZOOM_MAX, Math.round((z + ZOOM_STEP) * 100) / 100)),
    [],
  );
  const zoomOut = useCallback(
    () => setZoom((z) => Math.max(ZOOM_MIN, Math.round((z - ZOOM_STEP) * 100) / 100)),
    [],
  );
  const resetZoom = useCallback(() => setZoom(1), []);

  // The scaled content is measured at its natural (unscaled) size so the canvas
  // can reserve the correct scrolled area at any zoom. A transform (not CSS
  // zoom) is used to scale: it scales the rendered SVG faithfully, whereas CSS
  // zoom re-lays-out and clips Plotly's multi-line annotation text.
  const zoomContentRef = useRef<HTMLDivElement>(null);
  const [naturalHeight, setNaturalHeight] = useState(CANVAS_HEIGHT);
  useEffect(() => {
    const el = zoomContentRef.current;
    if (!el) return;
    const measure = () => setNaturalHeight(el.offsetHeight);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [orientation]);

  // Width of the scrollable canvas, so the horizontal axis can be a fixed length
  // that fits the view at zoom 1 (proportional spacing within it; zoom in for
  // detail when years cluster).
  const canvasRef = useRef<HTMLDivElement>(null);
  const [canvasWidth, setCanvasWidth] = useState(800);
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const measure = () => setCanvasWidth(el.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Drag-to-pan: press and drag anywhere on the canvas to scroll the timeline,
  // for both the Plotly horizontal view and the CSS vertical view (it only moves
  // the scroll container, never the views themselves). A small movement
  // threshold separates a pan from a click, and a real drag swallows the
  // following click (captured before it reaches a card) so panning never
  // toggles a card open or closed.
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const DRAG_THRESHOLD_PX = 5;
    let dragging = false;
    let moved = false;
    let startX = 0;
    let startY = 0;
    let startLeft = 0;
    let startTop = 0;

    const onMove = (e: MouseEvent) => {
      if (!dragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (!moved && Math.hypot(dx, dy) > DRAG_THRESHOLD_PX) {
        moved = true;
        el.style.cursor = "grabbing";
        el.style.userSelect = "none";
      }
      if (moved) {
        el.scrollLeft = startLeft - dx;
        el.scrollTop = startTop - dy;
        e.preventDefault();
      }
    };
    const onUp = () => {
      dragging = false;
      el.style.cursor = "grab";
      el.style.userSelect = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    const onDown = (e: MouseEvent) => {
      if (e.button !== 0) return; // primary button only
      dragging = true;
      moved = false;
      startX = e.clientX;
      startY = e.clientY;
      startLeft = el.scrollLeft;
      startTop = el.scrollTop;
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    };
    const onClickCapture = (e: MouseEvent) => {
      if (moved) {
        e.stopPropagation();
        e.preventDefault();
        moved = false;
      }
    };

    el.style.cursor = "grab";
    el.addEventListener("mousedown", onDown);
    el.addEventListener("click", onClickCapture, true);
    return () => {
      el.removeEventListener("mousedown", onDown);
      el.removeEventListener("click", onClickCapture, true);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  // Dated records grouped into one entry per year (oldest to newest), plus
  // colors, the undated set, and the total dated record count for the header.
  const { groups, undatedEntries, datedCount } = useMemo(() => {
    const t = buildTimeline(records);
    return {
      groups: groupTimelineByYear(t.dated),
      undatedEntries: t.undated,
      datedCount: t.dated.length,
    };
  }, [records]);

  // Canonical group indices arranged in the chosen display order. "asc" shows
  // oldest first (left in horizontal, top in vertical); "desc" shows newest
  // first. The expanded-state set stays keyed on canonical indices, so flipping
  // the order does not disturb which cards are open.
  const order = useMemo(
    () =>
      yearOrder === "asc"
        ? groups.map((_, i) => i)
        : groups.map((_, i) => groups.length - 1 - i),
    [groups, yearOrder],
  );

  // Year cards that contain an accepted record start expanded; all others
  // start collapsed. State resets whenever the data changes.
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  useEffect(() => {
    setExpanded(
      new Set(
        groups.reduce<number[]>((acc, g, i) => {
          if (g.isAccepted) acc.push(i);
          return acc;
        }, []),
      ),
    );
  }, [groups]);

  const toggleCard = useCallback((i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }, []);

  // One control for every card: collapse all when all are open, otherwise
  // expand all. Drives both the horizontal and vertical views (shared state).
  const allExpanded = groups.length > 0 && expanded.size === groups.length;
  const toggleAll = useCallback(() => {
    setExpanded((prev) =>
      prev.size === groups.length ? new Set() : new Set(groups.map((_, i) => i)),
    );
  }, [groups]);

  // Sorting for the undated-entries table. Clicking a column cycles ascending,
  // descending, then back to the original order.
  const [undatedSort, setUndatedSort] = useState<
    { key: UndatedSortKey; dir: "asc" | "desc" } | null
  >(null);
  const sortedUndated = useMemo(() => {
    if (!undatedSort) return undatedEntries;
    const { key, dir } = undatedSort;
    return [...undatedEntries].sort((a, b) => {
      const cmp = String(a[key] ?? "").localeCompare(String(b[key] ?? ""), undefined, {
        sensitivity: "base",
      });
      return dir === "asc" ? cmp : -cmp;
    });
  }, [undatedEntries, undatedSort]);
  const toggleUndatedSort = useCallback((key: UndatedSortKey) => {
    setUndatedSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: "asc" };
      if (prev.dir === "asc") return { key, dir: "desc" };
      return null;
    });
  }, []);

  // Absolute layout for the horizontal view: card positions, lanes, the axis
  // position, and the canvas extent (which grows taller as clustered cards stack
  // into extra lanes). The axis length is fixed to the canvas width.
  const horizontalLayout = useMemo(
    () => computeHorizontalLayout(groups, order, expanded, canvasWidth),
    [groups, order, expanded, canvasWidth],
  );

  // Absolute layout for the vertical view (positions, sides, columns, and the
  // canvas width, which grows when clustered cards spill into extra columns).
  const verticalLayout = useMemo(
    () => computeVerticalLayout(groups, order, expanded),
    [groups, order, expanded],
  );

  // Natural (unscaled) width of the active view. Horizontal uses the computed
  // timeline width; vertical uses the width its columns need on both sides.
  const contentWidth =
    orientation === "horizontal" ? horizontalLayout.totalWidth : verticalLayout.totalWidth;

  // Keep the axis centered in the scrollable canvas: horizontally for the
  // vertical view (its columns can be wider than the viewport) and vertically
  // for the horizontal view (its lanes can be taller than the viewport). Runs on
  // a layout change so both sides of the axis are equally visible on load.
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    if (orientation === "vertical") {
      // Center the axis horizontally; start at the top (oldest year).
      el.scrollLeft = Math.max(0, (el.scrollWidth - el.clientWidth) / 2);
      el.scrollTop = 0;
    } else {
      // Center the axis vertically; start at the left (oldest year).
      el.scrollTop = Math.max(0, (el.scrollHeight - el.clientHeight) / 2);
      el.scrollLeft = 0;
    }
  }, [orientation, contentWidth, naturalHeight]);

  if (records.length === 0) {
    return <Text c="dimmed">No results to display.</Text>;
  }

  return (
    <>
      {groups.length > 0 ? (
        <>
          <Group justify="space-between" mb="sm" wrap="nowrap">
            <Text size="md">
              <b>
                {datedCount} record{datedCount === 1 ? "" : "s"}
              </b>{" "}
              containing publication dates found of <i>{query}</i>, with{" "}
              <b>
                {groups.length} unique species name{groups.length === 1 ? "" : "s"}
              </b>{" "}
              <Text span c="dimmed" size="md">
                · click a card to expand or collapse it
              </Text>
            </Text>
            <Group gap="xs" wrap="nowrap">
              <Button
                variant="default"
                size="md"
                onClick={() => setYearOrder((o) => (o === "asc" ? "desc" : "asc"))}
              >
                {yearOrder === "asc" ? "Years: oldest first" : "Years: newest first"}
              </Button>
              <Button variant="default" size="md" onClick={toggleAll}>
                {allExpanded ? "Collapse all" : "Expand all"}
              </Button>
              <SegmentedControl
                value={orientation}
                onChange={(v) => setOrientation(v as "horizontal" | "vertical")}
                data={[
                  { label: "Horizontal", value: "horizontal" },
                  { label: "Vertical", value: "vertical" },
                ]}
                size="md"
              />
            </Group>
          </Group>

          <div style={{ position: "relative" }}>
            <div
              ref={canvasRef}
              style={{
                height: CANVAS_HEIGHT,
                overflow: "auto",
                border: "1px solid #e9ecef",
                borderRadius: 8,
              }}
            >
              <div
                style={{
                  position: "relative",
                  width: contentWidth * zoom,
                  height: naturalHeight * zoom,
                  margin: "0 auto",
                }}
              >
                <div
                  ref={zoomContentRef}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: contentWidth,
                    transform: `scale(${zoom})`,
                    transformOrigin: "top left",
                  }}
                >
                  {orientation === "horizontal" ? (
                    <HorizontalTimeline
                      layout={horizontalLayout}
                      groups={groups}
                      expanded={expanded}
                      onToggle={toggleCard}
                    />
                  ) : (
                    <VerticalTimeline
                      layout={verticalLayout}
                      groups={groups}
                      expanded={expanded}
                      onToggle={toggleCard}
                    />
                  )}
                </div>
              </div>
            </div>
            <div style={{ position: "absolute", left: 12, bottom: 12, zIndex: 5 }}>
              <ZoomControls onZoomIn={zoomIn} onZoomOut={zoomOut} onReset={resetZoom} />
            </div>
          </div>
        </>
      ) : (
        <Alert variant="light" color="blue">
          No publication years found in the results -- timeline cannot be rendered.
        </Alert>
      )}

      {undatedEntries.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <UnstyledButton onClick={undated.toggle}>
            <Text size="sm" c="dimmed">
              {undatedOpen ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}{" "}
              {undatedEntries.length} entr
              {undatedEntries.length === 1 ? "y" : "ies"} without a publication year
            </Text>
          </UnstyledButton>
          <Collapse in={undatedOpen}>
            <Table withTableBorder striped mt="xs" fz="sm">
              <Table.Thead>
                <Table.Tr>
                  {UNDATED_COLUMNS.map(({ label, key }) => (
                    <Table.Th key={key}>
                      <UnstyledButton
                        onClick={() => toggleUndatedSort(key)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          fontSize: "inherit",
                          fontWeight: "inherit",
                        }}
                      >
                        {label}
                        <SortCaret dir={undatedSort?.key === key ? undatedSort.dir : null} />
                      </UnstyledButton>
                    </Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sortedUndated.map((e, i) => (
                  <Table.Tr key={`${e.name}-${i}`}>
                    <Table.Td>
                      {e.url ? (
                        <Anchor href={e.url} target="_blank" rel="noopener noreferrer">
                          {e.name}
                        </Anchor>
                      ) : (
                        e.name
                      )}
                    </Table.Td>
                    <Table.Td>{e.author}</Table.Td>
                    <Table.Td>{e.source}</Table.Td>
                    <Table.Td>{e.status}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Collapse>
        </div>
      )}
    </>
  );
}
