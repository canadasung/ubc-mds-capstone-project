"use client";

/**
 * Timeline View — ports view_timeline.py.
 *
 * Each dated synonym is drawn as a card on a horizontal year axis, cards
 * alternating above/below to reduce overlap. Undated entries fall back to a
 * collapsible table.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Alert, Anchor, Collapse, Loader, Table, Text, UnstyledButton } from "@mantine/core";
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

function cardHtml(e: TimelineEntry, year: number): string {
  const src = e.url
    ? `<a href="${e.url}" target="_blank">${e.source}</a>`
    : e.source;
  const status =
    e.status && e.status !== "—" ? `<br><span style="color:#aaa">Status</span> ${e.status}` : "";
  return (
    `<b>${e.name}</b><br>` +
    `<span style="color:#aaa">Year</span> ${year}<br>` +
    `<span style="color:#aaa">Author</span> ${e.author}<br>` +
    `<span style="color:#aaa">Publication</span> ${e.publicationName}<br>` +
    `<span style="color:#aaa">Source</span> ${src}` +
    status
  );
}

export function TimelineView() {
  const { records } = useFilteredRecords();
  const query = useSearchStore((s) => s.submittedQuery);
  const [undatedOpen, undated] = useDisclosure(false);

  // Dated entries sorted oldest → newest, plus colors and the undated set.
  const { sorted, undatedEntries, sourceColors } = useMemo(() => {
    const t = buildTimeline(records);
    const s = [...t.dated].sort((a, b) => a.year! - b.year!);
    return { sorted: s, undatedEntries: t.undated, sourceColors: t.sourceColors };
  }, [records]);

  // Which cards are expanded (indices into `sorted`). Collapsed cards show only
  // the name; clicking a card toggles it. The newest entry (latest year, last
  // in `sorted`) starts expanded. State resets whenever the data changes.
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
        // Run the connector all the way to the card center so it meets the box
        // at any size; the card's white background hides the overlapped end.
        y1: yPos[i],
        line: { color: "#bdc3c7", width: 1, dash: "dot" as const },
      })),
    ];

    const annotations: Partial<Layout>["annotations"] = sorted.map((e, i) => {
      const isOpen = expanded.has(i);
      return {
        x: years[i],
        y: yPos[i],
        // Collapsed cards show only the name; expanded show the full details.
        text: isOpen ? cardHtml(e, years[i]) : `<b>${e.name}</b>`,
        showarrow: false,
        bgcolor: "white",
        bordercolor: sourceColors[e.source] ?? "#3498db",
        borderwidth: 2,
        borderpad: isOpen ? 10 : 6,
        align: "left",
        font: { size: 11, color: "#333", family: "Courier New, monospace" },
        xanchor: "center",
        yanchor: "middle",
        // Required so Plotly emits plotly_clickannotation for this card.
        captureevents: true,
      };
    });

    const data: Data[] = [
      {
        type: "scatter",
        mode: "markers",
        x: years,
        y: years.map(() => 0),
        marker: {
          size: 9,
          color: sorted.map((e) => sourceColors[e.source] ?? "#3498db"),
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
      },
      yaxis: { visible: false, range: [-1.4, 1.4] },
      plot_bgcolor: "white",
      paper_bgcolor: "white",
      showlegend: false,
      dragmode: "pan",
      shapes,
      annotations,
    };

    return { data, layout };
  }, [sorted, expanded, sourceColors]);

  if (records.length === 0) {
    return <Text c="dimmed">No results to plot.</Text>;
  }

  return (
    <>
      {figure ? (
        <>
          <Text mb="sm">
            <b>
              {sorted.length} name{sorted.length === 1 ? "" : "s"}
            </b>{" "}
            with publication dates for <i>{query}</i>{" "}
            <Text span c="dimmed" size="xs">
              · click a card to expand or collapse it
            </Text>
          </Text>
          <PlotlyChart
            data={figure.data}
            layout={figure.layout}
            config={{ scrollZoom: true, displayModeBar: false }}
            style={{ width: "100%" }}
            useResizeHandler
            onClickAnnotation={(e) => toggleCard(e.index)}
          />
        </>
      ) : (
        <Alert variant="light" color="blue">
          No publication years found in the results — timeline cannot be rendered.
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
