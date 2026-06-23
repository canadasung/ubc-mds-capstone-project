"use client";

/**
 * Table View — ports view_table.py.
 *
 * Cross-source presence matrix (Name × Source). A ✓ in a source column links to
 * that source's page for the name (when a URL exists). The queried name is row 0
 * and bolded; remaining rows are sorted by how many sources recognize them.
 * Source columns are ordered by how many names each source has, most to least.
 *
 * Every column header is clickable to re-sort the rows manually: the Name column
 * sorts alphabetically, and a source column groups the names it recognizes. Each
 * header cycles ascending, descending, then back to the default order. The
 * queried name stays pinned at the top in every mode.
 *
 * The table scrolls within a bounded height and uses a sticky header, so the
 * Name and source column headers stay visible while scrolling through tall tables.
 */

import { useCallback, useMemo, useState } from "react";
import { Anchor, Table, Text, Tooltip, UnstyledButton } from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";

import { useFilteredRecords } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import { fullForLabel } from "@/lib/sources";
import { buildPresenceTable, type PresenceRow } from "@/lib/transforms";
import { SortCaret, SORT_BTN_STYLE, nextSortState } from "@/components/SortCaret";

/**
 * Compare two presence rows for the manually-sorted column.
 *
 * Parameters
 * ----------
 * a, b : PresenceRow
 *     Rows to compare.
 * key : string
 *     The active sort column: ``"name"`` for the Name column, otherwise a source
 *     label.
 *
 * Returns
 * -------
 * number
 *     Negative, zero, or positive in the manner of ``Array.prototype.sort``. For
 *     the Name column the comparison is alphabetical; for a source column, names
 *     the source has a record for sort before names it does not.
 */
function compareRows(a: PresenceRow, b: PresenceRow, key: string): number {
  if (key === "name") {
    return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
  }
  const presentA = key in a.cells ? 0 : 1;
  const presentB = key in b.cells ? 0 : 1;
  return presentA - presentB;
}

export function TableView() {
  const { records } = useFilteredRecords();
  const query = useSearchStore((s) => s.submittedQuery);

  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);

  const { sources, rows } = useMemo(
    () => buildPresenceTable(records, query),
    [records, query],
  );

  const toggleSort = useCallback(
    (key: string) => setSort((prev) => nextSortState(prev, key)),
    [],
  );

  // sort === null keeps the default order (query row first, then most-recognized
  // names). When a header is toggled, the query row stays pinned and the rest are
  // ordered by the chosen column.
  const displayRows = useMemo(() => {
    if (!sort) return rows;
    const factor = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      if (a.isQuery !== b.isQuery) return a.isQuery ? -1 : 1;
      return factor * compareRows(a, b, sort.key);
    });
  }, [rows, sort]);

  return (
    <Table.ScrollContainer minWidth={400} maxHeight="70vh">
      <Table striped highlightOnHover withTableBorder withColumnBorders stickyHeader>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>
              <UnstyledButton onClick={() => toggleSort("name")} style={SORT_BTN_STYLE}>
                Name
                <SortCaret dir={sort?.key === "name" ? sort.dir : null} />
              </UnstyledButton>
            </Table.Th>
            {sources.map((src) => {
              const full = fullForLabel(src);
              return (
                <Table.Th key={src} style={{ textAlign: "center" }}>
                  <UnstyledButton onClick={() => toggleSort(src)} style={SORT_BTN_STYLE}>
                    <Tooltip label={full} disabled={full === src} withArrow>
                      <span>{src}</span>
                    </Tooltip>
                    <SortCaret dir={sort?.key === src ? sort.dir : null} />
                  </UnstyledButton>
                </Table.Th>
              );
            })}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {displayRows.map((row) => (
            <Table.Tr key={row.name} className={row.isQuery ? "queryRow" : undefined}>
              <Table.Td>
                <Text fw={row.isQuery ? 700 : 400} fs="italic">
                  {row.name}
                </Text>
              </Table.Td>
              {sources.map((src) => {
                const cell = row.cells[src];
                const present = src in row.cells;
                return (
                  <Table.Td key={src} style={{ textAlign: "center" }}>
                    {!present ? null : cell ? (
                      <Anchor href={cell} target="_blank" rel="noopener noreferrer">
                        <IconCheck size={16} />
                      </Anchor>
                    ) : (
                      <IconCheck size={16} color="var(--mantine-color-gray-6)" />
                    )}
                  </Table.Td>
                );
              })}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
