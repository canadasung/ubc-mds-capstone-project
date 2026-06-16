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

import { useMemo, useState } from "react";
import {
  Anchor,
  Group,
  Loader,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  Tooltip,
} from "@mantine/core";

import { useActiveSourceKeys, useSearch, useTaxonomy } from "@/lib/hooks";
import { linkOf, sourceOf, statusOf } from "@/lib/fields";
import { useSearchStore } from "@/lib/store";
import { fullLabelForKey, keyForApiName, labelForKey } from "@/lib/sources";
import {
  cellValue,
  computeShading,
  DEFAULT_BACKBONE,
  DIFF_PALETTE,
  MATCH_SHADE,
  type CellShade,
} from "@/lib/taxonomyShading";
import type { TaxonomyRow } from "@/lib/types";

export function TaxonomyView() {
  const query = useSearchStore((s) => s.submittedQuery);
  const { data, isLoading, isError } = useTaxonomy();
  const { keys, queriedSources } = useActiveSourceKeys();
  const search = useSearch();

  // Whether to shade cells by disagreement. Resets to on when the view remounts.
  const [highlight, setHighlight] = useState(true);

  // Source treated as the taxonomic "truth" backbone — the reference every
  // shaded cell is compared against. GBIF by default, user-selectable below.
  const [backbone, setBackbone] = useState(DEFAULT_BACKBONE);

  // Outbound link per source, taken from the search records (the taxonomy
  // endpoint carries no URLs). Prefer the "Accepted" row's link so it points at
  // the same record the taxonomy table treats as canonical.
  const linkBySource = useMemo(() => {
    const map = new Map<string, string>();
    for (const rec of search.data?.results ?? []) {
      const link = linkOf(rec);
      if (!link) continue;
      const key = keyForApiName(sourceOf(rec));
      if (!map.has(key) || statusOf(rec) === "Accepted") map.set(key, link);
    }
    return map;
  }, [search.data]);

  // Filter sources to the active set, drop now-empty ranks, then shade each cell
  // by edit distance from its column reference.
  const { sources, ranks, shading, disagreements, effectiveBackbone } =
    useMemo(() => {
    if (!data) {
      return {
        sources: [] as TaxonomyRow[],
        ranks: [] as string[],
        shading: new Map<string, Map<string, CellShade | null>>(),
        disagreements: [] as string[],
        effectiveBackbone: backbone,
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

    // Resolve the backbone to a source that's actually visible. If the chosen
    // one was filtered out, fall back to GBIF, then the first visible source.
    const visibleKeys = filtered.map((row) => keyForApiName(row.source));
    const effectiveBackbone = visibleKeys.includes(backbone)
      ? backbone
      : visibleKeys.includes(DEFAULT_BACKBONE)
        ? DEFAULT_BACKBONE
        : visibleKeys[0] ?? backbone;

    // shade the higher ranks against the chosen backbone source
    const shading = computeShading(filtered, presentRanks, effectiveBackbone);

    // A rank is a disagreement when the displayed sources hold 2+ distinct
    // (case-insensitive, non-empty) values for it. Recomputed here rather than
    // using data.disagreements so it reflects the filtered source set.
    const disagreements = presentRanks.filter((rank) => {
      const distinct = new Set(
        filtered
          .map((row) => cellValue(row, rank).toLowerCase())
          .filter((v) => v !== ""),
      );
      return distinct.size > 1;
    });

    return {
      sources: filtered,
      ranks: presentRanks,
      shading,
      disagreements,
      effectiveBackbone,
    };
  }, [data, keys, queriedSources, backbone]);

  // Options for the backbone picker: every visible source, keyed by source key.
  const backboneOptions = useMemo(
    () =>
      sources.map((row) => {
        const key = keyForApiName(row.source);
        return { value: key, label: labelForKey(key) };
      }),
    [sources],
  );

  if (isLoading) return <Loader />;
  if (isError || !data) {
    return (
      <Text c="dimmed" size="lg">
        No taxonomy found for &ldquo;{query}&rdquo;.
      </Text>
    );
  }

  if (sources.length === 0) {
    return (
      <Text c="dimmed" size="lg">
        No taxonomy to show for the selected sources.
      </Text>
    );
  }

  return (
    <>
      <Text c="dimmed" size="md" mb="sm">
        Accepted classification for <b>{query}</b> per source · {sources.length}{" "}
        source{sources.length === 1 ? "" : "s"} shown
      </Text>

      <DisagreementSummary
        sourceCount={sources.length}
        disagreements={disagreements}
      />

      <Switch
        checked={highlight}
        onChange={(e) => setHighlight(e.currentTarget.checked)}
        label="Highlight differences"
        size="md"
        mb="sm"
      />

      <Table.ScrollContainer minWidth={500}>
        <Table withTableBorder withColumnBorders striped fz="md">
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
              const link = linkBySource.get(sourceKey) ?? null;
              return (
                <Table.Tr key={row.source}>
                  <Table.Td fw={600}>
                    <Tooltip
                      label={fullLabel}
                      disabled={fullLabel === shortLabel}
                      withArrow
                    >
                      {link ? (
                        <Anchor
                          href={link}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {shortLabel}
                        </Anchor>
                      ) : (
                        <span>{shortLabel}</span>
                      )}
                    </Tooltip>
                  </Table.Td>
                  {ranks.map((r) => {
                    const val = cellValue(row, r);
                    const shade = shading.get(r)?.get(row.source) ?? null;
                    return (
                      <Table.Td key={r} style={highlight ? shade ?? undefined : undefined}>
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

      <Select
        label="Truth backbone"
        description="Source treated as the reference for Kingdom, Phylum, Class & Family."
        data={backboneOptions}
        value={effectiveBackbone}
        onChange={(v) => v && setBackbone(v)}
        allowDeselect={false}
        maw={260}
        mt="md"
      />

      {highlight && <ShadingLegend />}
    </>
  );
}

/**
 * One-line summary of where the displayed sources agree or disagree.
 * Hidden when fewer than two sources are shown (nothing to compare).
 */
function DisagreementSummary({
  sourceCount,
  disagreements,
}: {
  sourceCount: number;
  disagreements: string[];
}) {
  if (sourceCount < 2) return null;

  if (disagreements.length === 0) {
    return (
      <Text size="md" c="teal" mb="sm">
        All sources agree on the taxonomy.
      </Text>
    );
  }

  return (
    <Text size="md" c="orange" mb="sm">
      Sources disagree on: <b>{disagreements.join(", ")}</b> (
      {disagreements.length} rank{disagreements.length === 1 ? "" : "s"})
    </Text>
  );
}

/** Explains the backbone-relative blue shading under the table. */
function ShadingLegend() {
  const levels: Array<{ level: 1 | 2 | 3 | 4; label: string }> = [
    { level: 1, label: "1" },
    { level: 2, label: "2–5" },
    { level: 3, label: "6–7" },
    { level: 4, label: "8+" },
  ];

  const chip = (style: CellShade, label: string) => (
    <span
      style={{
        ...style,
        fontSize: 13,
        padding: "1px 6px",
        borderRadius: 3,
        border: "1px solid rgba(0,0,0,0.1)",
      }}
    >
      {label}
    </span>
  );

  return (
    <Stack gap={6} mt="md">
      <Text size="sm" c="dimmed">
        Only Kingdom, Phylum, Class &amp; Family are shaded. The backbone source
        and any source matching it are very light blue; cells that differ are a
        darker blue by character edit distance from the backbone.
      </Text>

      <Group gap={6} wrap="nowrap">
        <Text size="sm" fw={600}>
          Match:
        </Text>
        {chip(MATCH_SHADE, "backbone / same")}
        <Text size="sm" fw={600} ml="md">
          Edit distance:
        </Text>
        {levels.map(({ level, label }) => (
          <span key={level}>{chip(DIFF_PALETTE[level], label)}</span>
        ))}
      </Group>
    </Stack>
  );
}
