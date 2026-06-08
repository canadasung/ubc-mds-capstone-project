"use client";

/** Debug View — ports view_debug.py. Raw inspection of the search records. */

import { Anchor, Table, Text } from "@mantine/core";

import { useSearch } from "@/lib/hooks";

export function DebugView() {
  const search = useSearch();
  const records = search.data?.results ?? [];

  if (records.length === 0) {
    return <Text c="dimmed">Search returned an empty table.</Text>;
  }

  const columns = Object.keys(records[0]);

  return (
    <>
      <Text c="dimmed" size="sm" mb="xs">
        {records.length} rows × {columns.length} columns
      </Text>
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
                          link
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
