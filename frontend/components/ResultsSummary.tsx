"use client";

/**
 * Top-level counts shown to the right of the view switcher:
 *   - Synonym count  = records with status "Synonym" in the active source set
 *   - Source count   = number of sources the search routed to (active set)
 * The numbers are rendered bold + blue.
 */

import { Group, Text } from "@mantine/core";

import { statusOf } from "@/lib/fields";
import { useActiveSourceKeys, useFilteredRecords, useSearch } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";

export function ResultsSummary() {
  const submittedQuery = useSearchStore((s) => s.submittedQuery);
  const search = useSearch();
  const { records } = useFilteredRecords();
  const { keys } = useActiveSourceKeys();

  if (!submittedQuery || !search.data) return null;

  const synonymCount = records.filter(
    (r) => statusOf(r).toLowerCase() === "synonym",
  ).length;
  const sourceCount = keys.length;

  return (
    <Group gap="lg" wrap="nowrap">
      <Text size="lg">
        Synonym count:{" "}
        <Text span fw={700} c="blue">
          {synonymCount}
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
