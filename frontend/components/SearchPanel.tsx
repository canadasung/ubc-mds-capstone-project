"use client";

/**
 * SearchPanel — ports the left search column of prototype_master.py:
 *   - search form (Enter submits, like st.form)
 *   - "Database selection" collapse: per-source checkboxes
 *   - Select all / Unselect all / Suggest buttons
 *   - Live progress bar while search runs
 *   - "Did you mean?" suggestions parsed from empty results
 */

import { useState } from "react";
import {
  ActionIcon,
  Box,
  Button,
  Checkbox,
  Collapse,
  Divider,
  Group,
  Progress,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChevronDown, IconChevronRight, IconSearch } from "@tabler/icons-react";

import { useSearch } from "@/lib/hooks";
import { useSearchStore } from "@/lib/store";
import { GROUP_LABELS, SOURCES, SOURCE_KEYS, keyForApiName, type SourceGroup } from "@/lib/sources";
import { suggest } from "@/lib/api";
import { ApiError } from "@/lib/types";

const GROUP_ORDER: SourceGroup[] = ["backbone", "symbiota", "independent"];

export function SearchPanel() {
  const query = useSearchStore((s) => s.query);
  const setQuery = useSearchStore((s) => s.setQuery);
  const submit = useSearchStore((s) => s.submit);
  const selectedSources = useSearchStore((s) => s.selectedSources);
  const toggleSource = useSearchStore((s) => s.toggleSource);
  const setAllSources = useSearchStore((s) => s.setAllSources);
  const setSources = useSearchStore((s) => s.setSources);
  const isSearching = useSearchStore((s) => s.isSearching);
  const searchProgress = useSearchStore((s) => s.searchProgress);

  const [advancedOpen, advanced] = useDisclosure(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const search = useSearch();
  const error = search.error as ApiError | null;

  const handleSuggest = async () => {
    if (!query.trim()) {
      setSuggestError(
        "Please type in a valid search query to use automatic source suggestions."
      );
      return;
    }
    setIsSuggesting(true);
    setSuggestError(null);
    try {
      const res = await suggest(query.trim());
      if (res.sources.length === 0) {
        setSuggestError(
          "Could not identify kingdom. Please type in a valid search query to use the automatic source suggestions."
        );
        return;
      }
      const keys = res.sources.map(keyForApiName).filter((k) => SOURCE_KEYS.includes(k));
      setSources(keys);
    } catch {
      setSuggestError("Suggest request failed. Is the server running?");
    } finally {
      setIsSuggesting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSuggestError(null);
    submit();
  };

  return (
    <Stack gap="md">
      <Title order={4}>Search</Title>

      <form onSubmit={handleSubmit}>
        <Stack gap="sm">
          <TextInput
            placeholder="Enter species name (e.g. Podospora anserina)"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            leftSection={<IconSearch size={16} />}
            aria-label="Search query"
          />
          <Button type="submit" fullWidth loading={isSearching} disabled={isSearching}>
            Search
          </Button>

          {isSearching && (
            <Stack gap={4}>
              <Progress
                value={
                  searchProgress
                    ? (searchProgress.done / searchProgress.total) * 100
                    : 0
                }
                animated={!searchProgress}
                size="sm"
              />
              <Text size="xs" c="dimmed">
                {searchProgress
                  ? `Searching ${searchProgress.source} (${searchProgress.done}/${searchProgress.total})…`
                  : "Starting search…"}
              </Text>
            </Stack>
          )}
        </Stack>
      </form>

      {/* Error + "Did you mean?" */}
      {error && (
        <Box>
          <Text c="red" size="sm">
            {error.message}
          </Text>
          {error.available && error.available.length > 0 && (
            <Box mt="xs">
              <Text size="sm" mb={4}>
                Did you mean:
              </Text>
              <Group gap="xs">
                {error.available.map((s) => (
                  <Button
                    key={s}
                    size="compact-xs"
                    variant="light"
                    onClick={() => {
                      setQuery(s);
                      // submit on next tick so the store has the new query
                      setTimeout(submit, 0);
                    }}
                  >
                    {s}
                  </Button>
                ))}
              </Group>
            </Box>
          )}
        </Box>
      )}

      <Divider />

      {/* Database selection */}
      <Box>
        <Button
          variant="subtle"
          fullWidth
          justify="space-between"
          rightSection={
            advancedOpen ? (
              <IconChevronDown size={16} />
            ) : (
              <IconChevronRight size={16} />
            )
          }
          onClick={advanced.toggle}
        >
          Database selection
        </Button>

        <Collapse in={advancedOpen}>
          <Stack gap="sm" mt="sm">
            <Stack gap={4}>
              <Button
                size="compact-sm"
                variant="default"
                fullWidth
                onClick={() => {
                  setSuggestError(null);
                  setAllSources(true);
                }}
              >
                Select all
              </Button>
              <Button
                size="compact-sm"
                variant="default"
                fullWidth
                onClick={() => {
                  setSuggestError(null);
                  setAllSources(false);
                }}
              >
                Unselect all
              </Button>
              <Button
                size="compact-sm"
                variant="default"
                fullWidth
                loading={isSuggesting}
                onClick={handleSuggest}
              >
                Suggest
              </Button>
            </Stack>

            {suggestError && (
              <Text c="red" size="xs">{suggestError}</Text>
            )}

            <Stack gap="xs">
              {GROUP_ORDER.map((group) => (
                <Box key={group}>
                  <Text size="sm" fw={600} mb={4}>
                    {GROUP_LABELS[group]}
                  </Text>
                  <Stack gap={4} pl="xs">
                    {SOURCES.filter((s) => s.group === group).map((s) => (
                      <Checkbox
                        key={s.key}
                        label={s.label}
                        size="sm"
                        checked={selectedSources.includes(s.key)}
                        onChange={() => toggleSource(s.key)}
                      />
                    ))}
                  </Stack>
                </Box>
              ))}
            </Stack>
          </Stack>
        </Collapse>
      </Box>
    </Stack>
  );
}

/** Small reusable collapse toggle for the panel header (used in page.tsx). */
export function PanelToggle({
  open,
  onClick,
}: {
  open: boolean;
  onClick: () => void;
}) {
  return (
    <Tooltip label={open ? "Collapse search panel" : "Expand search panel"}>
      <ActionIcon variant="subtle" onClick={onClick} aria-label="Toggle search panel">
        {open ? <IconChevronRight size={18} /> : <IconChevronDown size={18} />}
      </ActionIcon>
    </Tooltip>
  );
}
