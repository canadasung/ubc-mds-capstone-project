"use client";

/**
 * Timeline view for species name records.
 *
 * Renders dated taxonomy entries on either a horizontal Plotly chart or a
 * vertical CSS timeline. A segmented toggle lets users switch between the two
 * orientations. Accepted names display in square boxes; all other entries
 * display in rounded boxes. In the horizontal view, shape is communicated via
 * axis marker symbol (square vs circle) and border color, because Plotly
 * annotation boxes do not support CSS border-radius. In the vertical view,
 * true CSS border-radius is applied to each card. Undated entries appear in a
 * collapsible table below either view.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  Alert,
  Anchor,
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
import { buildTimeline, type TimelineEntry } from "@/lib/transforms";

const PlotlyChart = dynamic(() => import("./PlotlyChart"), {
  ssr: false,
  loading: () => <Loader />,
});

/** Border color for accepted taxonomic name boxes, used in both views. */
const COLOR_ACCEPTED = "#1c7ed6";
/** Border color for synonym and unknown-status boxes, used in both views. */
const COLOR_SYNONYM = "#e67e22";

/**
 * Return true when the entry represents a currently accepted taxonomic name.
 *
 * Parameters
 * ----------
 * e : TimelineEntry
 *     A single timeline record.
 *
 * Returns
 * -------
 * boolean
 *     True when ``e.status`` equals "Accepted".
 */
function entryIsAccepted(e: TimelineEntry): boolean {
  return e.status === "Accepted";
}

/**
 * Build an HTML string for an expanded Plotly annotation card.
 *
 * Parameters
 * ----------
 * e : TimelineEntry
 *     The record whose details are rendered.
 * year : number
 *     Publication year shown as a labelled field.
 *
 * Returns
 * -------
 * string
 *     HTML string suitable for a Plotly annotation text property.
 */
function cardHtml(e: TimelineEntry, year: number): string {
  const src = e.url
    ? `<a href="${e.url}" target="_blank">${e.source}</a>`
    : e.source;
  const status =
    e.status && e.status !== "—"
      ? `<br><span style="color:#aaa">Status</span> ${e.status}`
      : "";
  return (
    `<b>${e.name}</b><br>` +
    `<span style="color:#aaa">Year</span> ${year}<br>` +
    `<span style="color:#aaa">Author</span> ${e.author}<br>` +
    `<span style="color:#aaa">Publication</span> ${e.publicationName}<br>` +
    `<span style="color:#aaa">Source</span> ${src}` +
    status
  );
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

// ---- Vertical timeline sub-components ------------------------------------

interface VerticalCardProps {
  /** Timeline record to display. */
  entry: TimelineEntry;
  /** Publication year shown in the expanded state. */
  year: number;
  /** Whether the card is currently in the expanded state. */
  isOpen: boolean;
  /** Callback invoked when the user clicks the card. */
  onToggle: () => void;
}

/**
 * Clickable card for the vertical timeline view.
 *
 * Renders with a square border (border-radius 0) when the entry status is
 * "Accepted" and with a rounded border (border-radius 10px) otherwise.
 * Clicking toggles between a compact stacked-name display and an expanded
 * detail view showing author, publication, source, and status.
 *
 * Parameters
 * ----------
 * entry : TimelineEntry
 *     Record providing name, author, publication, source, and status.
 * year : number
 *     Publication year shown in the expanded detail view.
 * isOpen : boolean
 *     True when the card should render in the expanded state.
 * onToggle : () => void
 *     Callback invoked on click to toggle the expanded state.
 */
function VerticalCard({ entry, year, isOpen, onToggle }: VerticalCardProps) {
  const accepted = entryIsAccepted(entry);
  const borderColor = accepted ? COLOR_ACCEPTED : COLOR_SYNONYM;
  const borderRadius = accepted ? 0 : 10;
  const nameParts = entry.name.trim().split(/\s+/);

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
        maxWidth: 260,
        minWidth: 120,
        textAlign: isOpen ? "left" : "center",
        userSelect: "none",
        lineHeight: 1.5,
      }}
    >
      {isOpen ? (
        <div>
          <div style={{ fontWeight: "bold", marginBottom: 4 }}>{entry.name}</div>
          <div>
            <span style={{ color: "#aaa" }}>Year</span> {year}
          </div>
          <div>
            <span style={{ color: "#aaa" }}>Author</span> {entry.author}
          </div>
          <div>
            <span style={{ color: "#aaa" }}>Publication</span> {entry.publicationName}
          </div>
          <div>
            <span style={{ color: "#aaa" }}>Source</span>{" "}
            {entry.url ? (
              <a
                href={entry.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: COLOR_ACCEPTED }}
              >
                {entry.source}
              </a>
            ) : (
              entry.source
            )}
          </div>
          {entry.status && entry.status !== "—" && (
            <div>
              <span style={{ color: "#aaa" }}>Status</span> {entry.status}
            </div>
          )}
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
            entry.name
          )}
        </div>
      )}
    </div>
  );
}

interface VerticalTimelineProps {
  /** Entries sorted oldest to newest. */
  sorted: TimelineEntry[];
  /** Mapping from source label to accent color, used for axis dots. */
  sourceColors: Record<string, string>;
  /** Indices (into sorted) of currently expanded cards. */
  expanded: Set<number>;
  /** Callback to toggle the expanded state of the card at the given index. */
  onToggle: (i: number) => void;
}

/**
 * Vertical CSS timeline for dated taxonomy entries.
 *
 * Lays out entries top to bottom along a central vertical axis line, with
 * cards alternating on the left and right sides. Each entry has a colored dot
 * and year label on the axis. Accepted names use square-cornered cards; all
 * other entries use rounded-cornered cards.
 *
 * Parameters
 * ----------
 * sorted : TimelineEntry[]
 *     Entries sorted oldest to newest.
 * sourceColors : Record<string, string>
 *     Accent colors keyed by source label, applied to axis dots.
 * expanded : Set<number>
 *     Set of indices whose cards are in the expanded state.
 * onToggle : (i: number) => void
 *     Callback invoked with the card index to toggle its expanded state.
 */
function VerticalTimeline({ sorted, sourceColors, expanded, onToggle }: VerticalTimelineProps) {
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

      {[...sorted].reverse().map((entry, displayIdx) => {
        const i = sorted.length - 1 - displayIdx;
        const isLeft = displayIdx % 2 === 0;
        const dotColor = sourceColors[entry.source] ?? "#3498db";
        const isOpen = expanded.has(i);

        return (
          <div
            key={`${entry.name}-${i}`}
            style={{
              display: "flex",
              alignItems: "center",
              marginBottom: 24,
              position: "relative",
            }}
          >
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
                <VerticalCard
                  entry={entry}
                  year={entry.year!}
                  isOpen={isOpen}
                  onToggle={() => onToggle(i)}
                />
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
                zIndex: 1,
              }}
            >
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
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
                }}
              >
                {entry.year}
              </Text>
            </div>

            {/* Right card slot */}
            <div style={{ flex: 1, paddingLeft: CENTER_WIDTH / 2 }}>
              {!isLeft && (
                <VerticalCard
                  entry={entry}
                  year={entry.year!}
                  isOpen={isOpen}
                  onToggle={() => onToggle(i)}
                />
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
 * Displays dated records either as a horizontal Plotly chart or as a vertical
 * CSS timeline, controlled by a segmented toggle. In the horizontal view,
 * accepted names use square axis markers and synonyms use circle markers, with
 * matching border colors (blue for accepted, orange for synonyms). In the
 * vertical view, accepted names use square-cornered cards and all other entries
 * use rounded-cornered cards. Undated entries appear in a collapsible table
 * below either view.
 */
export function TimelineView() {
  const { records } = useFilteredRecords();
  const query = useSearchStore((s) => s.submittedQuery);
  const [undatedOpen, undated] = useDisclosure(false);
  const [orientation, setOrientation] = useState<"horizontal" | "vertical">("horizontal");

  // Dated entries sorted oldest to newest, plus colors and the undated set.
  const { sorted, undatedEntries, sourceColors } = useMemo(() => {
    const t = buildTimeline(records);
    const s = [...t.dated].sort((a, b) => a.year! - b.year!);
    return { sorted: s, undatedEntries: t.undated, sourceColors: t.sourceColors };
  }, [records]);

  // The newest entry (latest year, last in sorted) starts expanded.
  // State resets whenever the data changes.
  const newestIdx = sorted.length - 1;
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  useEffect(() => {
    setExpanded(newestIdx >= 0 ? new Set([newestIdx]) : new Set());
  }, [sorted, newestIdx]);

  const toggleCard = useCallback((i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }, []);

  // Builds all Plotly figure data for the horizontal view.
  // Expanded cards are ordered last so they render on top.
  const figure = useMemo(() => {
    if (sorted.length === 0) return null;

    const years = sorted.map((s) => s.year!);
    const yPos = sorted.map((_, i) => (i % 2 === 0 ? 0.5 : -0.5));
    const yearMin = Math.min(...years) - 30;
    const yearMax = Math.max(...years) + 30;

    const shapes: Partial<Layout>["shapes"] = [
      {
        type: "line",
        x0: yearMin,
        x1: yearMax,
        y0: 0,
        y1: 0,
        line: { color: "#bdc3c7", width: 2 },
      },
      ...sorted.map((_, i) => ({
        type: "line" as const,
        x0: years[i],
        x1: years[i],
        y0: 0,
        y1: yPos[i],
        line: { color: "#bdc3c7", width: 1, dash: "dot" as const },
      })),
    ];

    type Ann = NonNullable<Partial<Layout>["annotations"]>[number];

    // Card annotations tagged with their sorted index so expanded cards can be
    // reordered to the top layer without losing the click mapping.
    const cards = sorted.map((e, i) => {
      const isOpen = expanded.has(i);
      const borderColor = entryIsAccepted(e) ? COLOR_ACCEPTED : COLOR_SYNONYM;
      const ann: Ann = {
        x: years[i],
        y: yPos[i],
        text: isOpen ? cardHtml(e, years[i]) : nameStacked(e.name),
        showarrow: false,
        bgcolor: "white",
        bordercolor: borderColor,
        borderwidth: 2,
        borderpad: isOpen ? 10 : 6,
        align: isOpen ? "left" : "center",
        font: { size: 13, color: "#333", family: "Courier New, monospace" },
        xanchor: "center",
        yanchor: "middle",
        captureevents: true,
      };
      return { ann, idx: i, isOpen };
    });

    // Year labels sit on the center line. Not clickable.
    const yearLabels = sorted.map((_, i) => {
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
    // annotation array position -> sorted index (or -1 for non-card labels)
    const annotationIndex = ordered.map((o) => o.idx);

    const data: Data[] = [
      {
        type: "scatter",
        mode: "markers",
        x: years,
        y: years.map(() => 0),
        marker: {
          size: 9,
          color: sorted.map((e) => sourceColors[e.source] ?? "#3498db"),
          // square marker for accepted names, circle for synonyms
          symbol: sorted.map((e) =>
            entryIsAccepted(e) ? "square" : "circle"
          ) as unknown as string,
        },
        text: sorted.map((e) => e.name),
        hoverinfo: "text",
      },
    ];

    const layout: Partial<Layout> = {
      height: 480,
      margin: { l: 20, r: 20, t: 30, b: 20 },
      xaxis: {
        title: { text: "Year of Publication" },
        range: [yearMin, yearMax],
        showgrid: false,
        zeroline: false,
        showticklabels: false,
      },
      yaxis: { visible: false, range: [-1.4, 1.4] },
      plot_bgcolor: "white",
      paper_bgcolor: "white",
      showlegend: false,
      dragmode: "pan",
      shapes,
      annotations,
    };

    return { data, layout, annotationIndex };
  }, [sorted, expanded, sourceColors]);

  if (records.length === 0) {
    return <Text c="dimmed">No results to plot.</Text>;
  }

  return (
    <>
      {sorted.length > 0 ? (
        <>
          <Group justify="space-between" mb="sm" wrap="nowrap">
            <Text>
              <b>
                {sorted.length} name{sorted.length === 1 ? "" : "s"}
              </b>{" "}
              with publication dates for <i>{query}</i>{" "}
              <Text span c="dimmed" size="xs">
                · click a card to expand or collapse it
              </Text>
            </Text>
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

          {orientation === "horizontal" ? (
            figure != null && (
              <PlotlyChart
                data={figure.data}
                layout={figure.layout}
                config={{ scrollZoom: true, displayModeBar: false }}
                style={{ width: "100%" }}
                useResizeHandler
                onClickAnnotation={(e) => {
                  const idx = figure.annotationIndex[e.index];
                  if (idx != null && idx >= 0) toggleCard(idx);
                }}
              />
            )
          ) : (
            <VerticalTimeline
              sorted={sorted}
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
