"use client";

/**
 * Top-level counts shown to the right of the view switcher:
 *   - Name count    = distinct names found in the active source set
 *                     (matches the rows in the Table view)
 *   - Source count  = number of sources the search routed to (active set)
 * The numbers are rendered bold + blue.
 */

import { Group, Text } from "@mantine/core";

import { nameOf } from "@/lib/fields";
import { useActiveSourceKeys, useFilteredRecords, useSearch } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";

export function ResultsSummary() {
  const submittedQuery = useSearchStore((s) => s.submittedQuery);
  const search = useSearch();
  const { records } = useFilteredRecords();
  const { keys } = useActiveSourceKeys();

  if (!submittedQuery || !search.data) return null;

  const nameCount = new Set(
    records
      .map((r) => nameOf(r).trim().replace(/\s+/g, " ").toLowerCase())
      .filter((n) => n !== ""),
  ).size;
  const sourceCount = keys.length;

  return (
    <Group gap="lg" wrap="nowrap">
      <Text size="lg">
        Name count:{" "}
        <Text span fw={700} c="blue">
          {nameCount}
        </Text>
      </Text>
      <Text size="lg">
        Source count:{" "}
        <Text span fw={700} c="blue">
          {sourceCount}
        </Text>
      </Text>
    </Group>
  );
}
