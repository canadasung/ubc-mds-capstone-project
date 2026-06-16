"use client";

/**
 * Timeline view for species name records.
 *
 * Renders dated taxonomy entries on either a horizontal Plotly chart (a
 * proportional time axis) or a vertical CSS timeline. Records that share a
 * publication year are combined into a single card for that year, headed by the
 * name and year and listing one labeled block per record (API, status, author,
 * source). A year card is treated as accepted when any of its records is
 * accepted: accepted years display square (green), synonym-only years rounded
 * (purple), and mixed years a split square-over-rounded border. Plotly
 * annotation boxes have no per-corner radius, so in the horizontal view the
 * card borders are drawn onto the SVG after each render. Axis dots are uniform
 * black circles and do not encode source or status. Undated entries appear in a
 * collapsible table below either view.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import dynamic from "next/dynamic";
import {
  Alert,
  Anchor,
  Button,
  Collapse,
  Group,
  Loader,
  SegmentedControl,
  Table,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import type { Data, Layout } from "plotly.js";

import { useFilteredRecords } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import {
  buildTimeline,
  groupTimelineByYear,
  type TimelineEntry,
  type YearGroup,
} from "@/lib/transforms";

const PlotlyChart = dynamic(() => import("./PlotlyChart"), {
  ssr: false,
  loading: () => <Loader />,
});

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

/** Estimated rendered width in pixels of a collapsed year card. */
const COLLAPSED_CARD_PX = 140;
/** Extra horizontal margin in pixels past the first/last card on the axis. */
const END_PAD_PX = 20;
/** Estimated rendered height in pixels of a collapsed vertical card. */
const COLLAPSED_VERTICAL_PX = 64;
/**
 * Target text width in pixels of an expanded card box. Card text is wrapped to
 * fit this width so the box stays a predictable size and does not clip.
 */
const CARD_WIDTH_EXPANDED = 300;
/** Approximate monospace character advance at the card font size, in pixels. */
const CARD_CHAR_PX = 7.8;
/**
 * Maximum characters per wrapped line in an expanded horizontal card, derived
 * from the target card width. Plotly does not auto-wrap annotation text, so
 * card text is wrapped to this width with explicit line breaks.
 */
const CARD_WRAP_CHARS = Math.floor((CARD_WIDTH_EXPANDED - 24) / CARD_CHAR_PX);

/** Minimum zoom level for the timeline scale control. */
const ZOOM_MIN = 0.4;
/** Maximum zoom level for the timeline scale control. */
const ZOOM_MAX = 2.4;
/** Zoom increment per click of the scale control. */
const ZOOM_STEP = 0.2;
/** Fixed height in pixels of the zoomable timeline canvas. */
const CANVAS_HEIGHT = 640;
/** Natural content width in pixels of the vertical view (cards on both sides). */
const VERTICAL_WIDTH = 760;

/**
 * Word-wrap plain text to a maximum line length.
 *
 * Words are kept whole where possible; a single word longer than the limit is
 * hard-broken. Used to wrap card text manually because Plotly annotations clip
 * rather than wrap.
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
 * Build one labeled, wrapped field ("Label: value") for a card.
 *
 * The "Label:" prefix is rendered in gray; the value follows in the default
 * color. The whole line is wrapped to *maxChars*.
 *
 * Parameters
 * ----------
 * label : string
 *     Field label without the trailing colon, e.g. "Author".
 * value : string
 *     Field value.
 * maxChars : number
 *     Maximum number of characters per wrapped line.
 *
 * Returns
 * -------
 * { html: string; lines: number }
 *     The field HTML and the number of text lines it occupies.
 */
function labeledField(
  label: string,
  value: string,
  maxChars: number,
): { html: string; lines: number } {
  const lines = wrapLines(`${label}: ${value}`, maxChars);
  const out = [...lines];
  out[0] = out[0].replace(/^([^:]*:)/, '<span style="color:#888">$1</span>');
  return { html: out.join("<br>"), lines: lines.length };
}

/**
 * Build the HTML for a single record as a block of labeled fields.
 *
 * Renders four labeled lines, each on its own line: API (the source database, a
 * link when the record has a URL), Status (colored by accepted/synonym), Author,
 * and Source (the publication). The line count is returned so the horizontal
 * view can reserve enough vertical room for the card.
 *
 * Parameters
 * ----------
 * e : TimelineEntry
 *     The record to render.
 * maxChars : number
 *     Maximum number of characters per wrapped line.
 *
 * Returns
 * -------
 * { html: string; lines: number }
 *     The record's HTML and the number of text lines it occupies.
 */
function recordHtml(e: TimelineEntry, maxChars: number): { html: string; lines: number } {
  const apiValue = e.url
    ? `<a href="${e.url}" target="_blank"><span style="color:${COLOR_LINK}"><u>${e.source}</u></span></a>`
    : e.source;
  const apiLine = `<span style="color:#888">API:</span> ${apiValue}`;
  const statusLine = `<span style="color:#888">Status:</span> <span style="color:${statusColor(e.status)}">${e.status}</span>`;
  const author = labeledField("Author", e.author, maxChars);
  const source = labeledField("Source", e.publicationName, maxChars);
  const html = [apiLine, statusLine, author.html, source.html].join("<br>");
  return { html, lines: 2 + author.lines + source.lines };
}

/**
 * Build the HTML for an expanded year card.
 *
 * A bold "Name, Year" header sits at the top (using the accepted name when
 * present, otherwise the first record), followed by one labeled block per
 * record, accepted records first. Each record carries its own status field.
 *
 * Parameters
 * ----------
 * group : YearGroup
 *     The year group whose records are rendered.
 * maxChars : number
 *     Maximum number of characters per wrapped line.
 *
 * Returns
 * -------
 * string
 *     HTML string suitable for a Plotly annotation text property.
 */
function groupCardHtml(group: YearGroup, maxChars: number): string {
  const representative = group.accepted[0] ?? group.synonyms[0];
  const header = `<span style="font-size:15px"><b>${representative.name}, ${group.year}</b></span>`;
  const blocks = [...group.accepted, ...group.synonyms].map(
    (e) => recordHtml(e, maxChars).html,
  );
  return [header, ...blocks].join("<br><br>");
}

/**
 * Format a binomial name as two stacked lines for a collapsed card label.
 *
 * Splits the name on whitespace so the genus appears on the first line and
 * remaining tokens on the second. Single-word names are returned unchanged.
 *
 * Parameters
 * ----------
 * name : string
 *     Scientific name (e.g. "Amanita muscaria").
 *
 * Returns
 * -------
 * string
 *     HTML string with genus and species separated by a line break tag.
 */
function nameStacked(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length <= 1) return `<b>${name}</b>`;
  return `<b>${parts[0]}<br>${parts.slice(1).join(" ")}</b>`;
}

/**
 * Build the HTML for a collapsed year card.
 *
 * Shows a representative name (the accepted name when present, otherwise the
 * first synonym) plus a count of the remaining records in the year.
 *
 * Parameters
 * ----------
 * group : YearGroup
 *     The year group whose summary is rendered.
 *
 * Returns
 * -------
 * string
 *     HTML string suitable for a Plotly annotation text property.
 */
function groupCollapsedHtml(group: YearGroup): string {
  const representative = group.accepted[0] ?? group.synonyms[0];
  const more =
    group.count > 1
      ? `<br><span style="color:#888">+${group.count - 1} more</span>`
      : "";
  return `${nameStacked(representative.name)}${more}`;
}

/**
 * Estimate the rendered pixel height of an expanded year card.
 *
 * Counts the header line plus, for each record, a separating blank line and its
 * labeled field lines. The estimate lets the horizontal view reserve enough
 * vertical room that expanded cards on opposite lanes do not overlap.
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
    lines += 1 + recordHtml(e, maxChars).lines; // separating gap + the record
  }
  return lines * LINE_PX + 24;
}

/**
 * Ensure the SVG holds the linear gradient used for mixed-status card borders.
 *
 * The gradient is green over the top half and purple over the bottom half, in
 * object bounding-box units so it maps to each card's own box. It is created
 * once per SVG and reused.
 *
 * Parameters
 * ----------
 * svg : SVGSVGElement or null
 *     The SVG that owns the card rectangles.
 *
 * Returns
 * -------
 * void
 */
function ensureMixedGradient(svg: SVGSVGElement | null): void {
  if (!svg || svg.querySelector("#timelineMixedBorder")) return;
  const ns = "http://www.w3.org/2000/svg";
  let defs = svg.querySelector("defs");
  if (!defs) {
    defs = document.createElementNS(ns, "defs");
    svg.insertBefore(defs, svg.firstChild);
  }
  const gradient = document.createElementNS(ns, "linearGradient");
  gradient.setAttribute("id", "timelineMixedBorder");
  gradient.setAttribute("x1", "0");
  gradient.setAttribute("y1", "0");
  gradient.setAttribute("x2", "0");
  gradient.setAttribute("y2", "1");
  for (const [offset, color] of [
    ["50%", COLOR_ACCEPTED],
    ["50%", COLOR_SYNONYM],
  ] as const) {
    const stop = document.createElementNS(ns, "stop");
    stop.setAttribute("offset", offset);
    stop.setAttribute("stop-color", color);
    gradient.appendChild(stop);
  }
  defs.appendChild(gradient);
}

/**
 * Style each year card's border in the horizontal Plotly view.
 *
 * Plotly annotation boxes are a single SVG rectangle, styled after each draw.
 * An accepted-only year gets square corners; a synonym-only year gets rounded
 * corners. A year holding both is split like the vertical card: because a
 * rectangle cannot mix corner radii per side, its border is drawn as a separate
 * path with square top corners and rounded bottom corners, stroked with the
 * green-over-purple gradient. The rectangle is kept for its white fill and click
 * target, but its own border is hidden.
 *
 * Parameters
 * ----------
 * graphDiv : HTMLElement or null
 *     The Plotly graph container supplied by the chart render callbacks.
 * annotationIndex : number[]
 *     Maps each annotation's array position to its year-group index, or -1 for
 *     non-card annotations such as year labels.
 * groups : YearGroup[]
 *     Year groups, used to look up each card's record statuses.
 *
 * Returns
 * -------
 * void
 */
function styleCardBorders(
  graphDiv: HTMLElement | null,
  annotationIndex: number[],
  groups: YearGroup[],
): void {
  if (!graphDiv) return;
  const radius = 10;
  graphDiv.querySelectorAll<SVGGElement>("g.annotation").forEach((el) => {
    const pos = Number(el.getAttribute("data-index"));
    const idx = Number.isNaN(pos) ? -1 : annotationIndex[pos];
    const group = idx >= 0 ? groups[idx] : undefined;
    if (!group) return;
    const rect = el.querySelector<SVGRectElement>("rect");
    if (!rect) return;
    const mixed = group.accepted.length > 0 && group.synonyms.length > 0;
    const existing = el.querySelector<SVGPathElement>("path[data-card-border]");

    if (mixed) {
      ensureMixedGradient(rect.ownerSVGElement);
      // Hide the rect's own border; keep its (square) white fill and clicks.
      rect.style.stroke = "none";
      rect.removeAttribute("rx");
      rect.removeAttribute("ry");
      const { x, y, width: w, height: h } = rect.getBBox();
      const r = Math.min(radius, w / 2, h / 2);
      const d =
        `M${x},${y} L${x + w},${y} L${x + w},${y + h - r} ` +
        `Q${x + w},${y + h} ${x + w - r},${y + h} ` +
        `L${x + r},${y + h} Q${x},${y + h} ${x},${y + h - r} Z`;
      const path =
        existing ?? document.createElementNS("http://www.w3.org/2000/svg", "path");
      if (!existing) {
        path.setAttribute("data-card-border", "1");
        path.style.pointerEvents = "none"; // never block clicks on the card
        rect.parentNode?.insertBefore(path, rect.nextSibling);
      }
      path.setAttribute("d", d);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "url(#timelineMixedBorder)");
      path.setAttribute("stroke-width", "2");
    } else {
      existing?.remove();
      rect.style.stroke = group.isAccepted ? COLOR_ACCEPTED : COLOR_SYNONYM;
      if (group.isAccepted) {
        rect.removeAttribute("rx");
        rect.removeAttribute("ry");
      } else {
        rect.setAttribute("rx", String(radius));
        rect.setAttribute("ry", String(radius));
      }
    }
  });
}

// ---- Vertical timeline sub-components ------------------------------------

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
 * Render one record as a block of labeled fields in a vertical year card.
 *
 * Shows API (the source database, a link when available), Status (colored by
 * accepted/synonym), Author, and Source (the publication), each on its own line.
 *
 * Parameters
 * ----------
 * entry : TimelineEntry
 *     The record to render.
 */
function RecordBlock({ entry }: { entry: TimelineEntry }) {
  const label = (text: string) => <span style={{ color: "#888" }}>{text}</span>;
  return (
    <div style={{ marginTop: 8 }}>
      <div>
        {label("API:")}{" "}
        {entry.url ? (
          <a
            href={entry.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: COLOR_LINK, textDecoration: "underline" }}
          >
            {entry.source}
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

interface VerticalCardProps {
  /** Year group rendered by the card. */
  group: YearGroup;
  /** Whether the card is currently in the expanded state. */
  isOpen: boolean;
  /** Callback invoked when the user clicks the card. */
  onToggle: () => void;
}

/**
 * Clickable year card for the vertical timeline view.
 *
 * An accepted-only year gets a square green border; a synonym-only year gets a
 * rounded purple border. A year holding both is split: a green square-cornered
 * top half over a purple rounded-cornered bottom half. Clicking toggles
 * between a compact representative-name display and an expanded view with a
 * "Name, Year" header followed by one labeled block per record (API, status,
 * author, source).
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
function VerticalCard({ group, isOpen, onToggle }: VerticalCardProps) {
  const hasAccepted = group.accepted.length > 0;
  const hasSynonym = group.synonyms.length > 0;
  const representative = group.accepted[0] ?? group.synonyms[0];
  const nameParts = representative.name.trim().split(/\s+/);

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
        ...borderStyle,
        padding: isOpen ? "10px 14px" : "6px 10px",
        cursor: "pointer",
        fontFamily: "Courier New, monospace",
        fontSize: 13,
        color: "#333",
        maxWidth: isOpen ? 300 : 260,
        minWidth: 120,
        textAlign: isOpen ? "left" : "center",
        userSelect: "none",
        lineHeight: 1.5,
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

interface VerticalTimelineProps {
  /** Year groups, oldest to newest. */
  groups: YearGroup[];
  /** Canonical group indices in display order (top to bottom). */
  order: number[];
  /** Indices (into groups) of currently expanded cards. */
  expanded: Set<number>;
  /** Callback to toggle the expanded state of the card at the given index. */
  onToggle: (i: number) => void;
}

/**
 * Vertical CSS timeline for year-grouped taxonomy entries.
 *
 * Cards are positioned by their publication year along a central vertical axis
 * (a proportional time scale, matching the horizontal view), alternating left
 * and right. The axis length is fixed to the canvas height so the whole span
 * fits the view; clustered cards may overlap until zoomed in. Each year has a
 * black dot and a year label. Accepted-only years use square cards, synonym-only
 * years rounded cards, and mixed years a split square-over-rounded card.
 *
 * Parameters
 * ----------
 * groups : YearGroup[]
 *     Year groups, oldest to newest.
 * order : number[]
 *     Canonical group indices in display order (top to bottom).
 * expanded : Set<number>
 *     Set of group indices whose cards are in the expanded state.
 * onToggle : (i: number) => void
 *     Callback invoked with the card index to toggle its expanded state.
 */
function VerticalTimeline({ groups, order, expanded, onToggle }: VerticalTimelineProps) {
  const CENTER_WIDTH = 64;
  const n = order.length;
  const years = order.map((ci) => groups[ci].year);
  const heights = order.map((ci) =>
    expanded.has(ci) ? estimateExpandedCardPx(groups[ci], CARD_WRAP_CHARS) : COLLAPSED_VERTICAL_PX,
  );

  // Fixed-length axis: the whole span fits the canvas height, with positions
  // still proportional to year. Padding reserves the end cards' half-heights so
  // they do not clip. Clustered cards may overlap at base zoom; zoom in to
  // separate them.
  const topPad = Math.max(28, heights[0] / 2 + 8);
  const bottomPad = Math.max(28, heights[n - 1] / 2 + 8);
  const span = Math.max(1, Math.abs(years[n - 1] - years[0]));
  const usable = Math.max(40, CANVAS_HEIGHT - topPad - bottomPad);
  const pxPerYear = usable / span;
  const totalHeight = topPad + span * pxPerYear + bottomPad;
  const topOf = (d: number) => topPad + Math.abs(years[d] - years[0]) * pxPerYear;

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

      {order.map((ci, d) => {
        const group = groups[ci];
        const isLeft = d % 2 === 0;
        const isOpen = expanded.has(ci);
        const top = topOf(d);
        const cardEdge = `calc(50% + ${CENTER_WIDTH}px)`;

        return (
          <div key={`year-${group.year}-${ci}`}>
            {/* Dashed connector from the central axis to this card */}
            <div
              aria-hidden
              style={{
                position: "absolute",
                top,
                left: isLeft ? undefined : "50%",
                right: isLeft ? "50%" : undefined,
                width: CENTER_WIDTH,
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
              <VerticalCard group={group} isOpen={isOpen} onToggle={() => onToggle(ci)} />
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
 * either as a horizontal Plotly chart (a proportional time axis) or a vertical
 * CSS timeline, via a segmented toggle. Each card has a "Name, Year" header and
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

  // Scale control for the timeline canvas. A CSS zoom is applied to the chart
  // content; react-plotly only resizes on window resize, so it is unaffected.
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

  // Builds all Plotly figure data for the horizontal view.
  //
  // Cards are placed at their real publication year (a proportional time axis)
  // whose total length is fixed to the canvas width, so the whole span fits the
  // view at zoom 1; zoom in to separate clustered cards. Cards alternate between
  // two lanes. The display order (oldest/newest first) reverses the x-axis.
  const figure = useMemo(() => {
    if (groups.length === 0) return null;

    // groups is sorted ascending by year, with one (distinct) year per group.
    const n = groups.length;
    const years = groups.map((g) => g.year);
    const yPos = groups.map((_, i) => (i % 2 === 0 ? 0.5 : -0.5));

    // Estimated rendered width of each card, used to reserve room for the end
    // cards so they sit fully inside the axis.
    const widths = groups.map((_, i) =>
      expanded.has(i) ? CARD_WIDTH_EXPANDED + 24 : COLLAPSED_CARD_PX,
    );

    const yearMin = years[0];
    const yearMax = years[n - 1];
    const yearSpan = Math.max(1, yearMax - yearMin);

    // Fixed-length axis: the whole span fits the canvas width at zoom 1, with
    // positions still proportional to year. The usable length reserves the end
    // cards' half-widths so they do not clip. Clustered cards may overlap at base
    // zoom; zoom in with the scale control to separate them.
    const endHalf = widths[0] / 2 + widths[n - 1] / 2;
    const usable = Math.max(60, canvasWidth - 40 - endHalf - 2 * END_PAD_PX);
    const pxPerYear = usable / yearSpan;

    const axisMin = yearMin - (widths[0] / 2 + END_PAD_PX) / pxPerYear;
    const axisMax = yearMax + (widths[n - 1] / 2 + END_PAD_PX) / pxPerYear;
    const minWidth = canvasWidth;

    // Grow the plot height so the two lanes sit far enough apart that the
    // tallest expanded card cannot overlap a card on the opposite lane. Lanes
    // are at y = ±0.5 within a 2.0-unit range (see the yaxis below), so the
    // pixel gap between them is height / 2; keep that above the tallest card.
    // The range hugs the lanes (±1.0) so there is little empty margin top/bottom.
    const tallestCard = groups.reduce(
      (max, g, i) =>
        expanded.has(i) ? Math.max(max, estimateExpandedCardPx(g, CARD_WRAP_CHARS)) : max,
      0,
    );
    const plotHeight = Math.min(1600, Math.max(480, Math.ceil(2.3 * tallestCard)));

    const shapes: Partial<Layout>["shapes"] = [
      {
        type: "line",
        x0: axisMin,
        x1: axisMax,
        y0: 0,
        y1: 0,
        line: { color: "#bdc3c7", width: 2 },
      },
      // Vertical end caps marking where the timeline starts and ends. Sized in
      // pixels (ysizemode "pixel", anchored at the y=0 axis) so they keep a
      // fixed length no matter how tall the plot grows when cards expand.
      ...[axisMin, axisMax].map((x) => ({
        type: "line" as const,
        x0: x,
        x1: x,
        ysizemode: "pixel" as const,
        yanchor: 0,
        y0: -13,
        y1: 13,
        line: { color: "#495057", width: 4 },
      })),
      ...groups.map((_, i) => ({
        type: "line" as const,
        x0: years[i],
        x1: years[i],
        y0: 0,
        y1: yPos[i],
        line: { color: "#bdc3c7", width: 1, dash: "dot" as const },
      })),
    ];

    type Ann = NonNullable<Partial<Layout>["annotations"]>[number];

    // Card annotations tagged with their canonical group index so expanded cards
    // can be reordered to the top layer without losing the click mapping.
    const cards = groups.map((g, i) => {
      const isOpen = expanded.has(i);
      const borderColor = g.isAccepted ? COLOR_ACCEPTED : COLOR_SYNONYM;
      const ann: Ann = {
        x: years[i],
        y: yPos[i],
        text: isOpen ? groupCardHtml(g, CARD_WRAP_CHARS) : groupCollapsedHtml(g),
        showarrow: false,
        bgcolor: "white",
        bordercolor: borderColor,
        borderwidth: 2,
        borderpad: isOpen ? 10 : 6,
        align: "left",
        font: { size: 13, color: "#333", family: "Courier New, monospace" },
        xanchor: "center",
        yanchor: "middle",
        captureevents: true,
        // Card text is pre-wrapped to CARD_WRAP_CHARS, so a fixed box width
        // keeps every expanded card the same size without clipping.
        ...(isOpen ? { width: CARD_WIDTH_EXPANDED } : {}),
      };
      return { ann, idx: i, isOpen };
    });

    // Year labels sit on the center line. Not clickable.
    const yearLabels = groups.map((_, i) => {
      const ann: Ann = {
        x: years[i],
        y: 0,
        yshift: 9,
        text: `<b>${years[i]}</b>`,
        showarrow: false,
        bgcolor: "rgba(255,255,255,0.85)",
        borderpad: 1,
        align: "center",
        font: { size: 13, color: "#333", family: "Courier New, monospace" },
        xanchor: "center",
        yanchor: "bottom",
        captureevents: false,
      };
      return { ann, idx: -1 };
    });

    // Draw order = z-order: collapsed cards, year labels, expanded cards last.
    const ordered = [
      ...cards.filter((c) => !c.isOpen),
      ...yearLabels,
      ...cards.filter((c) => c.isOpen),
    ];
    const annotations: Partial<Layout>["annotations"] = ordered.map((o) => o.ann);
    // annotation array position -> group index (or -1 for non-card labels)
    const annotationIndex = ordered.map((o) => o.idx);

    const data: Data[] = [
      {
        type: "scatter",
        mode: "markers",
        x: years,
        y: years.map(() => 0),
        // Uniform black circles: dots no longer encode source or status.
        marker: { size: 9, color: "#000", symbol: "circle" },
        text: groups.map((g) => `${g.year}: ${g.count} name${g.count === 1 ? "" : "s"}`),
        hoverinfo: "text",
      },
    ];

    // Oldest-first keeps the natural axis; newest-first reverses it.
    const xRange: [number, number] =
      yearOrder === "asc" ? [axisMin, axisMax] : [axisMax, axisMin];

    const layout: Partial<Layout> = {
      height: plotHeight,
      margin: { l: 20, r: 20, t: 30, b: 20 },
      xaxis: {
        title: { text: "Year of Publication" },
        range: xRange,
        showgrid: false,
        zeroline: false,
        showticklabels: false,
        fixedrange: true,
      },
      yaxis: { visible: false, range: [-1, 1], fixedrange: true },
      plot_bgcolor: "white",
      paper_bgcolor: "white",
      showlegend: false,
      dragmode: false,
      shapes,
      annotations,
    };

    return { data, layout, annotationIndex, minWidth };
  }, [groups, expanded, yearOrder, canvasWidth]);

  if (records.length === 0) {
    return <Text c="dimmed">No results to plot.</Text>;
  }

  // Natural (unscaled) width of the active view. Horizontal uses the computed
  // timeline width; vertical uses a fixed width holding cards on both sides.
  const contentWidth =
    orientation === "horizontal" ? figure?.minWidth ?? 600 : VERTICAL_WIDTH;

  return (
    <>
      {groups.length > 0 ? (
        <>
          <Group justify="space-between" mb="sm" wrap="nowrap">
            <Text>
              <b>
                {datedCount} record{datedCount === 1 ? "" : "s"}
              </b>{" "}
              containing publication dates found of <i>{query}</i>, with{" "}
              <b>
                {groups.length} unique species name{groups.length === 1 ? "" : "s"}
              </b>{" "}
              <Text span c="dimmed" size="xs">
                · click a card to expand or collapse it
              </Text>
            </Text>
            <Group gap="xs" wrap="nowrap">
              <Button
                variant="default"
                size="xs"
                onClick={() => setYearOrder((o) => (o === "asc" ? "desc" : "asc"))}
              >
                {yearOrder === "asc" ? "Years: oldest first" : "Years: newest first"}
              </Button>
              <Button variant="default" size="xs" onClick={toggleAll}>
                {allExpanded ? "Collapse all" : "Expand all"}
              </Button>
              <SegmentedControl
                value={orientation}
                onChange={(v) => setOrientation(v as "horizontal" | "vertical")}
                data={[
                  { label: "Horizontal", value: "horizontal" },
                  { label: "Vertical", value: "vertical" },
                ]}
                size="xs"
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
                    figure != null && (
                      <PlotlyChart
                        data={figure.data}
                        layout={figure.layout}
                        config={{ scrollZoom: false, displayModeBar: false }}
                        style={{ width: "100%" }}
                        useResizeHandler
                        onClickAnnotation={(e) => {
                          const idx = figure.annotationIndex[e.index];
                          if (idx != null && idx >= 0) toggleCard(idx);
                        }}
                        onInitialized={(_, gd) =>
                          styleCardBorders(gd, figure.annotationIndex, groups)
                        }
                        onUpdate={(_, gd) =>
                          styleCardBorders(gd, figure.annotationIndex, groups)
                        }
                      />
                    )
                  ) : (
                    <VerticalTimeline
                      groups={groups}
                      order={order}
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
