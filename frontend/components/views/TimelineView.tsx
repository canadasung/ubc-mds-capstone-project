"use client";

/**
 * Timeline view for species name records.
 *
 * Renders dated taxonomy entries on either a horizontal Plotly chart or a
 * vertical CSS timeline. Records that share a publication year are combined into
 * a single card for that year, with an Accepted section and a Synonyms section
 * inside. A year card is treated as accepted when any of its records is
 * accepted. Accepted cards display square; synonym-only cards display rounded.
 * Plotly annotation boxes have no border-radius property, so in the horizontal
 * view rounding is applied to the SVG rectangles after each render. Status is
 * also reinforced by the axis marker symbol (square vs circle) and border
 * color. Undated entries appear in a collapsible table below either view.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
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

/** Border color for accepted taxonomic name boxes, used in both views. */
const COLOR_ACCEPTED = "#1c7ed6";
/** Border color for synonym and unknown-status boxes, used in both views. */
const COLOR_SYNONYM = "#e67e22";

/** Horizontal pixels per entry in the horizontal view when no card is expanded. */
const SLOT_COLLAPSED = 95;
/**
 * Horizontal pixels per entry in the horizontal view when at least one card is
 * expanded. Sized so two same-lane neighbors, which sit two slots apart, stay
 * clear of an expanded box.
 */
const SLOT_EXPANDED = 190;
/**
 * Target width in pixels of an expanded card box. Card text is wrapped to fit
 * this width so it never widens past its slot or clips at the box edge.
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
 * Build the wrapped HTML for a single record, plus its line count.
 *
 * The record renders as a bold name line, an optional author and publication
 * line, and a source line (a link when the record carries a URL). Each part is
 * wrapped to *maxChars*. The line count is returned so the horizontal view can
 * reserve enough vertical room for the card.
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
  const nameLines = wrapLines(e.name, maxChars);
  const metaText = [e.author, e.publicationName]
    .filter((part) => part && part !== "—")
    .join(" · ");
  const metaLines = metaText ? wrapLines(metaText, maxChars) : [];
  const src = e.url
    ? `<a href="${e.url}" target="_blank">${e.source}</a>`
    : e.source;
  const parts = [
    `<b>${nameLines.join("<br>")}</b>`,
    ...(metaLines.length
      ? [`<span style="color:#888">${metaLines.join("<br>")}</span>`]
      : []),
    `<span style="color:#888">${src}</span>`,
  ];
  return { html: parts.join("<br>"), lines: nameLines.length + metaLines.length + 1 };
}

/**
 * Build a titled status section (Accepted or Synonyms) for a year card.
 *
 * Parameters
 * ----------
 * title : string
 *     Section heading, "Accepted" or "Synonyms".
 * color : string
 *     Heading color, matching the card border palette.
 * items : TimelineEntry[]
 *     Records belonging to the section.
 * maxChars : number
 *     Maximum number of characters per wrapped line.
 *
 * Returns
 * -------
 * string
 *     HTML for the section, or "" when there are no records.
 */
function sectionHtml(
  title: string,
  color: string,
  items: TimelineEntry[],
  maxChars: number,
): string {
  if (items.length === 0) return "";
  const rows = items.map((e) => recordHtml(e, maxChars).html).join("<br>");
  return `<span style="color:${color}"><b>${title}</b></span><br>${rows}`;
}

/**
 * Build the HTML for an expanded year card: Accepted then Synonyms sections.
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
  return [
    sectionHtml("Accepted", COLOR_ACCEPTED, group.accepted, maxChars),
    sectionHtml("Synonyms", COLOR_SYNONYM, group.synonyms, maxChars),
  ]
    .filter(Boolean)
    .join("<br><br>");
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
 * Counts one heading line per non-empty section plus roughly two and a half
 * lines per record (a name and a possibly wrapped detail line). The estimate
 * lets the horizontal view reserve enough vertical room that expanded cards on
 * opposite lanes do not overlap.
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
  let lines = 0;
  for (const section of [group.accepted, group.synonyms]) {
    if (section.length === 0) continue;
    lines += 1; // section heading
    for (const e of section) lines += recordHtml(e, maxChars).lines;
  }
  if (group.accepted.length && group.synonyms.length) lines += 1; // gap between sections
  return lines * LINE_PX + 24;
}

/**
 * Round the corners of synonym year cards in the horizontal Plotly view.
 *
 * Plotly annotation boxes expose no border-radius property, so the rounding is
 * applied to the rendered SVG rectangles after each draw. Year cards that
 * contain an accepted record are left square, mirroring the vertical view.
 *
 * Parameters
 * ----------
 * graphDiv : HTMLElement or null
 *     The Plotly graph container supplied by the chart render callbacks.
 * annotationIndex : number[]
 *     Maps each annotation's array position to its year-group index, or -1 for
 *     non-card annotations such as year labels.
 * groups : YearGroup[]
 *     Year groups, used to look up each card's accepted or synonym status.
 *
 * Returns
 * -------
 * void
 */
function roundSynonymAnnotations(
  graphDiv: HTMLElement | null,
  annotationIndex: number[],
  groups: YearGroup[],
): void {
  if (!graphDiv) return;
  // Radius in pixels, matching the vertical card border-radius.
  const radius = "10";
  graphDiv.querySelectorAll<SVGGElement>("g.annotation").forEach((el) => {
    const pos = Number(el.getAttribute("data-index"));
    const idx = Number.isNaN(pos) ? -1 : annotationIndex[pos];
    const group = idx >= 0 ? groups[idx] : undefined;
    const rounded = group != null && !group.isAccepted;
    el.querySelectorAll("rect").forEach((rect) => {
      if (rounded) {
        rect.setAttribute("rx", radius);
        rect.setAttribute("ry", radius);
      } else {
        rect.removeAttribute("rx");
        rect.removeAttribute("ry");
      }
    });
  });
}

// ---- Vertical timeline sub-components ------------------------------------

interface StatusSectionProps {
  /** Section heading, "Accepted" or "Synonyms". */
  title: string;
  /** Heading color, matching the card border palette. */
  color: string;
  /** Records belonging to the section. */
  items: TimelineEntry[];
}

/**
 * Render a titled status section inside an expanded vertical year card.
 *
 * Parameters
 * ----------
 * title : string
 *     Section heading, "Accepted" or "Synonyms".
 * color : string
 *     Heading color, matching the card border palette.
 * items : TimelineEntry[]
 *     Records belonging to the section.
 */
function StatusSection({ title, color, items }: StatusSectionProps) {
  if (items.length === 0) return null;
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ color, fontWeight: "bold" }}>{title}</div>
      {items.map((e, i) => {
        const meta = [e.author, e.publicationName].filter((p) => p && p !== "—");
        return (
          <div key={`${e.name}-${i}`} style={{ marginTop: 2 }}>
            <div style={{ fontWeight: "bold" }}>{e.name}</div>
            <div style={{ color: "#888" }}>
              {meta.length > 0 && <>{meta.join(" · ")} · </>}
              {e.url ? (
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: COLOR_ACCEPTED }}
                >
                  {e.source}
                </a>
              ) : (
                e.source
              )}
            </div>
          </div>
        );
      })}
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
 * Renders with a square border (border-radius 0) when the year contains an
 * accepted record and with a rounded border (border-radius 10px) otherwise.
 * Clicking toggles between a compact representative-name display and an
 * expanded view with Accepted and Synonyms sections.
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
  const borderColor = group.isAccepted ? COLOR_ACCEPTED : COLOR_SYNONYM;
  const borderRadius = group.isAccepted ? 0 : 10;
  const representative = group.accepted[0] ?? group.synonyms[0];
  const nameParts = representative.name.trim().split(/\s+/);

  return (
    <div
      onClick={onToggle}
      style={{
        border: `2px solid ${borderColor}`,
        borderRadius,
        backgroundColor: "white",
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
          <StatusSection title="Accepted" color={COLOR_ACCEPTED} items={group.accepted} />
          <StatusSection title="Synonyms" color={COLOR_SYNONYM} items={group.synonyms} />
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
  /** Mapping from source label to accent color, used for axis dots. */
  sourceColors: Record<string, string>;
  /** Indices (into groups) of currently expanded cards. */
  expanded: Set<number>;
  /** Callback to toggle the expanded state of the card at the given index. */
  onToggle: (i: number) => void;
}

/**
 * Vertical CSS timeline for year-grouped taxonomy entries.
 *
 * Lays out year cards top to bottom along a central vertical axis line, with
 * cards alternating on the left and right sides. Each year has a colored dot
 * and year label on the axis. Years containing an accepted record use
 * square-cornered cards; synonym-only years use rounded-cornered cards.
 *
 * Parameters
 * ----------
 * groups : YearGroup[]
 *     Year groups, oldest to newest.
 * sourceColors : Record<string, string>
 *     Accent colors keyed by source label, applied to axis dots.
 * expanded : Set<number>
 *     Set of group indices whose cards are in the expanded state.
 * onToggle : (i: number) => void
 *     Callback invoked with the card index to toggle its expanded state.
 */
function VerticalTimeline({ groups, sourceColors, expanded, onToggle }: VerticalTimelineProps) {
  const CENTER_WIDTH = 64;

  return (
    <div style={{ position: "relative", paddingTop: 8, paddingBottom: 8 }}>
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

      {[...groups].reverse().map((group, displayIdx) => {
        const i = groups.length - 1 - displayIdx;
        const isLeft = displayIdx % 2 === 0;
        const dotColor = sourceColors[group.source] ?? "#3498db";
        const isOpen = expanded.has(i);

        return (
          <div
            key={`year-${group.year}-${i}`}
            style={{
              display: "flex",
              alignItems: "center",
              marginBottom: 24,
              position: "relative",
            }}
          >
            {/* Dashed connector from the central axis to this card */}
            <div
              aria-hidden
              style={{
                position: "absolute",
                top: "50%",
                left: isLeft ? undefined : "50%",
                right: isLeft ? "50%" : undefined,
                width: CENTER_WIDTH,
                borderTop: "1px dashed #bdc3c7",
                zIndex: 0,
              }}
            />

            {/* Left card slot */}
            <div
              style={{
                flex: 1,
                display: "flex",
                justifyContent: "flex-end",
                paddingRight: CENTER_WIDTH / 2,
              }}
            >
              {isLeft && (
                <VerticalCard group={group} isOpen={isOpen} onToggle={() => onToggle(i)} />
              )}
            </div>

            {/* Axis dot and year label */}
            <div
              style={{
                width: CENTER_WIDTH,
                flexShrink: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                position: "relative",
                zIndex: 1,
              }}
            >
              <div
                style={{
                  width: 10,
                  height: 10,
                  // Square dot for years with an accepted record, circle
                  // otherwise, matching the horizontal view's axis markers.
                  borderRadius: group.isAccepted ? 0 : "50%",
                  backgroundColor: dotColor,
                  boxShadow: "0 0 0 2px white",
                  marginBottom: 2,
                }}
              />
              <Text
                size="xs"
                style={{
                  fontFamily: "Courier New, monospace",
                  fontWeight: "bold",
                  lineHeight: 1,
                  backgroundColor: "rgba(255,255,255,0.85)",
                  padding: "1px 2px",
                }}
              >
                {group.year}
              </Text>
            </div>

            {/* Right card slot */}
            <div
              style={{
                flex: 1,
                display: "flex",
                justifyContent: "flex-start",
                paddingLeft: CENTER_WIDTH / 2,
              }}
            >
              {!isLeft && (
                <VerticalCard group={group} isOpen={isOpen} onToggle={() => onToggle(i)} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---- Main component -------------------------------------------------------

/**
 * Timeline view component for species name records.
 *
 * Combines records that share a publication year into one card per year, shown
 * either as a horizontal Plotly chart or a vertical CSS timeline via a
 * segmented toggle. Each card has an Accepted section and a Synonyms section; a
 * year is treated as accepted when any record is accepted, which drives the
 * square (accepted) versus rounded (synonym) card shape, the axis marker
 * symbol, and the border color. Undated entries appear in a collapsible table
 * below either view.
 */
export function TimelineView() {
  const { records } = useFilteredRecords();
  const query = useSearchStore((s) => s.submittedQuery);
  const [undatedOpen, undated] = useDisclosure(false);
  const [orientation, setOrientation] = useState<"horizontal" | "vertical">("horizontal");

  // Dated records grouped into one entry per year (oldest to newest), plus
  // colors, the undated set, and the total dated record count for the header.
  const { groups, undatedEntries, sourceColors, datedCount } = useMemo(() => {
    const t = buildTimeline(records);
    return {
      groups: groupTimelineByYear(t.dated),
      undatedEntries: t.undated,
      sourceColors: t.sourceColors,
      datedCount: t.dated.length,
    };
  }, [records]);

  // The newest year (latest, last in groups) starts expanded. State resets
  // whenever the data changes.
  const newestIdx = groups.length - 1;
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  useEffect(() => {
    setExpanded(newestIdx >= 0 ? new Set([newestIdx]) : new Set());
  }, [groups, newestIdx]);

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

  // Builds all Plotly figure data for the horizontal view.
  //
  // Year cards are spaced evenly by index (slot position), not by their year
  // value, so neighbors never collide the way they do when clustered years share
  // an x coordinate. The plot widens with the year count, and wider again when
  // any card is expanded, while the chart scrolls horizontally inside its
  // container. The real publication year is kept only as label text. Expanded
  // cards are ordered last so they render on top.
  const figure = useMemo(() => {
    if (groups.length === 0) return null;

    const years = groups.map((g) => g.year);
    const xPos = groups.map((_, i) => i);
    const yPos = groups.map((_, i) => (i % 2 === 0 ? 0.5 : -0.5));
    const xMin = -0.6;
    const xMax = groups.length - 0.4;

    // Wider slots whenever any card is expanded, so the larger boxes and their
    // same-lane neighbors (two slots away) stay clear of each other. The chart
    // grows to this width and scrolls horizontally inside its container.
    const anyExpanded = expanded.size > 0;
    const slot = anyExpanded ? SLOT_EXPANDED : SLOT_COLLAPSED;
    const minWidth = slot * groups.length + 60;

    // Grow the plot height so the two lanes sit far enough apart that the
    // tallest expanded card cannot overlap a card on the opposite lane. Lanes
    // are at y = ±0.5 within a 2.8-unit range, so the pixel gap between them is
    // height / 2.8; keep that gap above the tallest expanded card, with margin.
    const tallestCard = groups.reduce(
      (max, g, i) =>
        expanded.has(i) ? Math.max(max, estimateExpandedCardPx(g, CARD_WRAP_CHARS)) : max,
      0,
    );
    const plotHeight = Math.min(1600, Math.max(480, Math.ceil(2.8 * tallestCard * 1.2)));

    const shapes: Partial<Layout>["shapes"] = [
      {
        type: "line",
        x0: xMin,
        x1: xMax,
        y0: 0,
        y1: 0,
        line: { color: "#bdc3c7", width: 2 },
      },
      ...groups.map((_, i) => ({
        type: "line" as const,
        x0: xPos[i],
        x1: xPos[i],
        y0: 0,
        y1: yPos[i],
        line: { color: "#bdc3c7", width: 1, dash: "dot" as const },
      })),
    ];

    type Ann = NonNullable<Partial<Layout>["annotations"]>[number];

    // Card annotations tagged with their group index so expanded cards can be
    // reordered to the top layer without losing the click mapping.
    const cards = groups.map((g, i) => {
      const isOpen = expanded.has(i);
      const borderColor = g.isAccepted ? COLOR_ACCEPTED : COLOR_SYNONYM;
      const ann: Ann = {
        x: xPos[i],
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
        x: xPos[i],
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
        x: xPos,
        y: xPos.map(() => 0),
        marker: {
          size: 9,
          color: groups.map((g) => sourceColors[g.source] ?? "#3498db"),
          // square marker when the year has an accepted record, circle otherwise
          symbol: groups.map((g) =>
            g.isAccepted ? "square" : "circle"
          ) as unknown as string,
        },
        text: groups.map((g) => `${g.year}: ${g.count} name${g.count === 1 ? "" : "s"}`),
        hoverinfo: "text",
      },
    ];

    const layout: Partial<Layout> = {
      height: plotHeight,
      margin: { l: 20, r: 20, t: 30, b: 20 },
      xaxis: {
        title: { text: "Year of Publication" },
        range: [xMin, xMax],
        showgrid: false,
        zeroline: false,
        showticklabels: false,
        fixedrange: true,
      },
      yaxis: { visible: false, range: [-1.4, 1.4], fixedrange: true },
      plot_bgcolor: "white",
      paper_bgcolor: "white",
      showlegend: false,
      dragmode: false,
      shapes,
      annotations,
    };

    return { data, layout, annotationIndex, minWidth };
  }, [groups, expanded, sourceColors]);

  if (records.length === 0) {
    return <Text c="dimmed">No results to plot.</Text>;
  }

  return (
    <>
      {groups.length > 0 ? (
        <>
          <Group justify="space-between" mb="sm" wrap="nowrap">
            <Text>
              <b>
                {datedCount} name{datedCount === 1 ? "" : "s"}
              </b>{" "}
              with publication dates for <i>{query}</i>, grouped into{" "}
              <b>
                {groups.length} year{groups.length === 1 ? "" : "s"}
              </b>{" "}
              <Text span c="dimmed" size="xs">
                · click a card to expand or collapse it
              </Text>
            </Text>
            <Group gap="xs" wrap="nowrap">
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

          {orientation === "horizontal" ? (
            figure != null && (
              <div style={{ overflowX: "auto" }}>
                <PlotlyChart
                  data={figure.data}
                  layout={figure.layout}
                  config={{ scrollZoom: false, displayModeBar: false }}
                  style={{ width: "100%", minWidth: figure.minWidth }}
                  useResizeHandler
                  onClickAnnotation={(e) => {
                    const idx = figure.annotationIndex[e.index];
                    if (idx != null && idx >= 0) toggleCard(idx);
                  }}
                  onInitialized={(_, gd) =>
                    roundSynonymAnnotations(gd, figure.annotationIndex, groups)
                  }
                  onUpdate={(_, gd) =>
                    roundSynonymAnnotations(gd, figure.annotationIndex, groups)
                  }
                />
              </div>
            )
          ) : (
            <VerticalTimeline
              groups={groups}
              sourceColors={sourceColors}
              expanded={expanded}
              onToggle={toggleCard}
            />
          )}
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
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Author</Table.Th>
                  <Table.Th>Source</Table.Th>
                  <Table.Th>Status</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {undatedEntries.map((e, i) => (
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
