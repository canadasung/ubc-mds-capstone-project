"use client";

/** Chooses the active view and handles the shared empty/loading/error states. */

import { Alert, Button, Center, Group, Loader, SimpleGrid, Stack, Text, ThemeIcon, Tooltip } from "@mantine/core";
import { IconCheck, IconInfoCircle, IconX } from "@tabler/icons-react";

import { useSearch, useFilteredRecords } from "@/lib/hooks";
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
  const cachedQuery = useSearchStore((s) => s.cachedQuery);
  const cachedSources = useSearchStore((s) => s.cachedSources);
  const searchProgress = useSearchStore((s) => s.searchProgress);
  const isFiltering = useSearchStore((s) => s.isFiltering);
  const hasHydrated = useSearchStore((s) => s._hasHydrated);
  const cancelSearch = useSearchStore((s) => s.cancelSearch);
  const sourceErrors = useSearchStore((s) => s.sourceErrors);
  const setQuery = useSearchStore((s) => s.setQuery);
  const submit = useSearchStore((s) => s.submit);
  const search = useSearch();
  const { records } = useFilteredRecords();

  if (!hasHydrated) {
    return (
      <Center mih={200}>
        <Text c="dimmed" size="sm">Reloading…</Text>
      </Center>
    );
  }

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

    // For incremental searches (same query, new source added), sources that
    // were already cached should appear immediately as completed.
    const isIncremental = cachedQuery === submittedQuery && cachedSources.length > 0;
    const fetchingKeys = isIncremental
      ? submittedSources.filter((k) => !cachedSources.includes(k))
      : submittedSources;

    return (
      <Center mih={200}>
        <Stack gap="md" align="center">
          <Text size="sm" c="dimmed">
            {searchProgress
              ? `Searching ${searchProgress.source} (${done}/${searchProgress.total})…`
              : "Starting search…"}
          </Text>
          <SimpleGrid cols={2} spacing="xs" verticalSpacing="xs">
            {submittedSources.map((key) => {
              const backendName = backendNameForKey(key);
              const alreadyCached = isIncremental && cachedSources.includes(key);
              const fetchIndex = fetchingKeys.indexOf(key);
              const isCompleted = alreadyCached || (fetchIndex >= 0 && fetchIndex < done);
              const isActive = !isCompleted && backendName === activeBackendName;
              const error = sourceErrors[key];

              return (
                <Group key={key} gap="xs" wrap="nowrap">
                  {error ? (
                    <Tooltip label={error} withArrow>
                      <ThemeIcon size="xs" radius="xl" color="red" variant="filled">
                        <IconX size={10} />
                      </ThemeIcon>
                    </Tooltip>
                  ) : isCompleted ? (
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
                    c={error ? "red" : isCompleted ? "teal" : isActive ? undefined : "dimmed"}
                    fw={isActive ? 600 : undefined}
                  >
                    {labelForKey(key)}
                  </Text>
                </Group>
              );
            })}
          </SimpleGrid>
          <Group gap="sm" justify="center" wrap="wrap">
            <Group gap={4} wrap="nowrap">
              <ThemeIcon size="xs" radius="xl" color="teal" variant="filled">
                <IconCheck size={10} />
              </ThemeIcon>
              <Text size="xs" c="dimmed">Found</Text>
            </Group>
            <Group gap={4} wrap="nowrap">
              <Loader size="xs" />
              <Text size="xs" c="dimmed">Searching</Text>
            </Group>
            <Group gap={4} wrap="nowrap">
              <Text size="xs" c="dimmed" lh={1}>○</Text>
              <Text size="xs" c="dimmed">Pending</Text>
            </Group>
            <Group gap={4} wrap="nowrap">
              <ThemeIcon size="xs" radius="xl" color="red" variant="filled">
                <IconX size={10} />
              </ThemeIcon>
              <Text size="xs" c="dimmed">Error</Text>
            </Group>
          </Group>
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
    const isExactMatch =
      suggestions.length === 1 &&
      suggestions[0].toLowerCase() === submittedQuery.toLowerCase();
    return (
      <Stack gap="md">
        <Alert variant="light" color="gray" title="No results">
          {err.message}
        </Alert>
        {isExactMatch ? (
          <Text size="sm" c="dimmed">
            This species exists but was not found in your selected sources. Try
            selecting additional sources, or use the <strong>Suggest</strong>{" "}
            button to find sources by kingdom.
          </Text>
        ) : suggestions.length > 0 ? (
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
        ) : null}
      </Stack>
    );
  }

  if (search.data && records.length === 0) {
    return (
      <Stack gap="md">
        <Alert variant="light" color="gray" title="No results">
          No results found in your selected sources.
        </Alert>
        <Text size="sm" c="dimmed">
          This species exists but was not found in your selected sources. Try
          selecting additional sources, or use the <strong>Suggest</strong>{" "}
          button to find sources by kingdom.
        </Text>
      </Stack>
    );
  }

  const erroredSources = Object.entries(sourceErrors);

  return (
    <Stack gap="md">
      {erroredSources.length > 0 && (
        <Alert
          variant="light"
          color="red"
          icon={<IconX />}
          title={`${erroredSources.length} source${erroredSources.length > 1 ? "s" : ""} failed`}
        >
          <Stack gap={4}>
            {erroredSources.map(([key, message]) => (
              <Text key={key} size="sm">
                <strong>{labelForKey(key)}</strong> — {message}
              </Text>
            ))}
          </Stack>
        </Alert>
      )}
      {(() => {
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
      })()}
    </Stack>
  );
}
