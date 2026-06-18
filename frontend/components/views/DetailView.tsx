"use client";

/**
 * Detail View — the full fetched records for the active source set, shown as a
 * raw table and downloadable as CSV.
 *
 * Records are filtered to the active source selection (the same set the other
 * tabs use), so the table and the download stay in sync with the
 * Database-selection checkboxes. Every column is shown with its raw CSV header;
 * the Download button exports exactly those rows and columns, named from the
 * query (e.g. "amanita_muscaria.csv").
 *
 * The table scrolls within a bounded height and uses a sticky header, so the
 * column names stay visible while scrolling through long result lists.
 */

import { useCallback, useMemo, useState } from "react";
import { Anchor, Button, Group, Table, Text, UnstyledButton } from "@mantine/core";

import { useFilteredRecords, useSearch } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import type { SpeciesRecord } from "@/lib/types";
import { SortCaret, SORT_BTN_STYLE, nextSortState } from "@/components/SortCaret";

const formatHeader = (col: string) =>
  col
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bApi\b/g, "API");

/** Column order: union of keys across records, first-seen order. */
function columnsOf(records: SpeciesRecord[]): string[] {
  const cols: string[] = [];
  for (const rec of records) {
    for (const k of Object.keys(rec)) {
      if (!cols.includes(k)) cols.push(k);
    }
  }
  return cols;
}

/** RFC-4180-ish CSV cell: quote when it contains a comma, quote, or newline. */
function csvCell(value: unknown): string {
  const s = value == null ? "" : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function toCsv(records: SpeciesRecord[], columns: string[]): string {
  const header = columns.map(csvCell).join(",");
  const body = records.map((rec) => columns.map((c) => csvCell(rec[c])).join(","));
  return [header, ...body].join("\r\n");
}

/** "Amanita muscaria" → "amanita_muscaria" (matches the backend file stem). */
function fileStem(query: string): string {
  const stem = query.trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
  return stem || "results";
}

export function DetailView() {
  const { records } = useFilteredRecords();
  const query = useSearchStore((s) => s.submittedQuery);
  const { data: searchData } = useSearch();
  const unavailMarker = searchData?.unavailable_marker ?? "N/A";
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);

  const columns = useMemo(() => columnsOf(records), [records]);

  const toggle = useCallback(
    (key: string) => setSort((prev) => nextSortState(prev, key)),
    [],
  );

  const sortedRecords = useMemo(() => {
    if (!sort) return records;
    const { key, dir } = sort;
    // Sort rank for a cell value in ascending order: real values (0) sort before
    // the unavailable marker (1), which sorts before blank cells (2). So in
    // ascending order the marker comes after every real value and blanks come
    // last; the direction flip reverses this for descending order. Real values
    // are compared alphabetically.
    const rankOf = (v: string) => (v === "" ? 2 : v === unavailMarker ? 1 : 0);
    return [...records].sort((a, b) => {
      const valA = a[key] == null ? "" : String(a[key]);
      const valB = b[key] == null ? "" : String(b[key]);
      const rankA = rankOf(valA);
      const rankB = rankOf(valB);
      let cmp: number;
      if (rankA !== rankB) {
        cmp = rankA - rankB;
      } else if (rankA === 0) {
        cmp = valA.localeCompare(valB, undefined, { sensitivity: "base" });
      } else {
        cmp = 0;
      }
      return dir === "asc" ? cmp : -cmp;
    });
  }, [records, sort, unavailMarker]);

  const handleDownload = () => {
    const csv = toCsv(records, columns);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${fileStem(query)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <Group justify="space-between" align="center" mb="xs" wrap="nowrap">
        <Text c="dimmed" size="sm">
          {records.length} row{records.length === 1 ? "" : "s"} × {columns.length} columns
        </Text>
        <Button size="compact-sm" onClick={handleDownload}>
          Download CSV
        </Button>
      </Group>

      <Text c="dimmed" size="xs" mb="sm">
        A blank cell means the source was queried but returned no value for that field.{" "}
        <span style={{ color: "var(--mantine-color-gray-5)" }}>{unavailMarker}</span>{" "}
        means the source does not provide that field at all. (For sources with status available,
        taxonomy fields are attached to Accepted names only.)
      </Text>

      <Table.ScrollContainer minWidth={800} maxHeight="70vh">
        <Table withTableBorder withColumnBorders striped fz="xs" stickyHeader>
          <Table.Thead>
            <Table.Tr>
              {columns.map((c) => (
                <Table.Th key={c}>
                  <UnstyledButton onClick={() => toggle(c)} style={SORT_BTN_STYLE}>
                    {formatHeader(c)}
                    <SortCaret dir={sort?.key === c ? sort.dir : null} />
                  </UnstyledButton>
                </Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sortedRecords.map((rec, i) => (
              <Table.Tr key={i}>
                {columns.map((c) => {
                  const v = rec[c];
                  const str = v == null ? "" : String(v);
                  const isLink = c !== "original_source" && /^https?:\/\//.test(str);
                  return (
                    <Table.Td key={c}>
                      {isLink ? (
                        <Anchor href={str} target="_blank" rel="noopener noreferrer">
                          {str}
                        </Anchor>
                      ) : str === unavailMarker ? (
                        <span style={{ color: "var(--mantine-color-gray-5)" }}>{str}</span>
                      ) : (
                        str
                      )}
                    </Table.Td>
                  );
                })}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </>
  );
}
