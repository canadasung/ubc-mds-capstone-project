"use client";

/** Chooses the active view and handles the shared empty/loading/error states. */

import { Alert, Button, Center, Group, Loader, SimpleGrid, Stack, Text, ThemeIcon } from "@mantine/core";
import { IconCheck, IconInfoCircle } from "@tabler/icons-react";

import { useSearch } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import { backendNameForKey, labelForKey } from "@/lib/sources";
import { ApiError } from "@/lib/types";

import { TableView } from "@/components/views/TableView";
import { DetailView } from "@/components/views/DetailView";
import { TimelineView } from "@/components/views/TimelineView";
import { RelationsView } from "@/components/views/RelationsView";
import { TaxonomyView } from "@/components/views/TaxonomyView";

export function ResultsArea() {
  const activeView = useSearchStore((s) => s.activeView);
  const submittedQuery = useSearchStore((s) => s.submittedQuery);
  const submittedSources = useSearchStore((s) => s.submittedSources);
  const searchProgress = useSearchStore((s) => s.searchProgress);
  const isFiltering = useSearchStore((s) => s.isFiltering);
  const cancelSearch = useSearchStore((s) => s.cancelSearch);
  const setQuery = useSearchStore((s) => s.setQuery);
  const submit = useSearchStore((s) => s.submit);
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

  if (isFiltering) {
    return (
      <Center mih={200}>
        <Text c="dimmed" size="sm">Filtering results…</Text>
      </Center>
    );
  }

  if (search.isFetching) {
    const done = searchProgress?.done ?? 0;
    const activeBackendName = searchProgress?.source ?? null;

    return (
      <Center mih={200}>
        <Stack gap="md" align="center">
          <Text size="sm" c="dimmed">
            {searchProgress
              ? `Searching ${searchProgress.source} (${done}/${searchProgress.total})…`
              : "Starting search…"}
          </Text>
          <SimpleGrid cols={2} spacing="xs" verticalSpacing="xs">
            {submittedSources.map((key, i) => {
              const backendName = backendNameForKey(key);
              const isCompleted = i < done;
              const isActive = !isCompleted && backendName === activeBackendName;

              return (
                <Group key={key} gap="xs" wrap="nowrap">
                  {isCompleted ? (
                    <ThemeIcon size="xs" radius="xl" color="teal" variant="filled">
                      <IconCheck size={10} />
                    </ThemeIcon>
                  ) : isActive ? (
                    <Loader size="xs" />
                  ) : (
                    <Text size="xs" c="dimmed" lh={1} style={{ width: 18, textAlign: "center" }}>
                      ○
                    </Text>
                  )}
                  <Text
                    size="sm"
                    c={isCompleted ? "teal" : isActive ? undefined : "dimmed"}
                    fw={isActive ? 600 : undefined}
                  >
                    {labelForKey(key)}
                  </Text>
                </Group>
              );
            })}
          </SimpleGrid>
          <Button size="xs" variant="subtle" color="red" onClick={cancelSearch}>
            Cancel
          </Button>
        </Stack>
      </Center>
    );
  }

  if (search.error) {
    const err = search.error as ApiError;
    const suggestions = err.available ?? [];
    return (
      <Stack gap="md">
        <Alert variant="light" color="gray" title="No results">
          {err.message}
        </Alert>
        {suggestions.length > 0 && (
          <Stack gap="xs">
            <Text size="sm">Did you mean:</Text>
            <Group gap="xs">
              {suggestions.map((s) => (
                <Button
                  key={s}
                  size="compact-xs"
                  variant="light"
                  onClick={() => {
                    setQuery(s);
                    setTimeout(submit, 0);
                  }}
                >
                  {s}
                </Button>
              ))}
            </Group>
          </Stack>
        )}
      </Stack>
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
