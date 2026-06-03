"use client";

/**
 * Taxonomic View — ports view_taxonomy.py.
 *
 * Consumes /api/taxonomy directly (the backend already shapes the per-source
 * comparison and computes disagreements). Cells in a rank where sources disagree
 * are highlighted red; a summary line reports agreement.
 */

import { Alert, Loader, Table, Text } from "@mantine/core";
import { IconAlertTriangle, IconCircleCheck } from "@tabler/icons-react";

import { useTaxonomy } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";

export function TaxonomyView() {
  const query = useSearchStore((s) => s.submittedQuery);
  const { data, isLoading, isError } = useTaxonomy();

  if (isLoading) return <Loader />;
  if (isError || !data) return <Text c="dimmed">No taxonomy found for &ldquo;{query}&rdquo;.</Text>;

  const { ranks, sources, disagreements } = data;
  const disagree = new Set(disagreements);

  if (sources.length === 0) {
    return <Text c="dimmed">No taxonomy found for &ldquo;{query}&rdquo;.</Text>;
  }

  return (
    <>
      <Text c="dimmed" size="sm" mb="sm">
        Accepted classification for <b>{query}</b> per source · {sources.length}{" "}
        source{sources.length === 1 ? "" : "s"} queried
      </Text>

      <Table.ScrollContainer minWidth={500}>
        <Table withTableBorder withColumnBorders striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Source</Table.Th>
              {ranks.map((r) => (
                <Table.Th key={r}>{r}</Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sources.map((row) => (
              <Table.Tr key={row.source}>
                <Table.Td fw={600}>{row.source}</Table.Td>
                {ranks.map((r) => {
                  const val = row[r];
                  return (
                    <Table.Td
                      key={r}
                      className={disagree.has(r) ? "disagreeCell" : undefined}
                    >
                      {val == null || val === "" ? "—" : String(val)}
                    </Table.Td>
                  );
                })}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      {sources.length > 1 &&
        (disagreements.length > 0 ? (
          <Alert
            mt="md"
            color="orange"
            variant="light"
            icon={<IconAlertTriangle />}
          >
            Sources disagree on: <b>{disagreements.join(", ")}</b> (
            {disagreements.length} rank{disagreements.length === 1 ? "" : "s"})
          </Alert>
        ) : (
          <Alert mt="md" color="green" variant="light" icon={<IconCircleCheck />}>
            All sources agree on the taxonomy.
          </Alert>
        ))}
    </>
  );
}
