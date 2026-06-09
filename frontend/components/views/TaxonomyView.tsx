"use client";

/**
 * Taxonomic View — ports view_taxonomy.py.
 *
 * Consumes /api/taxonomy (the backend shapes the per-source comparison), then
 * applies the active source filter client-side so it stays in sync with the
 * Advanced-options checkboxes — exactly like the record-based views. Ranks where
 * the *visible* sources disagree are highlighted red, and ranks that become
 * entirely empty after filtering are dropped.
 */

import { useMemo } from "react";
import { Alert, Loader, Table, Text } from "@mantine/core";
import { IconAlertTriangle, IconCircleCheck } from "@tabler/icons-react";

import { useActiveSourceKeys, useTaxonomy } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import { keyForApiName } from "@/lib/sources";
import type { TaxonomyRow } from "@/lib/types";

function cellValue(row: TaxonomyRow, rank: string): string {
  const v = row[rank];
  return v == null || v === "" ? "" : String(v);
}

export function TaxonomyView() {
  const query = useSearchStore((s) => s.submittedQuery);
  const { data, isLoading, isError } = useTaxonomy();
  const { keys, queriedSources } = useActiveSourceKeys();

  // Filter sources to the active set, then recompute the present ranks and the
  // disagreements over only the visible sources.
  const { sources, ranks, disagreements } = useMemo(() => {
    if (!data) return { sources: [] as TaxonomyRow[], ranks: [] as string[], disagreements: new Set<string>() };

    const allowed = new Set(keys);
    const filtered = data.sources.filter((row) => {
      const k = keyForApiName(row.source);
      // keep when allowed, or when the source is unknown to the queried set
      return allowed.has(k) || !queriedSources.includes(k);
    });

    // keep only ranks that still have at least one non-empty value
    const presentRanks = data.ranks.filter((r) =>
      filtered.some((row) => cellValue(row, r) !== ""),
    );

    const disagree = new Set<string>();
    for (const r of presentRanks) {
      const values = new Set(
        filtered.map((row) => cellValue(row, r)).filter((v) => v !== ""),
      );
      if (values.size > 1) disagree.add(r);
    }

    return { sources: filtered, ranks: presentRanks, disagreements: disagree };
  }, [data, keys, queriedSources]);

  if (isLoading) return <Loader />;
  if (isError || !data) {
    return <Text c="dimmed">No taxonomy found for &ldquo;{query}&rdquo;.</Text>;
  }

  if (sources.length === 0) {
    return <Text c="dimmed">No taxonomy to show for the selected sources.</Text>;
  }

  return (
    <>
      <Text c="dimmed" size="sm" mb="sm">
        Accepted classification for <b>{query}</b> per source · {sources.length}{" "}
        source{sources.length === 1 ? "" : "s"} shown
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
                  const val = cellValue(row, r);
                  return (
                    <Table.Td
                      key={r}
                      className={disagreements.has(r) ? "disagreeCell" : undefined}
                    >
                      {val === "" ? "—" : val}
                    </Table.Td>
                  );
                })}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      {sources.length > 1 &&
        (disagreements.size > 0 ? (
          <Alert mt="md" color="orange" variant="light" icon={<IconAlertTriangle />}>
            Sources disagree on: <b>{[...disagreements].join(", ")}</b> (
            {disagreements.size} rank{disagreements.size === 1 ? "" : "s"})
          </Alert>
        ) : (
          <Alert mt="md" color="green" variant="light" icon={<IconCircleCheck />}>
            All sources agree on the taxonomy.
          </Alert>
        ))}
    </>
  );
}
