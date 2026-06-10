"use client";

/** Chooses the active view and handles the shared empty/loading/error states. */

import { Alert, Center, Loader, Stack, Text } from "@mantine/core";
import { IconInfoCircle } from "@tabler/icons-react";

import { useSearch } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import { ApiError } from "@/lib/types";

import { TableView } from "@/components/views/TableView";
import { DetailView } from "@/components/views/DetailView";
import { TimelineView } from "@/components/views/TimelineView";
import { RelationsView } from "@/components/views/RelationsView";
import { TaxonomyView } from "@/components/views/TaxonomyView";

export function ResultsArea() {
  const activeView = useSearchStore((s) => s.activeView);
  const submittedQuery = useSearchStore((s) => s.submittedQuery);
  const search = useSearch();

  if (!submittedQuery) {
    return (
      <Alert
        variant="light"
        color="blue"
        icon={<IconInfoCircle />}
        title="Run a search to populate this view"
      >
        Enter a species name on the left and press Search.
      </Alert>
    );
  }

  if (search.isLoading) {
    return (
      <Center mih={200}>
        <Stack align="center" gap="xs">
          <Loader />
          <Text c="dimmed" size="sm">
            Querying selected sources…
          </Text>
        </Stack>
      </Center>
    );
  }

  // 404 ("no sample data") is surfaced as suggestions in the SearchPanel; here
  // we just show a neutral message rather than a scary error.
  if (search.isError) {
    const err = search.error as ApiError;
    return (
      <Alert variant="light" color="gray" title="No results">
        {err.message}
      </Alert>
    );
  }

  switch (activeView) {
    case "Overview":
      return <TableView />;
    case "Detail":
      return <DetailView />;
    case "Relations":
      return <RelationsView />;  
    case "Timeline":
      return <TimelineView />;
    case "Taxonomy":           
      return <TaxonomyView />;
    default:
      return null;
  }
}
