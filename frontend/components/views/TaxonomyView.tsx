"use client";

/**
 * Taxonomic View — ports view_taxonomy.py.
 *
 * Consumes /api/taxonomy (the backend shapes the per-source comparison), then
 * applies the active source filter client-side so it stays in sync with the
 * Advanced-options checkboxes — exactly like the record-based views. Ranks that
 * become entirely empty after filtering are dropped.
 *
 * Disagreement is shown per-cell via a colour gradient (see lib/taxonomyShading):
 * each cell is shaded by its character edit distance from the column's reference
 * — the search query for Genus/Species, GBIF for every other rank. Blue when a
 * column has a single differing value, orange when it has several.
 */

import { useMemo } from "react";
import { Group, Loader, Stack, Table, Text, Tooltip } from "@mantine/core";

import { useActiveSourceKeys, useTaxonomy } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import { fullLabelForKey, keyForApiName, labelForKey } from "@/lib/sources";
import {
  cellValue,
  computeShading,
  SHADE_PALETTE,
  type CellShade,
} from "@/lib/taxonomyShading";
import type { TaxonomyRow } from "@/lib/types";

export function TaxonomyView() {
  const query = useSearchStore((s) => s.submittedQuery);
  const { data, isLoading, isError } = useTaxonomy();
  const { keys, queriedSources } = useActiveSourceKeys();

  // Filter sources to the active set, drop now-empty ranks, then shade each cell
  // by edit distance from its column reference.
  const { sources, ranks, shading } = useMemo(() => {
    if (!data) {
      return {
        sources: [] as TaxonomyRow[],
        ranks: [] as string[],
        shading: new Map<string, Map<string, CellShade | null>>(),
      };
    }

    const allowed = new Set(keys);
    const filtered = data.sources.filter((row) => {
      const k = keyForApiName(row.source);
      // Index Fungorum is excluded from this view.
      if (k === "index_fungorum") return false;
      // keep when allowed, or when the source is unknown to the queried set
      return allowed.has(k) || !queriedSources.includes(k);
    });

    // keep only ranks that still have at least one non-empty value
    const presentRanks = data.ranks.filter((r) =>
      filtered.some((row) => cellValue(row, r) !== ""),
    );

    // reference for Genus/Species is the (normalised) query the backend echoed
    const shading = computeShading(filtered, presentRanks, data.query);

    return { sources: filtered, ranks: presentRanks, shading };
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
            {sources.map((row) => {
              const sourceKey = keyForApiName(row.source);
              const shortLabel = labelForKey(sourceKey);
              const fullLabel = fullLabelForKey(sourceKey);
              return (
                <Table.Tr key={row.source}>
                  <Table.Td fw={600}>
                    <Tooltip
                      label={fullLabel}
                      disabled={fullLabel === shortLabel}
                      withArrow
                    >
                      <span>{shortLabel}</span>
                    </Tooltip>
                  </Table.Td>
                  {ranks.map((r) => {
                    const val = cellValue(row, r);
                    const shade = shading.get(r)?.get(row.source) ?? null;
                    return (
                      <Table.Td key={r} style={shade ?? undefined}>
                        {val === "" ? "—" : val}
                      </Table.Td>
                    );
                  })}
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      <ShadingLegend />
    </>
  );
}

/** Explains the white → blue gradient under the table. */
function ShadingLegend() {
  const levels: Array<{ level: 1 | 2 | 3 | 4; label: string }> = [
    { level: 1, label: "1" },
    { level: 2, label: "2–5" },
    { level: 3, label: "6–7" },
    { level: 4, label: "8+" },
  ];

  return (
    <Stack gap={6} mt="md">
      <Text size="xs" c="dimmed">
        Cell colour = character edit distance from the reference (Genus &amp;
        Species: your search query; other ranks: GBIF). White = matches the
        reference.
      </Text>

      <Group gap={6} wrap="nowrap">
        <Text size="xs" fw={600}>
          Edit distance:
        </Text>
        {levels.map(({ level, label }) => (
          <span
            key={level}
            style={{
              ...SHADE_PALETTE[level],
              fontSize: 11,
              padding: "1px 6px",
              borderRadius: 3,
              border: "1px solid rgba(0,0,0,0.1)",
            }}
          >
            {label}
          </span>
        ))}
      </Group>
    </Stack>
  );
}
