"use client";

/**
 * Table View — ports view_table.py.
 *
 * Cross-source presence matrix (Name × Source). A ✓ in a source column links to
 * that source's page for the name (when a URL exists). The queried name is row 0
 * and bolded; remaining rows are sorted by how many sources recognize them.
 */

import { Anchor, Table, Text } from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";

import { useFilteredRecords } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import { buildPresenceTable } from "@/lib/transforms";

export function TableView() {
  const { records } = useFilteredRecords();
  const query = useSearchStore((s) => s.submittedQuery);

  if (records.length === 0) {
    return <Text c="dimmed">No names found across the selected sources.</Text>;
  }

  const { sources, rows } = buildPresenceTable(records, query);

  return (
    <Table.ScrollContainer minWidth={400}>
      <Table striped highlightOnHover withTableBorder withColumnBorders>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            {sources.map((src) => (
              <Table.Th key={src} style={{ textAlign: "center" }}>
                {src}
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
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
