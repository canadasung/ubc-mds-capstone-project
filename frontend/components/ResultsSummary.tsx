"use client";

/**
 * Top-level counts shown to the right of the view switcher:
 *   - Name count    = distinct names found in the active source set
 *                     (matches the rows in the Table view)
 *   - Source count  = number of sources the search routed to (active set)
 * The numbers are rendered bold + blue.
 */

import { Text } from "@mantine/core";

import { nameOf, sourceOf } from "@/lib/fields";
import { useFilteredRecords, useSearch } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";

export function ResultsSummary() {
  const submittedQuery = useSearchStore((s) => s.submittedQuery);
  const search = useSearch();
  const { records } = useFilteredRecords();

  if (!submittedQuery || !search.data) return null;

  const nameCount = new Set(
    records
      .map((r) => nameOf(r).trim().replace(/\s+/g, " ").toLowerCase())
      .filter((n) => n !== ""),
  ).size;
  const sourceCount = new Set(records.map((r) => sourceOf(r))).size;

  return (
    <Text size="lg">
      Found{" "}
      <Text span fw={700} c="blue">
        {nameCount} {nameCount === 1 ? "name" : "names"}
      </Text>{" "}
      from{" "}
      <Text span fw={700} c="blue">
        {sourceCount} API {sourceCount === 1 ? "source" : "sources"}
      </Text>
    </Text>
  );
}
