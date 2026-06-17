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
 */

import { useMemo } from "react";
import { Anchor, Button, Group, Table, Text } from "@mantine/core";

import { useFilteredRecords } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import type { SpeciesRecord } from "@/lib/types";

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

  const columns = useMemo(() => columnsOf(records), [records]);

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
      <Group justify="space-between" align="center" mb="sm" wrap="nowrap">
        <Text c="dimmed" size="sm">
          {records.length} row{records.length === 1 ? "" : "s"} × {columns.length} columns
        </Text>
        <Button size="compact-sm" onClick={handleDownload}>
          Download CSV
        </Button>
      </Group>

      <Table.ScrollContainer minWidth={800}>
        <Table withTableBorder withColumnBorders striped fz="xs">
          <Table.Thead>
            <Table.Tr>
              {columns.map((c) => (
                <Table.Th key={c}>{c}</Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {records.map((rec, i) => (
              <Table.Tr key={i}>
                {columns.map((c) => {
                  const v = rec[c];
                  const str = v == null ? "" : String(v);
                  const isLink = /^https?:\/\//.test(str);
                  return (
                    <Table.Td key={c}>
                      {isLink ? (
                        <Anchor href={str} target="_blank" rel="noopener noreferrer">
                          {str}
                        </Anchor>
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
